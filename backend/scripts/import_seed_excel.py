# -*- coding: utf-8 -*-
"""
Excel → bid_info_seed 合并导入脚本
---------------------------------
来源文件：25年4-6月关键词招中标数据8.8.xlsx
含 14 个 sheet：培训/人才/党性/红色/团建/新员工/场地/拓展/
                赋能营销/战训/团队建设/趣味运动会/团队拓展/考试
每个 sheet 约 1000 行，统一 31 列；合表后新增 source_keyword 标记来源。

执行方式：python scripts/import_seed_excel.py
连接：MySQL root / 12345 / 127.0.0.1:3306 / bid_info
"""
from __future__ import annotations

import hashlib
import os
import re
import sys
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Optional

import openpyxl
import pymysql

# ============== 配置 ==============
# Excel 位于项目包根目录（backend 的上一级）
EXCEL_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "25年4-6月关键词招中标数据8.8.xlsx",
)

DB_CFG = dict(
    host="127.0.0.1",
    port=int(os.environ.get("DB_PORT", "3306")),
    user="root",
    password=os.environ.get("DB_PASSWORD", "12345"),
    database="bid_info",
    charset="utf8mb4",
)

# Excel 列名 → 目标字段
COLUMN_MAP = {
    "新闻标题":             "news_title",
    "项目编号":             "project_code",
    "采购单位":             "purchase_unit",
    "中标单位":             "winner_unit",
    "招标金额":             "tender_amount",
    "中标金额":             "win_amount",
    "业务结构":             "business_structure",
    "招标时间":             "tender_time",
    "中标时间":             "win_time",
    "代理单位":             "agency_unit",
    "原文链接":             "original_link",
    "地区":                 "region_full",
    "省":                   "province",
    "市":                   "city",
    "招采类型":             "procure_type",
    "公告类型":             "notice_type",
    "专业":                 "major",
    "地区ID":               "region_id",
    "新闻ID":               "news_id",
    "创建时间":             "create_time",
    "截止时间":             "deadline",
    "预计采购时间":         "expected_purchase_time",
    "意项链接":             "intention_link",
    "长ID":                 "long_id",
    "市场感知链接":         "market_perception_link",
    "重复":                 "duplicate",
    "客群":                 "customer_group",
    "运营商客群":           "operator_customer_group",
    "中标单位类型":         "winner_unit_type",
    "市属":                 "city_level",
    "阶段":                 "stage",
}

# ============== 工具 ==============

BAD_DATE_TOKENS = {"1900/1/1", "1900-01-01", "1900/1/1 0:00:00"}


def clean_text(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.lower() == "none":
        return None
    return s


def parse_decimal(v: Any) -> Optional[Decimal]:
    if v is None or v == "":
        return None
    try:
        if isinstance(v, (int, float)):
            return Decimal(str(v)).quantize(Decimal("0.01"))
        s = re.sub(r"[,\s¥￥]", "", str(v))
        if not s:
            return None
        return Decimal(s).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        return None


def parse_datetime(v: Any) -> Optional[datetime]:
    if v is None or v == "":
        return None
    if isinstance(v, datetime):
        return v if v.year >= 1990 else None
    s = str(v).strip()
    if not s or s in BAD_DATE_TOKENS:
        return None
    # 常见格式尝试
    fmts = [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ]
    for f in fmts:
        try:
            dt = datetime.strptime(s, f)
            return dt if dt.year >= 1990 else None
        except ValueError:
            continue
    # openpyxl 有时给 Excel 日期序列号（datetime 对象前面已经兜住）
    return None


def make_raw_hash(title: str, keyword: str, news_id: str) -> str:
    raw = f"{keyword}|{news_id or ''}|{title or ''}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


# ============== 主逻辑 ==============

def load_all_rows():
    wb = openpyxl.load_workbook(EXCEL_PATH, data_only=True, read_only=True)
    print(f"[读取] Excel 共 {len(wb.sheetnames)} 个 sheet")

    all_rows: list[dict] = []
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        rows_iter = ws.iter_rows(values_only=True)
        try:
            headers = next(rows_iter)
        except StopIteration:
            print(f"  × {sheet_name}: 空 sheet，跳过")
            continue

        header_idx = {}
        for i, h in enumerate(headers):
            if h and str(h).strip() in COLUMN_MAP:
                header_idx[COLUMN_MAP[str(h).strip()]] = i

        skipped = 0
        loaded = 0
        for row in rows_iter:
            if row is None or all(c is None or str(c).strip() == "" for c in row):
                skipped += 1
                continue

            record: dict[str, Any] = {}
            for target_col, src_idx in header_idx.items():
                record[target_col] = row[src_idx] if src_idx < len(row) else None

            # 清洗 + 类型转换
            record["source_keyword"] = sheet_name
            record["news_title"] = clean_text(record.get("news_title"))
            record["project_code"] = clean_text(record.get("project_code"))
            record["purchase_unit"] = clean_text(record.get("purchase_unit"))
            record["winner_unit"] = clean_text(record.get("winner_unit"))
            record["tender_amount"] = parse_decimal(record.get("tender_amount"))
            record["win_amount"] = parse_decimal(record.get("win_amount"))
            record["business_structure"] = clean_text(record.get("business_structure"))
            record["tender_time"] = parse_datetime(record.get("tender_time"))
            record["win_time"] = parse_datetime(record.get("win_time"))
            record["agency_unit"] = clean_text(record.get("agency_unit"))
            record["original_link"] = clean_text(record.get("original_link"))
            record["region_full"] = clean_text(record.get("region_full"))
            record["province"] = clean_text(record.get("province"))
            record["city"] = clean_text(record.get("city"))
            record["procure_type"] = clean_text(record.get("procure_type"))
            record["notice_type"] = clean_text(record.get("notice_type"))
            record["major"] = clean_text(record.get("major"))
            record["region_id"] = clean_text(record.get("region_id"))
            record["news_id"] = clean_text(record.get("news_id"))
            record["create_time"] = parse_datetime(record.get("create_time"))
            record["deadline"] = parse_datetime(record.get("deadline"))
            record["expected_purchase_time"] = parse_datetime(record.get("expected_purchase_time"))
            record["intention_link"] = clean_text(record.get("intention_link"))
            record["long_id"] = clean_text(record.get("long_id"))
            record["market_perception_link"] = clean_text(record.get("market_perception_link"))
            record["duplicate"] = clean_text(record.get("duplicate"))
            record["customer_group"] = clean_text(record.get("customer_group"))
            record["operator_customer_group"] = clean_text(record.get("operator_customer_group"))
            record["winner_unit_type"] = clean_text(record.get("winner_unit_type"))
            record["city_level"] = clean_text(record.get("city_level"))
            record["stage"] = clean_text(record.get("stage"))
            record["raw_row_hash"] = make_raw_hash(
                record.get("news_title") or "",
                sheet_name,
                record.get("news_id") or "",
            )
            all_rows.append(record)
            loaded += 1

        print(f"  ✓ {sheet_name}: 载入 {loaded} 行，跳过空行 {skipped}")

    wb.close()
    print(f"[读取完成] 合计 {len(all_rows)} 行")
    return all_rows


def ensure_table(conn):
    """确保目标表存在，DDL 不在 import 脚本内，这里只检测"""
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema=%s AND table_name='bid_info_seed'",
        (DB_CFG["database"],),
    )
    exists = cur.fetchone()[0]
    cur.close()
    if not exists:
        raise SystemExit(
            "表 bid_info_seed 不存在，请先执行 backend/sql/02-bid_info_seed.sql 建表"
        )


