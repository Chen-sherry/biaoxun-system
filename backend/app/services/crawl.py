# -*- coding: utf-8 -*-
"""
爬虫服务层
支持两个国家级公共资源交易平台：
  1. ccgp.gov.cn — 中国政府采购网（静态列表页，最稳定的主源）
  2. ggzy.gov.cn — 全国公共资源交易平台（首页交易区块 + 详情页）

轻量实现：httpx + BeautifulSoup，不引入 Scrapy 重依赖。

2026-11 实测调优要点（原独立「爬虫」包合并）：
  - ccgp：search.ccgp.gov.cn/bxsearch 搜索接口经常 500，已废弃；
    改用 www.ccgp.gov.cn/cggg/{zygg|dfgg}/{分类}/index_{page}.htm 静态列表页，
    12 个分类目录全部实测可用。
  - ccgp：列表只给标题/时间，详情页有完整「公告概要」表（采购单位、代理机构、
    预算、总成交金额、开标时间、供应商…），新增 _fill_ccgp_detail() 抓详情补字段，
    并把正文写入 content/content_text（原来全库正文为空，AI 检索只能靠标题粗筛）。
  - ggzy：旧的 /information/html/b/{biztype}/{yyyyMMdd}/00/list_*.shtml 已 404，
    /information/pubTradingInfo/getTradList 接口也 404、/his/ 历史接口挂死；
    目前唯一可用入口是首页 server-rendered 的「交易公告/成交公示」区块
    （约 24 条/天），锚文本被截断 → 必须进详情页取完整标题。
  - 地区：ggzy /data/indexCollect.json 提供完整省级(areaJson) + 市级(cityJson)
    国标地区字典，运行时拉取缓存，用于 ccgp「地域/行政区域」中文名 → 6 位地区码。
  - 限速：详情页抓取间隔 0.3~0.4s，单轮最多 MAX_DETAIL_PER_RUN 条详情，
    缺正文的存量条目后续轮次自动补（见 crawl_and_save）。

采集到的数据 → 写入 bid_info 表，字段映射见 _map_to_bid_info()
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import httpx
from bs4 import BeautifulSoup

from app.config import settings
from app.database import SessionLocal
from app.models.bid import BidInfo, BidSource
from app.services.data_clean import (
    strip_html, clean_date,
    infer_notice_type_id, infer_procure_type, infer_customer_group,
    load_industries, infer_industry_id,
    _load_notice_type_map,
)

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}

# 详情页抓取限速：单轮最多抓多少条详情（超限的下一轮自动补）
MAX_DETAIL_PER_RUN = 60
DETAIL_SLEEP = 0.5      # 详情页间隔（秒）（2026-11 降频：放缓抓取速率）
LIST_SLEEP = 2.0        # 列表页间隔（秒）


# =====================================================
# 数据源配置
# =====================================================

SOURCE_GGZY = {
    "code": "ggzy",
    "name": "全国公共资源交易平台",
    "source_type": 1,  # 爬虫
    # 旧列表页格式（已 404）：/information/html/b/{biztype}/{yyyyMMdd}/00/list_{biztype}_{page}.shtml
    # 现用首页交易区块：http://www.ggzy.gov.cn/
    "list_url": "http://www.ggzy.gov.cn/",
    "detail_url_prefix": "http://www.ggzy.gov.cn",
    "field_rules": {},
    "interval_minutes": 120,
}

SOURCE_CCGP = {
    "code": "ccgp",
    "name": "中国政府采购网",
    "source_type": 1,
    # 旧的 search.ccgp.gov.cn/bxsearch 搜索接口经常 500，已废弃
    # 现用静态列表页（见 CCGP_CATEGORIES）
    "list_url": "http://www.ccgp.gov.cn/cggg/zygg/gkzb/index_{page}.htm",
    "detail_url_prefix": "http://www.ccgp.gov.cn",
    "field_rules": {},
    # 2026-11 降频：ccgp 封过服务器 IP，解封后维持低频（真正生效的是 bid_source.interval_minutes）
    "interval_minutes": 180,
}

# ccgp 静态列表页分类（2026-11 实测 12 个目录 index_1.htm 全部 200/20 条）
# 目录来源：/cggg/zygg/ 与 /cggg/dfgg/ 一级页；dyly（单一来源）目录已不存在
CCGP_CATEGORIES = {
    "zygg_gkzb":    ("中央-公开招标公告", "公开招标",     "http://www.ccgp.gov.cn/cggg/zygg/gkzb/index_{page}.htm"),
    "zygg_zbgg":    ("中央-中标公告",     "中标公告",     "http://www.ccgp.gov.cn/cggg/zygg/zbgg/index_{page}.htm"),
    "zygg_cjgg":    ("中央-成交公告",     "成交公告",     "http://www.ccgp.gov.cn/cggg/zygg/cjgg/index_{page}.htm"),
    "zygg_qtgg":    ("中央-其他公告",     None,           "http://www.ccgp.gov.cn/cggg/zygg/qtgg/index_{page}.htm"),
    "dfgg_gkzb":    ("地方-公开招标公告", "公开招标",     "http://www.ccgp.gov.cn/cggg/dfgg/gkzb/index_{page}.htm"),
    "dfgg_zbgg":    ("地方-中标公告",     "中标公告",     "http://www.ccgp.gov.cn/cggg/dfgg/zbgg/index_{page}.htm"),
    "dfgg_cjgg":    ("地方-成交公告",     "成交公告",     "http://www.ccgp.gov.cn/cggg/dfgg/cjgg/index_{page}.htm"),
    "dfgg_qtgg":    ("地方-其他公告",     None,           "http://www.ccgp.gov.cn/cggg/dfgg/qtgg/index_{page}.htm"),
    "dfgg_jzxcs":   ("地方-竞争性磋商",   "竞争性磋商",   "http://www.ccgp.gov.cn/cggg/dfgg/jzxcs/index_{page}.htm"),
    "dfgg_jzxtpgg": ("地方-竞争性谈判",   "竞争性谈判",   "http://www.ccgp.gov.cn/cggg/dfgg/jzxtpgg/index_{page}.htm"),
    "dfgg_xjgg":    ("地方-询价公告",     "询价公告",     "http://www.ccgp.gov.cn/cggg/dfgg/xjgg/index_{page}.htm"),
    "dfgg_gzgg":    ("地方-更正公告",     "更正公告",     "http://www.ccgp.gov.cn/cggg/dfgg/gzgg/index_{page}.htm"),
}


# =====================================================
# 通用工具
# =====================================================

def _dedup_key(source_code: str, external_id: str, title: str) -> str:
    """和 promote_seed 脚本保持一致：sha1(source + id + title)"""
    raw = f"{source_code}|{external_id}|{title}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _fetch_url(url: str, timeout: float = 15.0, retries: int = 2) -> Optional[str]:
    # ccgp 封了服务器出口 IP（403）：配置 CCGP_PROXY 后仅 ccgp 请求走代理，其余源直连
    proxy = None
    if "ccgp.gov.cn" in url:
        proxy = (getattr(settings, "ccgp_proxy", "") or "").strip() or None
        if proxy and not getattr(_fetch_url, "_proxy_logged", False):
            logger.info(f"[crawl] ccgp 走代理出口: {proxy.split('@')[-1]}")
            _fetch_url._proxy_logged = True
    for attempt in range(retries + 1):
        try:
            kw = dict(timeout=timeout, headers=DEFAULT_HEADERS, follow_redirects=True)
            if proxy:
                kw["proxy"] = proxy
            with httpx.Client(**kw) as client:
                r = client.get(url)
                r.raise_for_status()
                # 先尝试 utf-8，不行用 gbk
                try:
                    return r.content.decode("utf-8")
                except UnicodeDecodeError:
                    return r.content.decode("gbk", errors="ignore")
        except Exception as e:
            logger.warning(f"[crawl] fetch fail attempt={attempt+1} url={url[:80]} err={e}")
            time.sleep(2 * (attempt + 1))
    return None


_DATE_PATTERNS = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d",
    "%Y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M", "%Y/%m/%d",
    "%Y年%m月%d日 %H:%M", "%Y年%m月%d日",
)


def _parse_dt(s) -> Optional[datetime]:
    """详情页日期串（含中文年月日）→ datetime；data_clean.clean_date 格式不够用"""
    if s is None:
        return None
    if isinstance(s, datetime):
        return s
    t = str(s).strip()
    if not t or t.startswith("1900") or t.startswith("0000"):
        return None
    for fmt in _DATE_PATTERNS:
        try:
            return datetime.strptime(t, fmt)
        except ValueError:
            continue
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", t)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _parse_money(s) -> Optional[float]:
    """'￥649.080000万元' / '￥21.000000 万元（人民币）' / '500000' → float"""
    if s is None:
        return None
    t = str(s).replace(",", "")
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*万", t)
    if m:
        return float(m.group(1)) * 10000
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", t)
    return float(m.group(1)) if m else None


# ---- 地区字典（ggzy indexCollect.json，省/市两级国标码）----
_REGION_CACHE: Optional[tuple] = None
REGION_DICT_URL = "http://www.ggzy.gov.cn/data/indexCollect.json"


def _load_region_index():
    """返回 ({省名: 码}, {市名: 码})，进程内缓存；拉取失败返回空表"""
    global _REGION_CACHE
    if _REGION_CACHE is not None:
        return _REGION_CACHE
    prov: Dict[str, str] = {}
    city: Dict[str, str] = {}
    try:
        html = _fetch_url(REGION_DICT_URL, timeout=15, retries=1)
        data = json.loads(html) if html else {}
        for a in (data.get("areaJson") or []):
            if a.get("name") and a.get("id"):
                prov[str(a["name"]).strip()] = str(a["id"])
        for _pc, cities in (data.get("cityJson") or {}).items():
            for c in (cities or []):
                if c.get("name") and c.get("id"):
                    city[str(c["name"]).strip()] = str(c["id"])
    except Exception as e:
        logger.warning(f"[crawl] 地区字典加载失败（本次用不上地区码）: {e}")
    _REGION_CACHE = (prov, city)
    logger.info(f"[crawl] 地区字典: 省={len(prov)} 市={len(city)}")
    return _REGION_CACHE


def _region_code_of(name) -> Optional[str]:
    """'安徽'/'合肥市'/'江苏省' → 6 位国标地区码（省精确 → 市精确 → 前缀兜底）"""
    if not name:
        return None
    n = str(name).strip().replace(" ", "")
    if not n or n in ("省本级", "市本级", "县本级"):
        return None
    prov, city = _load_region_index()
    if not prov and not city:
        return None
    if n in prov:
        return prov[n]
    if n in city:
        return city[n]
    for table in (city, prov):
        for k, v in table.items():
            if k.startswith(n) or n.startswith(k):
                return v
    return None


# =====================================================
# 字段映射（爬虫层 → bid_info INSERT）
# =====================================================

def _map_to_bid_info(
    source_id: int,
    source_code: str,
    raw: Dict[str, Any],
    industries=None,
    conn=None,
) -> Optional[Dict[str, Any]]:
    """
    把爬虫抓到的一条原始数据 → bid_info INSERT 所需字段。
    raw 字段约定（爬虫层统一输出）：
        - external_id:   源站唯一标识
        - title:         公告标题
        - source_url:    原文链接
        - publish_time:  公告发布时间（datetime or ISO str）
        - winner_publish_time / win_date: 中标/成交公示时间（可空）
        - deadline:      报名/投标截止时间（可空）
        - tenderee:      采购人（可空）
        - winner_unit:   中标单位（可空）
        - win_amount:    中标金额（可空，Decimal 或 float）
        - procure_type:  招采类型（可空）
        - region_code:   地区代码（可空）
        - content:       正文 HTML（可空）
        - content_text:  正文纯文本（可空）
    """
    if not raw.get("title"):
        return None

    external_id = str(raw.get("external_id") or raw.get("source_url") or raw["title"][:32])
    dk = _dedup_key(source_code, external_id, raw["title"])

    # ---- 清洗 pipeline ----
    content = raw.get("content") or raw.get("html") or ""
    content_text = raw.get("content_text") or ""
    if not content_text and content:
        content_text = strip_html(content)
    content_text = content_text[:20000] if content_text else ""

    publish_time = clean_date(raw.get("publish_time"))
    # 中标/成交公示时间（v2 爬虫补充，用于中标时间筛选）
    winner_publish_time = clean_date(raw.get("winner_publish_time") or raw.get("win_date"))
    deadline = clean_date(raw.get("deadline"))

    # 分类推断
    title = raw["title"]
    notice_type_id = raw.get("notice_type_id")
    if not notice_type_id and conn is not None:
        notice_type_id = infer_notice_type_id(title, conn, content_text)

    procure_type = raw.get("procure_type") or infer_procure_type(title, content_text)
    customer_group = raw.get("customer_group") or infer_customer_group(
        raw.get("tenderee") or raw.get("buyer_name"), title
    )

    industry_id = raw.get("industry_id")
    if not industry_id and industries is not None:
        industry_id = infer_industry_id(title, content_text, industries)

    win_amount = raw.get("win_amount")
    if win_amount is not None:
        try:
            win_amount = float(win_amount)
        except Exception:
            win_amount = None

    return {
        "title": title[:500],
        "project_code": raw.get("project_code"),
        "tenderee": raw.get("tenderee") or raw.get("buyer_name"),
        "agency": raw.get("agency"),
        "region_code": raw.get("region_code"),
        "publish_time": publish_time,
        "winner_publish_time": winner_publish_time,
        "deadline": deadline,
        "budget": raw.get("budget"),
        "content": content[:50000] if content else None,
        "content_text": content_text or None,
        "source_id": source_id,
        "source_url": raw.get("source_url"),
        "dedup_key": dk,
        # v0.2 新增字段（清洗后更准）
        "winner_unit": raw.get("winner_unit"),
        "win_amount": win_amount,
        "procure_type": procure_type,
        "customer_group": customer_group,
        "industry_id": industry_id,
        "notice_type_id": notice_type_id,
        "winner_unit_type": raw.get("winner_unit_type"),
        "status": 1,
    }


# =====================================================
# 实际抓取（httpx 同步实现，供 Celery worker 调用）
# =====================================================

def crawl_ccgp(page: int = 1, category: str = "zygg_gkzb") -> List[Dict[str, Any]]:
    """
    抓 ccgp 静态列表页（替代已废弃的 bxsearch 搜索接口）。
    category 见 CCGP_CATEGORIES；./xxx.htm 相对链接以此页为 base 展开。
    """
    cat = CCGP_CATEGORIES.get(category)
    if not cat:
        logger.error(f"[crawl] ccgp 未知分类: {category}")
        return []
    cat_name, procure_type, tpl = cat
    results: List[Dict[str, Any]] = []
    url = tpl.format(page=page)
    base_dir = url.rsplit("/", 1)[0] + "/"
    html = _fetch_url(url)
    if not html:
        return results

    try:
        soup = BeautifulSoup(html, "html.parser")
        # 实测结构：ul.c_list_bid > li（附带 list-con 等历史选择器兜底）
        items = soup.select("ul.c_list_bid li") or soup.select("ul.list-con li") or []
        for it in items:
            a = it.find("a", href=True)
            if not a:
                continue
            title = (a.get("title") or a.get_text(strip=True) or "")[:200]
            link = a.get("href", "")
            if not title or not link:
                continue
            if link.startswith("./"):
                link = base_dir + link[2:]
            elif link.startswith("/"):
                link = "http://www.ccgp.gov.cn" + link
            elif not link.startswith("http"):
                continue

            # 实测 li 文本形态：
            #   标题 发布时间：2026-11-24 18:30 地域：江苏 采购人：南京明德软件有限公司
            txt = it.get_text(" ", strip=True)
            m_t = re.search(r"发布时间[：:]\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:[ ]+\d{1,2}:\d{2})?)", txt)
            pub_time = _parse_dt(m_t.group(1)) if m_t else None
            m_r = re.search(r"地域[：:]\s*([^\s|]+)", txt)
            region = m_r.group(1) if m_r else None
            m_b = re.search(r"采购人[：:]\s*([^\s|]+)", txt)
            buyer = m_b.group(1) if m_b else None

            raw = {
                "external_id": link.rsplit("/", 1)[-1].replace(".htm", "").replace(".html", ""),
                "title": title,
                "source_url": link,
                "publish_time": pub_time,
                "procure_type": procure_type,
            }
            if region:
                code = _region_code_of(region)
                if code:
                    raw["region_code"] = code
            if buyer:
                raw["tenderee"] = buyer
            # 中标/成交公告：发布时间即中标公示时间（v2 字段）
            if category.endswith("zbgg") or category.endswith("cjgg"):
                if pub_time:
                    raw["win_date"] = pub_time
            results.append(raw)
    except Exception as e:
        logger.exception(f"[crawl] ccgp parse error cat={category}: {e}")

    return results


# ccgp 详情页「公告概要」表 → 原始字段
_CCGP_DETAIL_MAP = {
    "采购单位": "tenderee",
    "采购人名称": "tenderee",
    "代理机构名称": "agency",
    "预算金额": "budget",
    "项目预算金额": "budget",
    "采购项目编号": "project_code",
    "项目编号": "project_code",
}


def _fill_ccgp_detail(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    抓 ccgp 详情页：正文（div.main，公告概要表 + 公告信息）
    + 结构化字段（预算/开标时间/代理机构/中标供应商/中标金额/行政区划）。
    失败返回原 raw（正文留空，等下一轮补）。
    """
    url = raw.get("source_url")
    if not url:
        return raw
    html = _fetch_url(url, timeout=20, retries=1)
    if not html:
        return raw
    try:
        soup = BeautifulSoup(html, "html.parser")
        main = soup.select_one("div.main") or soup.select_one("div.main_container")
        if not main:
            return raw
        raw["content"] = str(main)
        raw["content_text"] = main.get_text("\n", strip=True)

        # 概要表 key/value
        kv: Dict[str, str] = {}
        for tr in main.find_all("tr"):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if len(cells) >= 2 and cells[0] and len(cells[0]) <= 30 and cells[1]:
                kv.setdefault(cells[0], cells[1])

        for k, field in _CCGP_DETAIL_MAP.items():
            v = kv.get(k)
            if v and not raw.get(field):
                raw[field] = v

        # 金额（win_amount 为数值列）
        amount = kv.get("总成交金额") or kv.get("中标金额") or kv.get("成交金额")
        if amount and raw.get("win_amount") is None:
            parsed = _parse_money(amount)
            if parsed is not None:
                raw["win_amount"] = parsed

        # 截止时间优先取开标时间（报名截止含时间段，解析不出）
        if not raw.get("deadline"):
            dl = kv.get("开标时间") or kv.get("提交投标文件截止时间") or kv.get("投标截止时间")
            d = _parse_dt(dl)
            if d:
                raw["deadline"] = d

        # 中标/成交供应商：表头含「供应商名称」的表，取序号 1 那行
        rows = main.find_all("tr")
        for i, tr in enumerate(rows):
            cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
            if any("供应商名称" in c for c in cells):
                for nxt in rows[i + 1:i + 4]:
                    c2 = [td.get_text(" ", strip=True) for td in nxt.find_all(["td", "th"])]
                    if len(c2) >= 2 and c2[0] and len(c2[0]) <= 4 and re.fullmatch(r"\d+", c2[0]):
                        raw["winner_unit"] = raw.get("winner_unit") or c2[1]
                        break
                break

        # 行政区域（城市级）比列表的「地域」（省级）更精确
        area = kv.get("行政区域")
        if area:
            code = _region_code_of(area)
            if code:
                raw["region_code"] = code
    except Exception as e:
        logger.warning(f"[crawl] ccgp 详情解析失败 {url}: {e}")
    return raw


