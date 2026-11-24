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
    """dict_notice_type 的 name -> id 映射，按连接缓存（避免逐条查库）"""
    cached = getattr(conn, "_notice_type_map", None)
    if isinstance(cached, dict) and cached:
        return cached
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, name FROM dict_notice_type")
        type_map = {name: nid for nid, name in cur.fetchall()}
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
    """推断 proc_type"""
    if not title:
        return None
    blob = title + " " + (content_text or "")[:200]
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
                "人大", "政协", "委员会", "中共", "党委"]

SOE_KEYWORDS = ["集团", "有限责任", "股份有限", "国有", "央企", "国企",
                "银行", "保险", "证券", "电信", "移动", "联通", "国家电网",
                "中石油", "中石化", "中粮", "中化", "中铁", "中建", "中交",
                "邮政", "烟草", "盐业", "黄金", "中车", "北车", "南车"]

def infer_customer_group(tenderee: str, title: str = "") -> Optional[str]:
    """政务 / 国企 / 民企"""
    blob = (tenderee or "") + " " + (title or "")
    if not blob.strip():
        return None
    if any(kw in blob for kw in GOV_KEYWORDS):
        return "政务"
    if any(kw in blob for kw in SOE_KEYWORDS):
        return "国企"
    # 含有 "公司"、"企业" → 默认民企
    if "公司" in blob or "企业" in blob or "厂" in blob or "工作室" in blob:
        return "民企"
    return None


# =====================================================
# Step 6: 行业推断
# =====================================================

# 基于 dict_industry 现有数据，先查有哪些行业
def load_industries(conn) -> list[tuple[int, str, list[str]]]:
    """返回 [(id, name, 关键词列表), ...]"""
    cur = conn.cursor()
    # dict_industry 可能没有 keywords 列（老库），退化为用 name 匹配
    try:
        cur.execute("SELECT id, name, keywords FROM dict_industry WHERE status=1")
        rows = cur.fetchall()
        return [(r[0], r[1], (r[2] or "").split(",") if r[2] else [r[1]]) for r in rows]
    except Exception:
        conn.rollback()
        cur.execute("SELECT id, name FROM dict_industry WHERE status=1")
        return [(r[0], r[1], [r[1]]) for r in cur.fetchall()]
    finally:
        cur.close()

def infer_industry_id(title: str, content_text: str, industries: list) -> Optional[int]:
    """根据标题+内容关键词命中最多的行业"""
    if not title and not content_text:
        return None
    blob = (title or "") + " " + (content_text or "")[:500]
    best_id, best_score = None, 0
    for ind_id, ind_name, keywords in industries:
        score = sum(1 for kw in keywords if kw and kw in blob)
        if score > best_score:
            best_score = score
            best_id = ind_id
    return best_id


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

    return {
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
        "rows_processed": 0,
    }

    for bid_id in ids:
        cur.execute(
            "SELECT id, title, content, content_text, tenderee, publish_time, "
            "winner_publish_time, deadline, notice_type_id, procure_type, "
            "customer_group, industry_id "
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
                    "notice_type_id", "procure_type", "customer_group", "industry_id"):
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


if __name__ == "__main__":
    import sys
    dry_run = "--dry-run" in sys.argv
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
    if "--notice-type" in sys.argv:
        # 只回填公告类型（存量数据打标签）
        backfill_notice_type(limit=limit)
    else:
        clean_all_seed(limit=limit, dry_run=dry_run)
