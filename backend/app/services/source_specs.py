# -*- coding: utf-8 -*-
"""
源站专用清洗规范（SourceSpec）
======================================

按 source 分类，每个源站定义一套专用的"字段提取优先级"：

  source_code → Spec {
      "notice_type_detect": 公告类型推断规则（title 关键词优先级表）,
      "field_extract":      字段 → 专用提取函数（失败返回 None 即退回通用正则）,
      "html_selectors":     详情页正文容器选择器（专用顺序）,
      "amount_formats":     金额格式（如 ccgp 详情页是 "¥1,234,567.00 元" / ggzy 是 "1234567.00 万元"）,
  }

每个 extractor 函数签名：(content_html_or_text: str, raw: dict) -> value | None
  - raw 里已经放了 title / source_url / external_id，可用于二次推断

调用顺序（crawl.py 入库前）：
  1. extract_fields_from_text（通用规则，免费）
  2. 进入这里，若当前 source_code 有 Spec 且某字段仍空 → 调专用 extractor
  3. 通用规则 + 专用 extractor 都空 → AI 兜底（已在 crawl.py 里）
"""
from __future__ import annotations
import re
import logging
from typing import Optional, Dict, Any, Callable
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


# ============================================================
# 工具：字段提取器的通用 helper（让各 Spec 的 extractor 写起来简洁）
# ============================================================

def _extract_kv_from_table(html: str, key_variants: list[str]) -> Optional[str]:
    """HTML 里找 <th>/<td> 或 <label> + <span> 形式的 key/value 表

    key_variants = ["采购单位", "采购人", "招标人"] 任一命中即返回对应的 value
    """
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return None

    # 优先查 <tr> 形式：<th>采购单位</th><td>XX</td>
    for tr in soup.find_all("tr"):
        cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
        if len(cells) >= 2:
            head, tail = cells[0], cells[1]
            for kv in key_variants:
                if kv in head and tail and len(tail) >= 2 and len(tail) <= 120:
                    return tail

    # 其次查 <div class="xxx_kv"><label>采购单位：</label><span>XX</span></div> 形式
    for sel in (".info-kv", ".detail-item", ".form-row", ".pub-info"):
        for block in soup.select(sel):
            for lbl in block.find_all(["label", "th", "div"]):
                txt = lbl.get_text(" ", strip=True)
                for kv in key_variants:
                    if kv in txt:
                        nxt = lbl.find_next(["span", "td", "div"])
                        if nxt:
                            v = nxt.get_text(" ", strip=True)
                            if v and len(v) >= 2 and len(v) <= 120 and kv not in v:
                                return v
    return None


def _first_winner_from_table(html: str) -> Optional[str]:
    """供应商/中标人表格里取序号 1 那行的名称

    表头可能是：供应商名称 / 中标供应商 / 中标单位 / 中标人 等
    识别逻辑：找含"供应商/中标人/中标单位"的表头 → 下一行是序号 1 的条目
    """
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return None
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for i, tr in enumerate(rows):
            head_cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if not any(("供应商" in c or "中标人" in c or "中标单位" in c
                        or "竞得" in c or "受让" in c)
                       for c in head_cells):
                continue
            # 往下看最多 5 行，取序号为 1 的（第 1 列纯数字）
            for nxt in rows[i + 1:i + 6]:
                c2 = [c.get_text(" ", strip=True) for c in nxt.find_all(["td", "th"])]
                if len(c2) >= 2:
                    first = c2[0]
                    if re.fullmatch(r"\d{1,3}", first) and int(first) == 1:
                        name = c2[1]
                        if name and 2 <= len(name) <= 80:
                            return name
                    # 有些表没序号，第一行直接就是第一候选人
                    if re.search(r"(有限公司|集团|中心|厂|所)$", first or c2[1] or ""):
                        name = first or c2[1]
                        if 2 <= len(name) <= 80:
                            return name
    return None