def crawl_ggzy(page: int = 1) -> List[Dict[str, Any]]:
    """
    抓 ggzy.gov.cn：首页「交易公告 / 成交公示」区块（server-rendered）。
    旧列表 URL 与 getTradList 接口均已失效（2026-11 实测）。
    首页锚文本被截断 → 每条必须进详情页取完整标题（失败则丢弃该条）。
    首页无分页：page > 1 返回空。
    """
    if page > 1:
        return []
    results: List[Dict[str, Any]] = []
    html = _fetch_url("http://www.ggzy.gov.cn/", timeout=20)
    if not html:
        return results

    try:
        soup = BeautifulSoup(html, "html.parser")
        # 详情链接形如 /information/deal/html/a/{地区码}/{分类}/{yyyyMMdd}/{hash}.html
        seen = set()
        seen_titles = set()   # 首页可能出现同一公告的多条镜像，按标题去重
        for a in soup.find_all("a", href=True):
            href = a["href"]
            m = re.match(r"/information/deal/html/a/(\d{6})/(\d{4})/(\d{8})/([^/]+)\.html?$", href)
            if not m or href in seen:
                continue
            seen.add(href)
            region_code, _cls, yyyymmdd, hash_id = m.groups()
            # 地区码前缀校验（首页出现过 0067 这类非地区码）
            if region_code[:2] not in ("11", "12", "13", "14", "15", "21", "22", "23",
                                       "31", "32", "33", "34", "35", "36", "37", "41",
                                       "42", "43", "44", "45", "46", "50", "51", "52",
                                       "53", "54", "61", "62", "63", "64", "65"):
                region_code = None
            try:
                pub_time = datetime(int(yyyymmdd[:4]), int(yyyymmdd[4:6]), int(yyyymmdd[6:]))
            except ValueError:
                pub_time = None

            raw = _ggzy_detail("http://www.ggzy.gov.cn" + href, hash_id)
            if not raw:
                continue  # 详情失败 → 标题不完整，宁缺毋滥
            if raw["title"] in seen_titles:
                continue
            seen_titles.add(raw["title"])
            raw["source_url"] = "http://www.ggzy.gov.cn" + href
            raw["publish_time"] = raw.get("publish_time") or pub_time
            if region_code:
                raw["region_code"] = region_code
            results.append(raw)
            time.sleep(DETAIL_SLEEP)
    except Exception as e:
        logger.exception(f"[crawl] ggzy parse error: {e}")

    return results


