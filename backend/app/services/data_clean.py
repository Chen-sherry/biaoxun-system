# -*- coding: utf-8 -*-
"""
数据清洗 + 分类推断服务

爬虫入库 → 清洗 pipeline → 正式落库
种子数据补全同样走这条 pipeline

核心步骤（按顺序）：
1. HTML 去标签 → content_text（content 保留原文）
2. 日期清洗：1900-01-01 / 空串 → NULL
3. 公告类型推断 notice_type_id（基于标题关键词 → dict_notice_type）
4. 招采类型推断 procure_type（基于标题关键词）
5. 客群推断 customer_group（基于 tenderee 关键词）
6. 行业推断 industry_id（基于标题+内容关键词 → dict_industry）
"""
from __future__ import annotations

import os
import re
import sys
import logging
from datetime import datetime, date
from typing import Optional

import pymysql

logger = logging.getLogger(__name__)

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # backend/
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)
try:
    from app.config import settings as _settings
    DB_CONFIG = dict(host=_settings.db_host, port=int(_settings.db_port), user=_settings.db_user, password=_settings.db_password, database=_settings.db_name, charset=_settings.db_charset)
except Exception:
    DB_CONFIG = dict(host="127.0.0.1", port=3306, user="root", password="12345", database="bid_info", charset="utf8mb4")


# =====================================================
# Step 1: HTML → 纯文本
# =====================================================

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HTML_ENTITY_RE = re.compile(r"&(nbsp|amp|lt|gt|quot|apos|#\d+|#x[0-9a-fA-F]+);")
_WS_RE = re.compile(r"\s+")

def strip_html(raw: Optional[str]) -> str:
    """HTML 去标签 → 干净纯文本"""
    if not raw:
        return ""
    text = _HTML_TAG_RE.sub("", raw)
    text = _HTML_ENTITY_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text


# =====================================================
# Step 2: 日期清洗
# =====================================================

_BAD_DATES = {"1900-01-01", "0000-00-00", "", "null", "None"}

def clean_date(val) -> Optional[datetime]:
    """1900-01-01 / 空串 / 异常格式 → None"""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.year < 1990:
            return None
        return val
    if isinstance(val, date):
        if val.year < 1990:
            return None
        return datetime(val.year, val.month, val.day)
    s = str(val).strip()
    if not s or s in _BAD_DATES or s.startswith("1900") or s.startswith("0000"):
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


# =====================================================
# Step 3: 公告类型推断
# =====================================================

# 按优先级排序：先匹配到的关键词生效（具体类型在前，通用类型在后）
# 注意：type_name 必须与 dict_notice_type.name 完全一致，否则查不到 id
NOTICE_TYPE_RULES = [
    # (关键词列表, dict_notice_type.name)
    # —— 更正 / 澄清类 ——
    (["更正公告", "变更公告", "修改公告", "补充公告", "更正通知", "变更"], "更正公告"),
    (["答疑", "澄清公告", "澄清通知", "补充答疑", "澄清"], "答疑澄清"),
    # —— 失败 / 终止类 ——
    (["废标", "流标", "作废", "失败公告", "无效投标", "无效标"], "流标公告"),
    (["终止公告", "中止公告", "项目终止", "终止采购", "终止"], "终止公告"),
    # —— 资格 / 单一来源 ——
    (["资格预审", "预审公告", "资格审查公告"], "资格预审公告"),
    (["单一来源"], "单一来源公示"),
    # —— 结果类（中标/成交优先于通用「结果」）——
    (["中标公示", "中标结果", "中标通知书", "中标公告", "中标候选人", "中标", "招标结果"], "中标公告"),
    (["成交公告", "成交结果", "成交公示", "成交通知", "中选结果", "中选公告", "中选候选人", "中选", "结果公示", "结果公告"], "成交公告"),
    # —— 采购方式类 ——
    (["竞争性磋商", "磋商公告", "磋商"], "竞争性磋商公告"),
    (["竞争性谈判", "谈判公告", "谈判采购"], "竞争性谈判公告"),
    (["询价", "询价文件"], "询价公告"),
    (["邀请招标", "邀请书", "邀请公告"], "邀请招标"),
    # —— 计划 / 合同类 ——
    (["采购意向", "意向公开", "采购计划", "采购需求"], "采购意向"),
    (["合同公告", "政府采购合同", "合同公示"], "合同公告"),
    # —— 通用兜底 ——
    (["公开招标", "招标公告", "招标"], "招标公告"),
    (["采购公告", "采购项目公告", "询比", "比选", "征集", "招商", "采购"], "采购公告"),
]

# 标题与正文都匹配不上时的兜底类型：保证每条标讯都有公告类型标签
NOTICE_TYPE_FALLBACK = "其他"