def _money_from_table(html: str, key_variants: list[str],
                      prefer_regex_over_table: bool = False) -> Optional[float]:
    """从 HTML/文本里取金额，返回元（float）

    prefer_regex_over_table=True 时优先用"中标/成交/总价"类正则（避免误抓起始价/预算）
    否则用 key_variants 定位关键词再扫金额（ccgp 概要表专用）
    """
    if not html:
        return None
    # 先转纯文本（去掉 HTML tag 属性里的数字干扰）
    try:
        text = BeautifulSoup(html, "html.parser").get_text("\n", strip=True)
    except Exception:
        text = re.sub(r"<[^>]+>", "", html)

    # 数字前不能紧跟数字/逗号/小数点，否则 "148,530,915.00元" 会被截成 "915.00元"
    money_plain = (r"(?<![\d,.])(?:人民币|￥|¥)?\s*"
                   r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)\s*(亿元|万元|元)")
    # 无单位兜底：¥1,234,567.00 / 980000.00 这种
    money_no_unit = (r"(?<![\d,.])(?:￥|¥)?\s*"
                     r"(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d{1,2})(?!\d)")

    if prefer_regex_over_table:
        # ggzy 专用：只认"中标/成交/总价"，不认起始价/预算
        # 遍历所有 win_kw 命中的 blob，扫所有带单位的金额，取最大的（成交价 > 起始价）
        win_kw = ("中标", "成交", "总价")
        best: Optional[float] = None
        for kw in win_kw:
            start = 0
            while True:
                idx = text.find(kw, start)
                if idx < 0:
                    break
                blob = text[idx:idx + 800]
                for m in re.finditer(money_plain, blob):
                    v = _money_to_yuan(m.group(1), m.group(2))
                    if best is None or v > best:
                        best = v
                start = idx + len(kw)
        return best

    # ccgp 默认：key_variants 定位关键词再扫金额
    for kw in key_variants:
        idx = text.find(kw)
        if idx < 0:
            continue
        # 关键词后紧跟的 200 字符内找（避免 blob 太长匹配到后面别的金额）
        blob = text[idx:idx + 200]
        m = re.search(money_plain, blob)
        if m:
            return _money_to_yuan(m.group(1), m.group(2))
        # 无单位兜底（¥1,234,567.00 这种紧接关键词的金额）
        m2 = re.search(money_no_unit, blob)
        if m2:
            return float(m2.group(1).replace(",", ""))
    return None


def _table_column_amount(html: str, keys: tuple) -> Optional[float]:
    """表格列定位取金额：「成交价（万元）」表头 → 取数据行同列数值

    适配土地挂牌/成交公示表：表头行有「成交价(万元)」，数值在后续行的同列。
    列的先后顺序和行列数各站不一，用表头文本定位列号最可靠。
    """
    if not html:
        return None
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return None
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for ri, tr in enumerate(rows):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            for ci, ctext in enumerate(cells):
                if not any(k in ctext for k in keys):
                    continue
                unit = "元"
                if "万元" in ctext:
                    unit = "万元"
                elif "亿元" in ctext:
                    unit = "亿元"
                # 数值在同一表头行的相邻单元格，或后续数据行的同列
                cand_cells = []
                if ci + 1 < len(cells):
                    cand_cells.append(cells[ci + 1])
                for nxt in rows[ri + 1:ri + 6]:
                    c2 = [c.get_text(" ", strip=True) for c in nxt.find_all(["td", "th"])]
                    if ci < len(c2):
                        cand_cells.append(c2[ci])
                for cv in cand_cells:
                    m = re.search(r"(?<![\d.,])(\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)", cv or "")
                    if m:
                        v = float(m.group(1).replace(",", ""))
                        if v <= 0:
                            continue
                        if unit == "万元":
                            v *= 1e4
                        elif unit == "亿元":
                            v *= 1e8
                        return v
    return None


def _money_to_yuan(num_str: str, unit: str) -> float:
    num = float(num_str.replace(",", ""))
    if "亿" in unit:
        num *= 1e8
    elif "万" in unit:
        num *= 1e4
    return num


def _parse_dt_smart(s: str) -> Optional[str]:
    """多种日期格式 → ISO 字符串（给 crawler 用）"""
    if not s:
        return None
    m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})"
                  r"(?:\s+(\d{1,2})[:：](\d{1,2}))?", s)
    if not m:
        return None
    y, mo, d = m.group(1), int(m.group(2)), int(m.group(3))
    hh, mm = m.group(4), m.group(5)
    hh = hh or "00"
    mm = mm or "00"
    return f"{y}-{int(mo):02d}-{int(d):02d} {int(hh):02d}:{int(mm):02d}:00"


# ============================================================
# 两个源站的专用 extractor 函数
# ============================================================