_GGZY_TITLE_SUFFIX = re.compile(r"[_|].*?(国家|全国)公共资源交易平台\s*$")


def _ggzy_source_url(bsoup) -> Optional[str]:
    """b/ 页的「原文链接地址」——真实正文在第三方源站（如浙江省公共资源交易网）"""
    a = bsoup.find("a", href=True)
    for x in bsoup.find_all("a", href=True):
        href = (x.get("href") or "").strip()
        if not href.startswith("http"):
            continue
        if "ggzy.gov.cn" in href:          # 站内链接不算原文
            continue
        if "原文" in x.get_text() or a is None:
            return href
    return None


# 源站常见的正文容器（政务/交易类站点约定），按优先级依次尝试
_GGZY_CONTENT_SELECTORS = (
    "div.ewb-trade-mid", "div.TRS_Editor", "div#zoom", "div#content",
    "div.detail_content", "div.article-content", "div.news-content",
    "div.main-content", "div.content", "div.article",
)


def _ggzy_pick_content(soup, min_len: int = 200):
    """从源站页面挑正文容器：先按已知选择器，再退回最长文本块"""
    for sel in _GGZY_CONTENT_SELECTORS:
        el = soup.select_one(sel)
        if el and len(el.get_text(strip=True)) >= min_len:
            return el
    # 退路：文本最长的 div/article（排除明显是整页外壳的）
    best, best_n = None, 0
    for el in soup.find_all(["div", "article", "section"]):
        cls = " ".join(el.get("class") or []).lower()
        if any(k in cls for k in ("header", "footer", "nav", "menu", "sidebar")):
            continue
        n = len(el.get_text(strip=True))
        if n > best_n:
            best, best_n = el, n
    if best and best_n >= min_len:
        return best
    return None