def _load_notice_type_map(conn) -> dict:
    """dict_notice_type 的 name -> id 映射，按连接缓存（避免逐条查库）

    兼容 pymysql 普通 Cursor（tuple 输出）和 DictCursor（dict-like 输出）。
    """
    cached = getattr(conn, "_notice_type_map", None)
    if isinstance(cached, dict) and cached:
        return cached
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM dict_notice_type")
        rows = cur.fetchall()
        type_map = {}
        for row in rows:
            if hasattr(row, "keys") and "id" in row:
                nid, name = row["id"], row["name"]
            else:
                nid, name = row[0], row[1]
            type_map[name] = nid
    finally:
        cur.close()
    try:
        conn._notice_type_map = type_map
    except Exception:
        pass
    return type_map


def match_notice_type_name(title: str = "", content_text: str = "") -> str:
    """按关键词匹配公告类型名；标题与正文都匹配不上时返回兜底类型「其他」"""
    for text in (title or "", (content_text or "")[:300]):
        if not text:
            continue
        for keywords, type_name in NOTICE_TYPE_RULES:
            for kw in keywords:
                if kw in text:
                    return type_name
    return NOTICE_TYPE_FALLBACK


def infer_notice_type_id(title: str, conn, content_text: str = "") -> Optional[int]:
    """推断 dict_notice_type.id，保证每条标讯都有标签（兜底「其他」）"""
    type_map = _load_notice_type_map(conn)
    type_name = match_notice_type_name(title, content_text)
    type_id = type_map.get(type_name)
    if type_id is None:
        logger.warning("dict_notice_type 缺少类型「%s」，请补充字典数据", type_name)
        type_id = type_map.get(NOTICE_TYPE_FALLBACK) or next(iter(type_map.values()), None)
    return type_id


# =====================================================
# Step 4: 招采类型推断
# =====================================================

PROCURE_TYPE_RULES = [
    (["公开招标"], "公开招标"),
    (["邀请招标"], "邀请招标"),
    (["竞争性谈判"], "竞争性谈判"),
    (["竞争性磋商"], "竞争性磋商"),
    (["询价"], "询价"),
    (["单一来源"], "单一来源"),
    (["框架协议"], "框架协议"),
    (["集中采购"], "集中采购"),
    (["电子反拍"], "电子反拍"),
    (["网上超市"], "网上超市"),
    (["直购", "直接采购"], "直接采购"),
    (["定向", "委托"], "定向委托"),
]

def infer_procure_type(title: str, content_text: str = "") -> Optional[str]:
    """推断 proc_type：先按标题匹配，再按正文全文匹配（原先只看正文前 200 字，
    方式词出现在正文深处的补不到；调用方均只在字段为空时才调用）"""
    if not title:
        return None
    for blob in (title, content_text or ""):
        if not blob:
            continue
        for keywords, name in PROCURE_TYPE_RULES:
            for kw in keywords:
                if kw in blob:
                    return name
    return None


# =====================================================
# Step 5: 客群推断
# =====================================================

GOV_KEYWORDS = ["人民政府", "人民医院", "人民法院", "检察院", "公安局", "派出所",
                "财政局", "税务局", "教育局", "文化局", "体育局", "卫计局",
                "农业农村局", "自然资源", "生态环境", "交通运输", "住建局",
                "民政", "人社", "医保", "公积金", "镇政府", "乡政府", "街道办",
                "人大", "政协", "委员会", "中共", "党委",
                # 事业单位 / 教育卫生科研
                "大学", "学院", "学校", "中学", "小学", "幼儿园", "校区",
                "医院", "卫生院", "疾控", "妇幼", "中医院", "卫生服务中心",
                "研究院", "研究所", "设计院", "科学院", "实验室",
                "图书馆", "博物馆", "文化馆", "体育中心", "档案馆",
                "指挥部", "管理中心", "服务站", "执法", "监督", "管理局",
                "基金会", "协会", "联合会", "慈善", "红十字"]

SOE_KEYWORDS = ["集团", "有限责任", "股份有限", "国有", "央企", "国企",
                "银行", "保险", "证券", "电信", "移动", "联通", "国家电网",
                "中石油", "中石化", "中粮", "中化", "中铁", "中建", "中交",
                "邮政", "烟草", "盐业", "黄金", "中车", "北车", "南车"]

# 兜底客群（关键词都匹配不上时使用；必须与前端下拉选项「政务/国企/民企」一致，否则筛不到）
CUSTOMER_GROUP_FALLBACK = "政务"