def _extract_from_ccgp(content_html: str, raw: dict) -> Dict[str, Any]:
    """ccgp.gov.cn 详情页专用：公告概要表 + 中标供应商表

    ccgp 详情页结构（div.main > div.main_container > 公告概要/公告信息）：
      <table>
        <tr><td class="title">采购单位</td><td colspan="3">太原理工大学</td></tr>
        <tr><td class="title">预算金额</td><td colspan="3">¥1,234,567.00</td></tr>
        <tr><td class="title">开标时间</td><td colspan="3">2026-12-15 09:00:00</td></tr>
        <tr><td class="title">中标供应商</td><td>...</td></tr>
      </table>
    """
    out: Dict[str, Any] = {}

    # 先把 table 里的 key→value 都抓出来（ccgp 表结构稳定）
    kv: Dict[str, str] = {}
    try:
        soup = BeautifulSoup(content_html or "", "html.parser")
        for tr in soup.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if len(cells) >= 2:
                head, tail = cells[0], cells[1]
                if head and tail and 2 <= len(head) <= 20:
                    kv[head] = tail
    except Exception:
        pass

    def _kv(*keys: str) -> Optional[str]:
        for k in keys:
            v = kv.get(k)
            if v:
                return v
        return None

    # 1) 采购人 / 代理机构（可以同时存在）
    td = _kv("采购单位", "采购人", "招标人")
    if td:
        out["tenderee"] = td
    ag = _kv("代理机构名称", "代理机构", "招标代理机构", "采购代理")
    if ag:
        out["agency"] = ag

    # 2) 预算（ccgp 表里金额格式稳定：¥1,234,567.00 / 1,234,567.00 元）
    bv = _kv("预算金额", "采购预算", "项目预算")
    if bv:
        amt = _parse_ccgp_money(bv)
        if amt is not None:
            out["budget"] = f"{amt:.2f}"

    # 3) 开标/投标截止（ccgp 表里时间格式：2026年11月24日  19:30 或 2026-12-15 09:00:00）
    for k in ("开标时间", "投标截止时间", "提交投标文件截止时间", "开标日期"):
        dt = _kv(k)
        if dt:
            iso = _parse_dt_smart(dt)
            if iso:
                out["deadline"] = iso
                break

    # 4) 中标供应商 + 中标金额
    wu = _first_winner_from_table(content_html)
    if wu:
        out["winner_unit"] = wu
    wa_val = _kv("总成交金额", "中标金额", "成交金额", "中标成交金额")
    if wa_val:
        amt = _parse_ccgp_money(wa_val)
        if amt is not None and amt > 0:
            out["win_amount"] = amt

    return out


def _parse_ccgp_money(s: str) -> Optional[float]:
    """ccgp 表里金额格式：¥1,234,567.00 / 1,234,567.00 元 / 人民币1200万元"""
    if not s:
        return None
    # 纯数字 + 逗号 + 可选小数
    m = re.search(r"(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)", s)
    if not m:
        return None
    num = float(m.group(1).replace(",", ""))
    # 单位换算
    if "亿" in s:
        num *= 1e8
    elif "万" in s:
        num *= 1e4
    return num


def _extract_from_ggzy(content_html: str, raw: dict) -> Dict[str, Any]:
    """ggzy.gov.cn 详情页专用：三跳聚合壳 + 地方公共资源交易网原文

    ggzy 原文 HTML 有两种常见格式：
    A. **表格格式一（colspan=2 单列）**：每个 <td colspan="2"> 里放一段"序号、字段名：值"
       如：<td>1、项目名称：XX</td><td>2、采购文件领取截止时间：2026-12-03 17:00</td>
    B. **表格格式二（两列 key/value）**：地方交易网原文（如浙江省）标准公告表
    C. **纯文本关键词**：土地出让类公示常用"竞得人：XX 成交价：XX"格式

    提取优先级：A（正则扫 colspan 表）→ B（两列表）→ C（纯文本正则）
    """
    out: Dict[str, Any] = {}

    # 把 HTML 转成纯文本（保留换行），方便统一正则扫
    try:
        text = BeautifulSoup(content_html or "", "html.parser").get_text("\n", strip=True)
    except Exception:
        text = content_html or ""

    # --- A. colspan=2 单列表里的结构化字段（最常见） ---
    # 匹配：任意"关键词：值"格式（表格 td 里常见）
    kw_patterns = [
        ("tenderee", [
            r"(?:\d+[、.]\s*)?(?:项目业主|建设单位|采购人|采购单位|招标人)[：:]\s*([^\s，,；;。\n（）(]{2,80})",
        ]),
        ("agency", [
            r"(?:\d+[、.]\s*)?招标(?:代理)?机构[：:]\s*([^\s，,；;。\n（）(]{2,80})",
        ]),
        ("budget", [
            r"(?:\d+[、.]\s*)?采购预算[：:]\s*([^\s，,；;。\n（）(]{2,80})",
            r"(?:\d+[、.]\s*)?预算金额[：:]\s*([^\s，,；;。\n（）(]{2,80})",
        ]),
        ("deadline", [
            r"(?:\d+[、.]\s*)?开标(?:时间|日期)[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}(?:\s+\d{1,2}[:：]\d{1,2})?)",
            r"(?:\d+[、.]\s*)?(?:提交)?投标(?:文件)?(?:递交|截止)时间[：:]\s*(\d{4}[-/年]\d{1,2}[-/月]\d{1,2}(?:\s+\d{1,2}[:：]\d{1,2})?)",
        ]),
        ("winner_unit", [
            r"(?:第一中标候选人|第一成交候选人|第一候选人)[：:]\s*([^\s，,；;。\n（）(]{2,60})",
            r"(?:\d+[、.]\s*)?中标人[：:]\s*([^\s，,；;。\n（）(]{2,60})",
            r"(?:\d+[、.]\s*)?成交(?:供应)?商[：:]\s*([^\s，,；;。\n（）(]{2,60})",
            r"(?:\d+[、.]\s*)?竞得人[：:]\s*([^\s，,；;。\n（）(]{2,60})",
            r"(?:\d+[、.]\s*)?受让人[：:]\s*([^\s，,；;。\n（）(]{2,60})",
        ]),
    ]
    for field, pats in kw_patterns:
        for p in pats:
            m = re.search(p, text)
            if m:
                v = m.group(1).strip()
                if v and 2 <= len(v) <= 120:
                    if field == "deadline":
                        iso = _parse_dt_smart(v)
                        if iso:
                            out[field] = iso
                    elif field == "budget":
                        out[field] = v
                    else:
                        out[field] = v
                    break

    # --- B. 两列表兜底（少数地方交易网原文结构清晰） ---
    if not out.get("tenderee"):
        td = _extract_kv_from_table(content_html,
                                      ["招标人", "采购人", "采购单位", "招标单位",
                                       "采购人名称", "项目业主"])
        if td:
            out["tenderee"] = td
    if not out.get("agency"):
        ag = _extract_kv_from_table(content_html,
                                     ["招标代理机构", "代理机构", "采购代理"])
        if ag:
            out["agency"] = ag

    # --- C. 中标金额 / 成交价 ---
    # 优先表格列定位（土地挂牌「成交价（万元）」表头 + 数据行同列），最可靠
    wa = _table_column_amount(
        content_html,
        ("成交价", "成交金额", "成交总价", "中标金额", "中标价"))
    # 其次正则：只认"中标/成交/总价"，不认起始价/预算
    if wa is None:
        wa = _money_from_table(
            content_html,
            ["中标金额", "成交金额", "总成交金额", "中标价", "成交价",
             "成交总价", "总中标金额"],
            prefer_regex_over_table=True)
    if wa is not None and wa >= 1000:  # 过滤标书费/工本费
        out["win_amount"] = wa

    # --- D. 表格中标候选人兜底（少数地方交易网有标准候选人表格） ---
    if not out.get("winner_unit"):
        wu = _first_winner_from_table(content_html)
        if wu:
            out["winner_unit"] = wu

    return out