def _ggzy_detail(url: str, hash_id: str) -> Optional[Dict[str, Any]]:
    """
    ggzy 详情页（聚合壳）：完整标题在 div.fully h4，另带招标项目编号/信息来源。
    2026-11-26 修复：a/ 页只是聚合壳（3KB，无正文），真实正文（表格：招标人/报价/
    开标时间等）在页面 JS 的 firstLastUrl 指向的 b/ 页 —— 必须再抓一层才能拿到。
    返回 raw dict，失败返回 None。
    """
    html = _fetch_url(url, timeout=20, retries=1)
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
        h4 = soup.select_one("div.fully h4")
        title = h4.get_text(strip=True) if h4 else ""
        if not title and soup.title:
            title = _GGZY_TITLE_SUFFIX.sub("", soup.title.get_text(strip=True)).strip("_| ")
        title = title[:200]
        if not title:
            return None

        raw: Dict[str, Any] = {
            "external_id": hash_id,
            "title": title,
        }

        # 招标项目编号 / 项目编号（壳页有）
        text = soup.get_text(" ", strip=True)
        m = re.search(r"(?:招标|采购)?项目编号[：:]\s*([A-Za-z0-9\-]+)", text)
        if m:
            raw["project_code"] = m.group(1)

        # 真实正文：firstLastUrl → b/ 页（表格内容在这里）
        body = None
        m = re.search(r"var\s+firstLastUrl\s*=\s*'([^']+)'", html)
        if m:
            body_html = _fetch_url("https://www.ggzy.gov.cn" + m.group(1),
                                   timeout=20, retries=1)
            if body_html:
                bsoup = BeautifulSoup(body_html, "html.parser")
                # 发布时间（b 页 p_o 头部：发布时间：2026-11-25 15:50）
                mp = re.search(r"发布时间[：:]\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2})",
                               bsoup.get_text(" ", strip=True))
                if mp:
                    try:
                        raw["publish_time"] = datetime.strptime(
                            mp.group(1), "%Y-%m-%d %H:%M")
                    except ValueError:
                        pass
                body = (bsoup.select_one("div#mycontent")
                        or bsoup.select_one("div.detail_content")
                        or bsoup.select_one("div.detail"))

                # b/ 页仍是占位（#mycontent 只有「公示内容」几个字）→ 三跳到原文链接地址
                if body is None or len(body.get_text(strip=True)) < 50:
                    src_url = _ggzy_source_url(bsoup)
                    if src_url:
                        src_html = _fetch_url(src_url, timeout=25, retries=1)
                        if src_html:
                            deep = _ggzy_pick_content(
                                BeautifulSoup(src_html, "html.parser"))
                            if deep is not None:
                                body = deep
                                raw["source_url"] = src_url

        # 兜底：b/ 页抓取失败 → 用壳页正文（信息薄但至少有标题编号）
        if body is None:
            body = soup.select_one("div.fully") or soup.select_one("div.location")
        if body:
            raw["content"] = str(body)
            raw["content_text"] = body.get_text("\n", strip=True)
        return raw
    except Exception as e:
        logger.warning(f"[crawl] ggzy 详情解析失败 {url}: {e}")
        return None