def infer_customer_group(tenderee: str, title: str = "") -> str:
    """政务 / 国企 / 民企；都不命中时兜底「政务」，保证每条标讯都有客群"""
    blob = (tenderee or "") + " " + (title or "")
    if any(kw in blob for kw in GOV_KEYWORDS):
        return "政务"
    if any(kw in blob for kw in SOE_KEYWORDS):
        return "国企"
    # 含有 "公司"、"企业" → 默认民企
    if "公司" in blob or "企业" in blob or "厂" in blob or "工作室" in blob:
        return "民企"
    return CUSTOMER_GROUP_FALLBACK


# =====================================================
# Step 6: 行业推断
# =====================================================

# 兜底行业（全部关键词都不命中时使用，与 dict_industry.name 对应）
INDUSTRY_FALLBACK = "其他行业"


# 基于 dict_industry 现有数据，先查有哪些行业
def load_industries(conn) -> list[tuple[int, str, list[str]]]:
    """返回 [(id, name, 关键词列表), ...]

    兼容普通 Cursor（tuple）和 DictCursor（dict）。
    """
    def _norm(row, ncols=3):
        if hasattr(row, "keys") and "id" in row:
            if ncols >= 3 and "keywords" in row:
                return row["id"], row["name"], row.get("keywords")
            return row["id"], row["name"], None
        return row

    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name, keywords FROM dict_industry WHERE status=1")
        rows = cur.fetchall()
        out = []
        for r in rows:
            rid, name, kw = _norm(r, 3)
            out.append((rid, name, (kw or "").split(",") if kw else [name]))
        return out
    except Exception:
        conn.rollback()
        cur.execute("SELECT id, name FROM dict_industry WHERE status=1")
        return [(_norm(r, 2)[0], _norm(r, 2)[1], [_norm(r, 2)[1]])
                for r in cur.fetchall()]
    finally:
        cur.close()

def infer_industry_id(title: str, content_text: str, industries: list) -> Optional[int]:
    """根据标题+内容关键词命中最多的行业；一个都不中时兜底「其他行业」"""
    if not industries:
        return None
    fallback_id = next((i for i, n, _ in industries if n == INDUSTRY_FALLBACK), None)
    if not title and not content_text:
        return fallback_id
    blob = (title or "") + " " + (content_text or "")[:500]
    best_id, best_score = None, 0
    for ind_id, ind_name, keywords in industries:
        score = sum(1 for kw in keywords if kw and kw in blob)
        if score > best_score:
            best_score = score
            best_id = ind_id
    return best_id if best_id is not None else fallback_id


# =====================================================
# Step 7: 单条记录清洗主入口
# =====================================================

def clean_one(record: dict, conn) -> dict:
    """
    输入 dict（从数据库 SELECT 出来的行），返回填充好的 dict。
    不直接 UPDATE，由调用方决定怎么写库（批量更高效）。
    """
    title = record.get("title") or ""
    content = record.get("content") or ""
    content_text = record.get("content_text") or ""
    tenderee = record.get("tenderee") or ""

    # 如果 content_text 是空但 content 有值 → 从 HTML 清洗
    if not content_text and content:
        content_text = strip_html(content)

    # 如果 content 和 content_text 都空但 title 有值 → content_text = 标题作兜底
    if not content_text:
        content_text = title

    # 日期清洗
    publish_time = clean_date(record.get("publish_time"))
    winner_publish_time = clean_date(record.get("winner_publish_time"))
    deadline = clean_date(record.get("deadline"))

    # 分类推断
    industries = record.get("_industries") or load_industries(conn)
    notice_type_id = record.get("notice_type_id") or infer_notice_type_id(title, conn, content_text)
    procure_type = record.get("procure_type") or infer_procure_type(title, content_text)
    customer_group = record.get("customer_group") or infer_customer_group(tenderee, title)
    industry_id = record.get("industry_id") or infer_industry_id(title, content_text, industries)

    # 正文字段提取（2026-11-26 接入最新逻辑，与爬虫入库/补抓脚本同一实现）：
    # 截止时间 / 项目编号 / 地区 / 单位 / 金额 —— 只补空字段，不覆盖已有值
    out = {
        **record,
        "content_text": content_text,
        "publish_time": publish_time,
        "winner_publish_time": winner_publish_time,
        "deadline": deadline,
        "notice_type_id": notice_type_id,
        "procure_type": procure_type,
        "customer_group": customer_group,
        "industry_id": industry_id,
    }
    try:
        extra = extract_fields_from_text(
            title, content_text, conn=conn,
            current={"deadline": out.get("deadline"),
                     "project_code": out.get("project_code"),
                     "region_code": out.get("region_code"),
                     "tenderee": out.get("tenderee") or None,
                     "budget": out.get("budget")})
        out.update(extra)
    except Exception:
        logger.warning("clean_one extract_fields failed id=%s", record.get("id"), exc_info=True)
    return out


# =====================================================
# Step 8: 全表批量清洗（种子数据用）
# =====================================================