def _kw_match(text: str, patterns: list[str]) -> Optional[str]:
    """关键词正则兜底：匹配任意一个 pattern 返回 capture group 1"""
    for p in patterns:
        m = re.search(p, text)
        if m:
            v = m.group(1).strip()
            if v and 2 <= len(v) <= 120:
                return v
    return None


# ============================================================
# SourceSpec 注册表
# ============================================================

SOURCE_SPECS: Dict[str, Dict[str, Any]] = {
    "ccgp": {
        "name": "中国政府采购网",
        "extract": _extract_from_ccgp,
        "content_selectors": [  # 详情页正文容器（专用顺序）
            "div.main", "div.main_container", "div.content", "div.article",
        ],
    },
    "ggzy": {
        "name": "全国公共资源交易平台",
        "extract": _extract_from_ggzy,
        "content_selectors": [
            "div#mycontent", "div.detail_content", "div.detail",
            "div.content", "div.article",
        ],
    },
}


def get_extractor(source_code: str) -> Optional[Callable[[str, dict], dict]]:
    """取源站专用 extractor，源站无 spec 则返回 None（走通用正则 + AI）"""
    spec = SOURCE_SPECS.get(source_code)
    return spec["extract"] if spec else None


def extract_via_spec(source_code: str, content_html: str, raw: dict) -> dict:
    """对指定源站跑专用 extractor，返回 {'field': value} 字典（可能空）

    crawl.py 入库前用：fields = extract_via_spec(source_code, html, raw)
    for f, v in fields.items():
        if not existing.get(f) and v:
            existing[f] = v
    """
    extractor = get_extractor(source_code)
    if not extractor:
        return {}
    try:
        return extractor(content_html or "", raw or {})
    except Exception as e:
        logger.warning("[source_spec] %s extractor 异常: %s", source_code, e)
        return {}


def fill_gaps_via_spec(source_code: str, content_html: str, current: dict) -> dict:
    """专用 extractor 只填空字段，不覆盖已有的

    current = {"tenderee": None, "winner_unit": "XX已抓到", ...}
    返回的 dict 里只会含 current 中为 None/空/0 的字段
    """
    fields = extract_via_spec(source_code, content_html, current)
    out: dict = {}
    for f, v in fields.items():
        if v is None:
            continue
        cur = current.get(f)
        # 已有的值不覆盖：None / "" / 0 / 空字符串 才算空
        if cur is None or cur == "" or cur == 0:
            out[f] = v
    return out