def insert_batches(conn, rows, batch_size=500):
    if not rows:
        print("[导入] 无数据")
        return 0

    cols = list(rows[0].keys())
    placeholders = ", ".join(["%s"] * len(cols))
    col_list = ", ".join(f"`{c}`" for c in cols)

    sql = (
        f"INSERT IGNORE INTO bid_info_seed ({col_list}) VALUES ({placeholders})"
    )

    cur = conn.cursor()
    affected_total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i : i + batch_size]
        cur.executemany(sql, [tuple(r[c] for c in cols) for r in batch])
        conn.commit()
        affected_total += cur.rowcount
        print(f"  批次 {i // batch_size + 1}: 本批 {len(batch)} 行，新增 {cur.rowcount} 行（忽略重复）")

    cur.close()
    return affected_total


def main():
    if not os.path.exists(EXCEL_PATH):
        print(f"[错误] Excel 不存在：{EXCEL_PATH}")
        sys.exit(1)

    print("=" * 60)
    print("  bid_info_seed 合并导入工具")
    print("=" * 60)

    # 1. 读 Excel
    rows = load_all_rows()

    # 2. 连库
    conn = pymysql.connect(**DB_CFG)
    ensure_table(conn)

    # 3. 清表（避免重复导入）
    cur = conn.cursor()
    cur.execute("TRUNCATE TABLE bid_info_seed")
    conn.commit()
    cur.close()
    print("[清表] 已 TRUNCATE bid_info_seed")

    # 4. 分批 INSERT IGNORE
    added = insert_batches(conn, rows)

    # 5. 校验
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM bid_info_seed")
    total = cur.fetchone()[0]
    cur.execute(
        "SELECT source_keyword, COUNT(*) AS c FROM bid_info_seed GROUP BY source_keyword ORDER BY c DESC"
    )
    per_keyword = cur.fetchall()
    cur.execute(
        "SELECT procure_type, COUNT(*) AS c FROM bid_info_seed GROUP BY procure_type ORDER BY c DESC LIMIT 10"
    )
    by_procure = cur.fetchall()
    cur.execute(
        "SELECT MIN(win_time), MAX(win_time), MIN(tender_amount), MAX(tender_amount) FROM bid_info_seed"
    )
    stat = cur.fetchone()
    cur.close()
    conn.close()

    print("\n" + "=" * 60)
    print(f"[完成] 导入 {added} 行，表内合计 {total} 行")
    print(f"  按关键词分布：")
    for k, c in per_keyword:
        print(f"    · {k:<12} {c:>5} 行")
    print(f"  招采类型 TOP：")
    for k, c in by_procure:
        print(f"    · {str(k):<12} {c:>5} 行")
    print(f"  中标时间范围: {stat[0]}  ~  {stat[1]}")
    print(f"  招标金额范围: {stat[2]}  ~  {stat[3]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