def clean_all_seed(limit: int = 0, dry_run: bool = False) -> dict:
    """
    批量清洗 bid_info 种子数据。
    limit=0 表示全量；dry_run=True 只打印不写库。
    """
    conn = pymysql.connect(**DB_CONFIG)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM bid_info")
    total = cur.fetchone()[0] if limit == 0 else limit

    cur.execute("SELECT id FROM bid_info ORDER BY id LIMIT %s", (total,))
    ids = [r[0] for r in cur.fetchall()]

    industries = load_industries(conn)

    stats = {
        "content_text_filled": 0,
        "date_cleaned": 0,
        "notice_type_filled": 0,
        "procure_type_filled": 0,
        "customer_group_filled": 0,
        "industry_filled": 0,
        "fields_extracted": 0,   # 正文字段提取补空（截止/编号/地区/单位/金额）
        "rows_processed": 0,
    }

    for bid_id in ids:
        cur.execute(
            "SELECT id, title, content, content_text, tenderee, publish_time, "
            "winner_publish_time, deadline, notice_type_id, procure_type, "
            "customer_group, industry_id, project_code, region_code, budget "
            "FROM bid_info WHERE id=%s", (bid_id,)
        )
        row = dict(zip([d[0] for d in cur.description], cur.fetchone()))
        if not row:
            continue

        original = dict(row)
        row["_industries"] = industries
        cleaned = clean_one(row, conn)

        diffs = []
        for col in ("content_text", "publish_time", "winner_publish_time", "deadline",
                    "notice_type_id", "procure_type", "customer_group", "industry_id",
                    "project_code", "region_code", "tenderee", "budget"):
            if cleaned.get(col) != original.get(col):
                diffs.append(col)

        if not dry_run and diffs:
            sets = ", ".join(f"{c}=%s" for c in diffs)
            values = [cleaned.get(c) for c in diffs] + [bid_id]
            cur.execute(f"UPDATE bid_info SET {sets} WHERE id=%s", values)

        # 统计
        if "content_text" in diffs and original.get("content_text") in (None, ""):
            stats["content_text_filled"] += 1
        if any(c in diffs for c in ("publish_time", "winner_publish_time", "deadline")):
            stats["date_cleaned"] += 1
        if "notice_type_id" in diffs and original.get("notice_type_id") is None:
            stats["notice_type_filled"] += 1
        if "procure_type" in diffs and not original.get("procure_type"):
            stats["procure_type_filled"] += 1
        if "customer_group" in diffs and not original.get("customer_group"):
            stats["customer_group_filled"] += 1
        if "industry_id" in diffs and original.get("industry_id") is None:
            stats["industry_filled"] += 1
        if any(c in diffs for c in ("project_code", "region_code", "tenderee", "budget")):
            stats["fields_extracted"] += 1
        stats["rows_processed"] += 1

        if stats["rows_processed"] % 1000 == 0:
            print(f"  ... processed {stats['rows_processed']}/{total}")

    if not dry_run:
        conn.commit()
    cur.close()
    conn.close()

    print("\n" + "=" * 50)
    print("清洗结果统计:")
    print("=" * 50)
    for k, v in stats.items():
        print(f"  {k:25s} {v}")
    return stats


def backfill_notice_type(limit: int = 0) -> int:
    """回填 notice_type_id 为空的存量标讯，只改这一个字段，返回更新条数"""
    conn = pymysql.connect(**DB_CONFIG)
    try:
        cur = conn.cursor()
        sql = "SELECT id, title, content_text FROM bid_info WHERE notice_type_id IS NULL"
        if limit:
            sql += f" LIMIT {int(limit)}"
        cur.execute(sql)
        rows = cur.fetchall()
        updated = 0
        for bid_id, title, content_text in rows:
            type_id = infer_notice_type_id(title or "", conn, content_text or "")
            if type_id is None:
                continue
            cur.execute("UPDATE bid_info SET notice_type_id=%s, updated_at=NOW() WHERE id=%s", (type_id, bid_id))
            updated += 1
            if updated % 500 == 0:
                conn.commit()
                print(f"  ... {updated}/{len(rows)}")
        conn.commit()
        cur.close()
        print(f"公告类型回填完成：待处理 {len(rows)} 条，已更新 {updated} 条")
        return updated
    finally:
        conn.close()


# =====================================================
# 正文字段提取（2026-11-26 下沉为公共函数）
# 原实现只在 scripts/fetch_missing_content.py 里，爬虫入库不调用，
# 导致新入库标讯 deadline/项目编号等字段为空就被推送 —— 现爬虫与补抓脚本共用本组函数
# =====================================================