# =====================================================
# 入库 & 主入口
# =====================================================

def _get_or_create_source(db, code: str, name: str, source_type: int = 1) -> int:
    src = db.query(BidSource).filter(BidSource.code == code).first()
    if src:
        return src.id
    src = BidSource(code=code, name=name, source_type=source_type, status=1)
    db.add(src)
    db.commit()
    db.refresh(src)
    return src.id


def crawl_and_save(code: str, pages: int = 1, max_detail: int = MAX_DETAIL_PER_RUN) -> Dict[str, Any]:
    """
    采集一个数据源，写 bid_info（dedup_key 冲突则跳过）。
    调优点：
      - 预载全表 dedup_key 做内存去重（原来每条查一次库）
      - ccgp 新条目抓详情补正文/预算/开标时间/中标供应商（限 max_detail 条/轮）
      - 已存在但缺正文的条目自动补正文（存量补全）
    返回统计结果。
    """
    db = SessionLocal()
    conn = None
    try:
        if code == "ggzy":
            source_name = SOURCE_GGZY["name"]
        elif code == "ccgp":
            source_name = SOURCE_CCGP["name"]
        else:
            logger.error(f"[crawl] unknown source code: {code}")
            return {"source": code, "status": "error", "message": "unknown source"}

        source_id = _get_or_create_source(db, code, source_name)
        # data_clean 的 load_industries / infer_notice_type_id 用的是 cursor()，要 DBAPI 连接
        conn = db.get_bind().raw_connection()
        industries = load_industries(conn)
        # 公告类型 name->id（AI 分类结果落库用，按连接缓存）
        notice_type_map = _load_notice_type_map(conn)

        # 预载去重键 → {dedup_key: content_text}
        existing: Dict[str, Optional[str]] = dict(
            db.query(BidInfo.dedup_key, BidInfo.content_text).all()
        )

        stats = {"fetched": 0, "saved": 0, "updated": 0, "skipped": 0,
                 "details": 0, "ai": 0, "pending": 0}

        def handle(raw: Dict[str, Any]) -> None:
            if not raw.get("title"):
                return
            stats["fetched"] += 1
            ext = str(raw.get("external_id") or raw.get("source_url") or raw["title"][:32])
            dk = _dedup_key(code, ext, raw["title"])

            if dk in existing:
                # 已存在：正文为空的补正文（受单轮预算限制）
                if code == "ccgp" and not existing[dk] and stats["details"] < max_detail:
                    row = db.query(BidInfo).filter(BidInfo.dedup_key == dk).first()
                    if row and not row.content_text:
                        stats["details"] += 1
                        det = _fill_ccgp_detail(raw)
                        if det.get("content_text"):
                            row.content = (det.get("content") or "")[:50000] or None
                            row.content_text = (det.get("content_text") or "")[:20000] or None
                            for f in ("deadline", "budget", "agency", "project_code", "winner_unit"):
                                if getattr(row, f, None) in (None, "") and det.get(f) is not None:
                                    setattr(row, f, det[f])
                            wa = det.get("win_amount")
                            if wa is not None and row.win_amount is None:
                                row.win_amount = wa
                            # 补正文后立即提取（同 data_clean 公共函数，只补空字段）
                            if row.content_text:
                                try:
                                    from app.services.data_clean import extract_fields_from_text
                                    extra = extract_fields_from_text(
                                        row.title or "", row.content_text, conn=conn.cursor(),
                                        current={"deadline": row.deadline,
                                                 "project_code": row.project_code,
                                                 "region_code": row.region_code,
                                                 "tenderee": row.tenderee,
                                                 "budget": row.budget,
                                                 "winner_unit": row.winner_unit,
                                                 "win_amount": row.win_amount})
                                    for k, v in extra.items():
                                        setattr(row, k, v)
                                except Exception:
                                    logger.warning("补正文后提取失败 id=%s", row.id, exc_info=True)

                                # 源站专用 extractor 补漏（同入库路径）
                                try:
                                    from app.services.source_specs import fill_gaps_via_spec
                                    from app.services.data_clean import is_result_notice
                                    spec_fields = fill_gaps_via_spec(
                                        code,
                                        row.content or row.content_text or "",
                                        {"tenderee": row.tenderee,
                                         "agency": getattr(row, "agency", None),
                                         "budget": row.budget,
                                         "deadline": row.deadline,
                                         "winner_unit": row.winner_unit,
                                         "win_amount": row.win_amount,
                                         "project_code": row.project_code,
                                         "region_code": row.region_code},
                                        allow_winner=is_result_notice(
                                            row.title or "", row.content_text or ""))
                                    for k, v in spec_fields.items():
                                        setattr(row, k, v)
                                except Exception:
                                    logger.warning("补正文后 SourceSpec 失败 id=%s", row.id, exc_info=True)
                            stats["updated"] += 1
                stats["skipped"] += 1
                return

            if code == "ccgp" and stats["details"] < max_detail:
                stats["details"] += 1
                raw = _fill_ccgp_detail(raw)

            mapped = _map_to_bid_info(source_id, code, raw, industries=industries, conn=conn)
            if not mapped:
                return
            if mapped["dedup_key"] in existing:
                stats["skipped"] += 1
                return

            # 入库即提取（2026-11-26）：正文中的截止时间/项目编号/单位/金额/地区
            # 提取函数与补抓脚本共用 data_clean 同一实现；只补空字段，不覆盖已有值
            if mapped.get("content_text"):
                try:
                    from app.services.data_clean import extract_fields_from_text
                    extra = extract_fields_from_text(
                        mapped.get("title") or "", mapped["content_text"],
                        conn=conn.cursor(),
                        current={"deadline": mapped.get("deadline"),
                                 "project_code": mapped.get("project_code"),
                                 "region_code": mapped.get("region_code"),
                                 "tenderee": mapped.get("tenderee"),
                                 "budget": mapped.get("budget"),
                                 "winner_unit": mapped.get("winner_unit"),
                                 "win_amount": mapped.get("win_amount")})
                    mapped.update(extra)
                except Exception:
                    logger.warning("入库即提取失败 title=%s", str(mapped.get("title"))[:40], exc_info=True)

            # === 2026-11-27: 源站专用 extractor 补漏（source_specs.py） ===
            # 走专用 parser 扫 content HTML，只填通用正则漏掉的空字段
            # 优先级：源站专用 > 通用规则 > AI 兜底
            try:
                from app.services.source_specs import fill_gaps_via_spec
                from app.services.data_clean import is_result_notice
                current_for_spec = {
                    "tenderee": mapped.get("tenderee"),
                    "agency": mapped.get("agency"),
                    "budget": mapped.get("budget"),
                    "deadline": mapped.get("deadline"),
                    "winner_unit": mapped.get("winner_unit"),
                    "win_amount": mapped.get("win_amount"),
                    "project_code": mapped.get("project_code"),
                    "region_code": mapped.get("region_code"),
                }
                spec_fields = fill_gaps_via_spec(
                    code,
                    mapped.get("content") or mapped.get("content_text") or "",
                    current_for_spec,
                    allow_winner=is_result_notice(
                        mapped.get("title") or "", mapped.get("content_text") or ""))
                if spec_fields:
                    mapped.update(spec_fields)
                    logger.info("[crawl] SourceSpec(%s) 补到字段: %s", code, list(spec_fields.keys()))
            except Exception:
                logger.warning("SourceSpec 专用提取失败 title=%s",
                               str(mapped.get("title"))[:40], exc_info=True)

            # 双线第二道（2026-11-26）：规则提取后关键字段仍不满 → AI 兜底提取，
            # 同一次调用顺带让 AI 分类（行业/客群/公告类型，方案 A 不新增触发）。
            #   - 总开关关闭（后台待审核页）→ 不调 AI，统一转人工审核
            #   - 调用失败（超时/HTTP 错误/解析失败/异常）→ status=0 进 /bid/pending 待审核
            #   - AI 返回空 = 确认没有 → 照常放行；分类值须命中字典清单才覆盖规则结果
            try:
                from app.services.ai_extract import missing_fields, ai_extract_missing
                from app.services import ai_setting_service as ai_svc
                miss = missing_fields(mapped)
                if miss and not bool(ai_svc.get("param.ai_extract_enabled", True)):
                    mapped["status"] = 0
                    stats["pending"] += 1
                    logger.info("[crawl] AI 提取开关关闭→转人工 title=%s 缺=%s",
                                str(mapped.get("title"))[:40], miss)
                    miss = []
                if miss:
                    ai_vals, ai_ok = ai_extract_missing(
                        mapped.get("title") or "",
                        mapped.get("content_text") or "", miss,
                        class_options={
                            "industry": [n for _, n, _ in industries],
                            "notice_type": list(notice_type_map),
                        })
                    if not ai_ok:
                        mapped["status"] = 0
                        stats["pending"] += 1
                        logger.info("[crawl] AI 提取失败→待审核 title=%s",
                                    str(mapped.get("title"))[:40])
                    else:
                        mapped["ai_processed"] = 1
                        for f in ("tenderee", "winner_unit", "win_amount"):
                            if ai_vals.get(f) is not None:
                                mapped[f] = ai_vals[f]
                        ind_name = ai_vals.get("industry")
                        if ind_name:
                            iid = next((i for i, n, _ in industries
                                        if n == ind_name), None)
                            if iid is not None:
                                mapped["industry_id"] = iid
                        nt_name = ai_vals.get("notice_type")
                        if nt_name:
                            nid = notice_type_map.get(nt_name)
                            if nid is not None:
                                mapped["notice_type_id"] = nid
                        if ai_vals.get("customer_group"):
                            mapped["customer_group"] = ai_vals["customer_group"]
                        if ai_vals:
                            stats["ai"] += 1
            except Exception:
                # AI 环节异常同样视为失败 → 待审核人工兜底，不静默放行
                mapped["status"] = 0
                stats["pending"] += 1
                logger.warning("AI 兜底异常→待审核 title=%s",
                               str(mapped.get("title"))[:40], exc_info=True)

            db.add(BidInfo(**mapped))
            existing[mapped["dedup_key"]] = mapped.get("content_text")
            stats["saved"] += 1

        for page in range(1, pages + 1):
            if code == "ggzy":
                # 首页无分页，只抓一轮
                if page == 1:
                    for raw in crawl_ggzy(page=1):
                        handle(raw)
                break
            # ccgp：12 个分类目录逐个抓
            for cat in CCGP_CATEGORIES:
                for raw in crawl_ccgp(page=page, category=cat):
                    handle(raw)
                db.commit()          # 按分类提交，避免长事务
                time.sleep(LIST_SLEEP)

        db.commit()

        # 记录采集时间，供 crawl_all_registered_sources 按 interval_minutes 降频跳过
        try:
            db.query(BidSource).filter(BidSource.id == source_id).update(
                {"last_crawl_at": datetime.now()})
            db.commit()
        except Exception:
            logger.warning("[crawl] 更新 last_crawl_at 失败", exc_info=True)

        # 清洗+提取后的收尾：为本轮新入库标讯增量生成语义向量（供 AI 检索混合召回）
        if stats["saved"] > 0:
            try:
                from app.services.embedding_service import build_embeddings
                _n = build_embeddings(limit=0)
                logger.info(f"[crawl] {code}: 语义向量增量 {_n} 条")
            except Exception:
                logger.warning(f"[crawl] {code}: 语义向量增量生成失败（不影响采集）", exc_info=True)

        logger.info(
            f"[crawl] {code}: fetched={stats['fetched']} saved={stats['saved']} "
            f"updated={stats['updated']} skipped={stats['skipped']} "
            f"details={stats['details']} ai={stats['ai']} "
            f"pending={stats['pending']}"
        )
        return {
            "source": code,
            "status": "ok",
            "fetched": stats["fetched"],
            "saved": stats["saved"],
            "updated": stats["updated"],
            "skipped": stats["skipped"],
            "details": stats["details"],
            "ai": stats["ai"],
            "pending": stats["pending"],
        }
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
        db.close()