# 编号值：允许中文前缀（如「浙工咨丽招采〔2026〕5号」），但必须含字母/数字，
# 排除「项目编号：见附件」这类纯中文；遇冒号/句读即截断，避免吞掉相邻表格列
_CODE_VAL = (r"([\[\(（〔]?[A-Za-z0-9一-龥]"
             r"[A-Za-z0-9一-龥\-_（）()〔〕\[\]\.\/]{1,44}号?)")
_PROJECT_CODE_RES = [
    re.compile(r"项目编号\s*[：:]?\s*" + _CODE_VAL),
    re.compile(r"采购项目编号\s*[：:]?\s*" + _CODE_VAL),
    re.compile(r"标段编号\s*[：:]?\s*" + _CODE_VAL),
    re.compile(r"招标编号\s*[：:]?\s*" + _CODE_VAL),
    re.compile(r"项目编号为\s*" + _CODE_VAL),
]
# 值里必须含数字或字母，排除「项目编号：见附件」这类纯中文
_HAS_ALNUM = re.compile(r"[A-Za-z0-9]")

# 截止时间：标签 + 中文日期 / ISO 日期
# 按优先级排列：具体标签在前，通用标签在后（列表顺序 = 优先级，与文本位置无关）
_DEADLINE_LABELS = (
    "投标截止时间", "投标截止日期", "投标文件递交截止时间", "递交投标文件截止时间",
    "提交投标文件截止时间", "投标文件提交截止时间", "响应文件递交截止时间",
    "响应文件提交截止时间", "响应文件递交截止", "递交响应文件截止时间",
    "磋商截止时间", "报价截止时间", "报价截止日期", "报价截止",
    "递交截止时间", "提交截止时间", "递交截止", "提交截止",
    "截止时间", "截止日期",
    # 注：「开标时间/开启时间」不算截止时间（开标在截止之后，语义不同）
)
# 出现在标签前面时说明是「文件售卖/获取」截止，不是投标截止，必须跳过
# 「公示」是公示期截止（如 公示截止时间:2026-11-28），也不是投标截止
_DEADLINE_EXCLUDE = ("售卖", "获取", "发售", "下载", "购买", "报名", "注册", "公示")
# 排除词只看紧邻标签前的短窗口，避免「免费获取 四、响应文件提交 截止时间」被误排除
_DEADLINE_PRE_WINDOW = 8
# 中文日期：支持 2025年7月4日 9:5 / 2025年7月4日9时5分 / …14 点 00 分（「点」也算时分隔）
_CN_DATE = (r"(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*"
            r"(?:\d{1,2}\s*[:：时点]\s*\d{1,2}(?:\s*[:：分]\s*\d{1,2})?(?:\s*秒)?)?)")
# ISO 日期：2025-07-08 15:00:00 / 2025/7/8 15:00 / 2026-12-02（时间可选，纯日期也算）
_ISO_DATE = r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s*\d{1,2}[:：]\d{2}(?::\d{2})?)?)"
# 截止标签后多少字符内出现日期才算数（太大会把空表单字段后面无关日期误取）
_DEADLINE_WINDOW = 80

_REGION_RES = [
    re.compile(r"行政区域[：:]\s*([一-龥]{2,10}?(?:省|市|自治区|特别行政区))"),
    re.compile(r"项目所在地[：:]\s*([一-龥]{2,10}?(?:省|市|自治区))"),
    re.compile(r"采购单位地址[：:]\s*(?:[一-龥]{2,6}省|)?([一-龥]{2,6}市)"),
]

# 单位（招标人/采购人）：常见形态
#   「采购人信息： 名称：值」/「招标人: 名称:值」/「采购人名称：值」/「招标人为值」/「招标人 值」
_TENDEREE_RES = [
    # 标签 + 可选「信息/名称」后缀 + 冒号 + 可选「名称：」子标签 + 值
    re.compile(r"(?:招标人|招标单位|采购人|采购单位|项目业主|发包人|需求单位)"
               r"\s*(?:信息|名\s*称|单位名称)?\s*[：:]\s*"
               r"(?:名\s*称\s*[：:]\s*)?"
               r"([^\n\r，,；;。]{2,60})"),
    # 「招标人为值」「采购人为值」
    re.compile(r"(?:招标人|招标单位|采购人|采购单位|项目业主|发包人|需求单位)"
               r"\s*为\s*([^\n\r，,；;。]{2,60})"),
    # 「招标人 值」——空格分隔无冒号（后面不能紧跟 名称/信息 等，避免重复吞子标签）
    re.compile(r"(?:招标人|招标单位|采购人|采购单位|项目业主|发包人|需求单位)"
               r"[ 　]+(?![名信联电邮招采项])([^\n\r，,；;。]{2,60})"),
]

# 预算金额：数值 + 单位（万元/元），排除「中标金额/成交金额」（那是结果不是预算）
# 「投标报价」是 ggzy 中标公示表格里的金额（小写报价），对展示有意义，纳入
# 注：原先「任意数字+元」兜底会误提代理服务费/起拍价/中标报价（实证 #8650/#8643/#8647），
#     已删除——预算必须有明确标签才认
_BUDGET_RES = [
    re.compile(r"(?:预算金额|项目预算|采购预算|预算|总投资|项目金额|投标报价)"
               r"\s*[：:为约]?\s*([\d,]+(?:\.\d+)?)\s*(万元|亿元|元)"),
]
_BUDGET_NEG = ("中标", "成交", "结算", "决算",
               "代理", "服务费", "起拍", "保证金", "收费")  # 这些词出现在标签前则不是预算

# 结果类字段（ggzy 中标/成交公告）：标签与值常被换行分隔，extract_fields_from_text
# 已把正文压平成单行，压平后「中标人： 值」可同行匹配。
# 不匹配「中标候选人」（候选人 ≠ 中标人，宁缺勿滥）
_WINNER_UNIT_RES = [
    re.compile(r"(?:中标|成交|中选)(?:人|供应商|单位)\s*(?:名\s*称|全称)?"
               r"\s*[：:]\s*([^\s：:，,；;。]{2,60})"),
    # v2（2026-11-27）：成交/挂牌场景（竞得单位/受让单位/竞买人/成交方）
    re.compile(r"(?:竞得|受让)(?:人|单位|方)\s*(?:名\s*称|全称)?\s*[：:]\s*([^\s：:，,；;。]{2,60})"),
    re.compile(r"(?:受让|竞得)单位\s+([^\s，,；;]{2,60}(?:有限公司|集团|厂|公司|中心))"),
]
_WINNER_AMOUNT_RES = [
    # 「中标价（费率或单价等）：250.4306万元」括号说明可跳过
    re.compile(r"(?:中标|成交|中选)(?:价|金额|报价)\s*(?:[（(][^）)]*[）)])?"
               r"\s*[：:为约]?\s*([\d,]+(?:\.\d+)?)\s*(亿元|万元|元)"),
    # v2（2026-11-27）：土地挂牌等场景（成交价/出让价/竞得价）
    re.compile(r"(?:成交|出让|竞得)(?:价|金额)\s*[（(][^）)]*[）)]?"
               r"\s*[：:为约]?\s*([\d,]+(?:\.\d+)?)\s*(亿元|万元|元)"),
]
_WINNER_UNIT_BAD = ("未开标", "详见", "无", "待定", "废标", "流标", "否决")


# 编号值后面若紧跟这些词，说明吞到了相邻表格列（「…2025-024采购方式竞争性磋商…」），截断
_PC_STOP = ("采购方式", "采购公告", "采购需求", "预算", "最高限价", "项目名称",
            "标段名称", "招标文件编号", "项目分包", "磋商日期", "开标时间",
            "中标", "成交", "公告期限", "公示期限", "联系电话", "联系人")


def extract_project_code(text: str) -> Optional[str]:
    for rx in _PROJECT_CODE_RES:
        m = rx.search(text)
        if not m:
            continue
        # 去掉首尾包裹括号与句读（如 标题「（项目编号JXLH2026-LN-XC006）」尾部的 ））
        v = m.group(1).strip().strip("（）()〔〕[]【】。；;，,、 ")
        # 值内吞到相邻列的标签词 → 截到标签词之前
        cuts = [v.find(w) for w in _PC_STOP]
        cuts = [i for i in cuts if i > 0]
        if cuts:
            v = v[:min(cuts)]
        v = v.strip().strip("（）()〔〕[]【】。；;，,、 ")
        if len(v) >= 5 and len(v) <= 40 and _HAS_ALNUM.search(v):
            return v
    return None


def _parse_cn_date(s: str) -> Optional[datetime]:
    """兼容 中文日期（2025年7月4日 9:5 / 9时5分30秒 / 14 点 00 分）与 ISO（2025-07-08 15:00:00 / 2026-12-02）
    2026-11-26 修复：年月日/时分之间的空格（「2026 年 12 月 17 日」）曾导致锚定失败；
    「点」原先不识别；日期尾部残留字（如「17：30前」）导致整体匹配失败。
    """
    s = re.sub(r"\s+", " ", s).strip()
    s = (s.replace("年", "-").replace("月", "-").replace("日", " ")
           .replace("点", ":").replace("时", ":").replace("分", ":").replace("秒", "")
           .replace("：", ":").replace("/", "-"))
    s = re.sub(r"\s+", " ", s)
    # 去掉分隔符两侧空格：「2026 - 12 - 17」「09 : 30」→「2026-12-17」「09:30」
    s = re.sub(r"\s*-\s*", "-", s)
    s = re.sub(r"\s*:\s*", ":", s)
    s = s.strip().rstrip(":").strip()
    # 用 search 而非全串 match：容忍尾部残留字（「前」「截止」等）
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})"
                  r"(?:[ ](\d{1,2}):(\d{1,2})(?::(\d{1,2}))?)?", s)
    if not m:
        return None
    y, mo, d, h, mi, se = m.groups()
    try:
        return datetime(int(y), int(mo), int(d),
                        int(h or 0), int(mi or 0), int(se or 0))
    except ValueError:
        return None