def _due_to_crawl(code: str) -> bool:
    """采集放行判断：
    - bid_source.status=0 → 停用（如 ccgp 被封禁期间），直接跳过
    - 按 last_crawl_at + interval_minutes 降频，未到点跳过
    - 无记录或查询失败一律放行（首次抓取、异常不阻断）"""
    db = SessionLocal()
    try:
        src = db.query(BidSource).filter(BidSource.code == code).first()
        if not src:
            return True
        if not src.status:
            logger.info(f"[crawl] source={code} 已停用（bid_source.status=0），跳过")
            return False
        if not src.last_crawl_at:
            return True
        due = datetime.now() - src.last_crawl_at >= timedelta(
            minutes=src.interval_minutes or 60)
        if not due:
            logger.info(f"[crawl] source={code} 未到采集间隔"
                        f"（{src.interval_minutes} 分钟），跳过")
        return due
    except Exception:
        return True
    finally:
        db.close()


def crawl_all_registered_sources(pages_per_source: int = 1) -> List[Dict[str, Any]]:
    """采集所有已注册的爬虫源（code in {ggzy, ccgp}）；
    status=0 停用、按 bid_source.interval_minutes 降频
    （ccgp 180 分钟、ggzy 120 分钟一次）"""
    results = []
    for code in ("ggzy", "ccgp"):
        try:
            if not _due_to_crawl(code):
                results.append({"source": code, "status": "skipped",
                                "message": "disabled or interval not due"})
                continue
            results.append(crawl_and_save(code, pages=pages_per_source))
        except Exception as e:
            logger.exception(f"[crawl] source={code} fatal: {e}")
            results.append({"source": code, "status": "error", "message": str(e)})
    return results