def extract_deadline(text: str) -> Optional[datetime]:
    """按标签优先级找投标截止时间。
    同一标签可能多次出现，逐个尝试；标签前文含「售卖/获取/发售…」时跳过（那是文件获取截止）。
    """
    for label in _DEADLINE_LABELS:
        start = 0
        while True:
            idx = text.find(label, start)
            if idx < 0:
                break
            start = idx + 1
            pre = text[max(0, idx - _DEADLINE_PRE_WINDOW): idx]
            if any(x in pre for x in _DEADLINE_EXCLUDE):
                continue
            window = text[idx: idx + _DEADLINE_WINDOW]
            for rx in (_CN_DATE, _ISO_DATE):
                m = re.search(rx, window)
                if not m:
                    continue
                # 日期前出现引号/右括号 → 是正文里夹的 JSON
                # （如 "publishTime":"2025-06-11 12:34:51"），不是截止时间
                if '"' in window[:m.start()] or '}' in window[:m.start()]:
                    continue
                dt = _parse_cn_date(m.group(1))
                if dt and 2020 <= dt.year <= 2035:
                    return dt
    return None


def extract_region_name(text: str) -> Optional[str]:
    for rx in _REGION_RES:
        m = rx.search(text)
        if m:
            return m.group(1).strip()
    return None


# 值以这些词开头说明采购人格子是空的、抓到的是相邻单元格/正文，不是单位名
_TENDEREE_BAD_PREFIX = (
    "项目名称", "项目编号", "标段", "采购项目", "名称",
    "联系人", "联系电话", "联系方式", "电话", "邮箱",
    "招标代理", "代理机构", "采购代理",
    "本项目", "该项目", "根据", "按照", "受",
    # 采购人格子为空时抓到的相邻标签（「需求单位： 需求单位地址：…」）
    "需求单位", "采购单位", "地址", "邮编",
)


def extract_tenderee(text: str) -> Optional[str]:
    """从正文提取招标人/采购人（仅用于补空字段）。
    表格文本里值后面常跟着 联系方式/招标代理 等相邻单元格，需截断；
    采购人格子为空时会抓到「项目名称：XX」等相邻列，需按前缀跳过。
    """
    for rx in _TENDEREE_RES:
        m = rx.search(text)
        if m:
            v = m.group(1).strip().strip("：:　 ")
            # 单位名里不该有空格/冒号：一旦出现说明已越界到相邻单元格或下一字段
            cuts = [i for i in (v.find(" "), v.find("　"), v.find("："), v.find(":"))
                    if i > 0]
            if cuts:
                v = v[:min(cuts)]
            if v.startswith(_TENDEREE_BAD_PREFIX):
                continue
            for stop in ("联系方式", "联系人", "联系电话", "电话", "邮箱",
                         "招标代理", "代理机构", "采购代理",
                         "项目名称", "项目编号", "标段名称", "标段编号"):
                i = v.find(stop)
                if i > 0:
                    v = v[:i]
            v = v.strip().strip("：:　 ")
            if v.startswith(_TENDEREE_BAD_PREFIX):
                continue
            if 2 <= len(v) <= 60:
                return v
    return None


def extract_budget(text: str) -> Optional[str]:
    """从正文提取预算金额，返回带单位的原串（如 350.00 万元）；仅用于补空字段"""
    for rx in _BUDGET_RES:
        for m in rx.finditer(text):
            # 标签前 8 字内出现 中标/成交 等词 → 是结果金额，跳过
            idx = m.start()
            pre = text[max(0, idx - 8): idx]
            if any(x in pre for x in _BUDGET_NEG):
                continue
            num = m.group(1).replace(",", "")
            unit = m.group(2) if (m.lastindex or 0) >= 2 else "元"
            try:
                val = float(num)
            except ValueError:
                continue
            if val <= 0:
                continue
            # 亿元统一折成「万元」口径保留原单位即可，直接回原串
            return f"{m.group(1)} {unit}"
    return None


def extract_winner(text: str) -> dict:
    """提取结果类字段：中标单位、中标金额（元）。
    仅用于补空字段；标签与值同行/压平后相邻均可匹配。
    返回只含确实提取到的键。"""
    out: dict = {}
    flat = re.sub(r"\s+", " ", text or "")
    for rx in _WINNER_UNIT_RES:
        m = rx.search(flat)
        if m:
            v = m.group(1).strip().strip("：:　 ")
            # 值吞到相邻标签/越界时按已知标签截断
            for stop in ("中标", "成交", "中选", "采购人", "招标人", "项目名称",
                         "标段", "统一社会信用代码"):
                i = v.find(stop)
                if i > 0:
                    v = v[:i]
            v = v.strip()
            if v and v not in _WINNER_UNIT_BAD and 2 <= len(v) <= 60:
                out["winner_unit"] = v
                break
    for rx in _WINNER_AMOUNT_RES:
        m = rx.search(flat)
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
            except ValueError:
                continue
            unit = m.group(2)
            if val <= 0:
                continue
            if unit == "亿元":
                val *= 100000000
            elif unit in ("万元", "万"):
                val *= 10000
            out["win_amount"] = val
            break
    return out


def parse_budget_wan(s: Optional[str]) -> Optional[float]:
    """把 budget 字符串（如 "350.00 万元"、"1.2 亿元"、"500000 元"）折算成万元数值。
    解析失败返回 None（调用方决定保留还是跳过）。单位口径与 extract_budget 一致。"""
    if not s:
        return None
    m = re.search(r"([\d,]+(?:\.\d+)?)\s*(亿元|万元|万|元)?", str(s))
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", ""))
    except ValueError:
        return None
    unit = m.group(2) or "元"
    if unit in ("亿元",):
        return val * 10000
    if unit in ("万元", "万"):
        return val
    return val / 10000


def extract_fields_from_text(title: str, text: str, conn=None,
                             current: Optional[dict] = None) -> dict:
    """从正文一次性提取所有可补字段，只返回**当前为空**的字段新值。
    current: {"deadline","project_code","region_code","tenderee","budget"} 现值（缺省视为全空）
    爬虫入库与补抓脚本共用；conn 供地区字典查询（可空，空则不提地区）。
    """
    cur = current or {}
    flat = re.sub(r"\s+", " ", text or "")
    out: dict = {}

    if cur.get("deadline") is None:
        dl = extract_deadline(flat)
        if dl:
            out["deadline"] = dl
    if not cur.get("project_code"):
        # 标题也参与：「XX采购项目（项目编号JXLH2026-LN-XC006）」编号只在标题里
        pc = extract_project_code((title or "") + " " + flat)
        if pc:
            out["project_code"] = pc
    if not cur.get("tenderee"):
        td = extract_tenderee(flat)
        if td:
            out["tenderee"] = td
    if not cur.get("budget"):
        bg = extract_budget(flat)
        if bg:
            out["budget"] = bg
    # 结果类字段：中标单位/中标金额（中标公告正文里有，原管线一直没提）
    if not cur.get("winner_unit") or not cur.get("win_amount"):
        win = extract_winner(flat)
        if not cur.get("winner_unit") and win.get("winner_unit"):
            out["winner_unit"] = win["winner_unit"]
        if not cur.get("win_amount") and win.get("win_amount"):
            out["win_amount"] = win["win_amount"]
    # 地区：正文标签没写时，用正文里出现的市/省名反查 dict_region（只填空值）
    if (not cur.get("region_code") or cur.get("region_code") == "-1") and conn is not None:
        try:
            # conn 可能是连接（clean_one）也可能是游标（爬虫入库），统一成游标
            cursor = conn if hasattr(conn, "execute") else conn.cursor()
            nname = extract_region_name(flat)
            code = None
            if nname:
                cursor.execute("SELECT code FROM dict_region WHERE name=%s LIMIT 1", (nname,))
                row = cursor.fetchone()
                if row:
                    code = row[0]
            if not code:
                # 市（level=2）优先，其次省（level=1）；同级长名优先，避免短名误吞
                cursor.execute("SELECT name, code FROM dict_region "
                               "WHERE level IN (1,2) ORDER BY level DESC, LENGTH(name) DESC")
                for cname, ccode in cursor.fetchall():
                    if cname and cname in flat:
                        code = ccode
                        break
            if code:
                out["region_code"] = code
        except Exception:
            logger.debug("extract region failed", exc_info=True)

    # 客群：采购人补出来后按「采购人+标题」重推（原来只按标题，代理机构名带“公司”会误判民企）
    if out.get("tenderee"):
        out["customer_group"] = infer_customer_group(out["tenderee"], title)

    return out


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
    if "--notice-type" in sys.argv:
        # 只回填公告类型（存量数据打标签）
        backfill_notice_type(limit=limit)
    else:
        clean_all_seed(limit=limit, dry_run=dry_run)
