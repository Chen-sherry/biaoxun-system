# -*- coding: utf-8 -*-
"""
bid_info_seed → bid_info 转正脚本
---------------------------------
从 Excel 合并种子表把 8239 行映射进正式业务表。
映射规则见 MAP 字典。
执行：python scripts/promote_seed_to_bid_info.py
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime
from decimal import Decimal

import pymysql

DB_CFG = dict(
    host="127.0.0.1", port=int(os.environ.get("DB_PORT", "3306")), user="root",
    password=os.environ.get("DB_PASSWORD", "12345"),
    database="bid_info", charset="utf8mb4",
)

# 种子源 source（bid_source 不存在时会 INSERT）
SEED_SOURCE = dict(
    name="Excel 种子数据（25年4-6月）",
    code="seed_excel_25h1",
    source_type=4,   # Excel
    base_url="e:\\标讯系统\\25年4-6月关键词招中标数据8.8.xlsx",
    list_url_rule=None,
    field_rules=None,
    status=1,
    description="从 25年4-6月关键词招中标数据8.8.xlsx 合并导入，含 14 个关键词 sheet，8239 行",
)

# 字段映射：正式表字段 ← (种子表字段, 转换函数)
# 正式表字段按 INSERT 顺序排列
MAP = [
    ("title",               "news_title",            lambda v: v),
    ("project_code",        "project_code",          lambda v: v or None),
    ("tenderee",            "purchase_unit",         lambda v: v or None),
    ("winner_unit",         "winner_unit",           lambda v: v or None),
    ("agency",              "agency_unit",           lambda v: v or None),
    ("procure_type",        "procure_type",          lambda v: v or None),
    ("region_code",         "region_id",             lambda v: v or None),     # 种子表 region_id 是代码
    ("publish_time",        "create_time",           lambda v: v),             # 用种子的录入时间当公告发布时间
    ("winner_publish_time", "win_time",              lambda v: v),             # 中标时间单独保留
    ("deadline",            "deadline",              lambda v: v),
    ("budget",              "tender_amount",         lambda v: str(v) if v is not None else None),  # DECIMAL → VARCHAR
    ("win_amount",          "win_amount",            lambda v: v),             # DECIMAL 直接
    ("source_url",          "original_link",         lambda v: v or None),
    ("dedup_key",           None,                    None),                    # 运行时生成
    ("customer_group",      "customer_group",        lambda v: v or None),
    ("winner_unit_type",    "winner_unit_type",      lambda v: v or None),
    ("source_id",           None,                    None),                    # 运行时填充
    ("status",              None,                    None),                    # 固定 1
]


def sha1(*parts) -> str:
    raw = "|".join(str(p or "") for p in parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def ensure_seed_source(cur):
    cur.execute("SELECT id FROM bid_source WHERE code=%s", (SEED_SOURCE["code"],))
    row = cur.fetchone()
    if row:
        print(f"[source] 已存在 id={row[0]}")
        return row[0]
    cols = ", ".join(SEED_SOURCE.keys())
    ph = ", ".join(["%s"] * len(SEED_SOURCE))
    cur.execute(f"INSERT INTO bid_source ({cols}) VALUES ({ph})", list(SEED_SOURCE.values()))
    print(f"[source] 已创建 id={cur.lastrowid}")
    return cur.lastrowid


def main():
    conn = pymysql.connect(**DB_CFG)
    cur = conn.cursor()

    # 0. 确保采集源存在
    source_id = ensure_seed_source(cur)
    conn.commit()

    # 1. 清正式表里从种子转正的那部分（保留其他 source 的）
    cur.execute("SELECT COUNT(*) FROM bid_info WHERE source_id=%s", (source_id,))
    before = cur.fetchone()[0]
    if before:
        print(f"[清目标数据] bid_info 中已有 {before} 行 source_id={source_id}，先 DELETE")
        cur.execute("DELETE FROM bid_info WHERE source_id=%s", (source_id,))
        conn.commit()

    # 2. 读种子表——直接全部拉到内存
    print("[读取] 从 bid_info_seed 全量拉取...")
    cur.execute("""
        SELECT news_title, project_code, purchase_unit, winner_unit, agency_unit,
               procure_type, region_id, create_time, win_time, deadline,
               tender_amount, win_amount, original_link, news_id,
               customer_group, winner_unit_type, source_keyword
        FROM bid_info_seed
        WHERE news_title IS NOT NULL AND news_title <> ''
        ORDER BY source_keyword, news_id
    """)
    all_rows = cur.fetchall()
    print(f"[读取] 共 {len(all_rows)} 行，开始分批写入...")

    batch_size = 500
    batch = []
    inserted = 0

    insert_cols = [m[0] for m in MAP]
    placeholders = ", ".join(["%s"] * len(insert_cols))
    col_str = ", ".join(f"`{c}`" for c in insert_cols)
    sql = f"INSERT IGNORE INTO bid_info ({col_str}) VALUES ({placeholders})"

    for row in all_rows:
        (news_title, project_code, purchase_unit, winner_unit, agency_unit,
         procure_type, region_id, create_time, win_time, deadline,
         tender_amount, win_amount, original_link, news_id,
         customer_group, winner_unit_type, source_keyword) = row

        dedup_key = sha1(source_keyword, news_id, news_title)   # 用种子业务主键 news_id 确保跨批次唯一

        values = [
            news_title,
            project_code,
            purchase_unit,
            winner_unit,
            agency_unit,
            procure_type,
            region_id,
            create_time,
            win_time,
            deadline,
            str(tender_amount) if tender_amount is not None else None,
            win_amount,
            original_link,
            dedup_key,
            customer_group,
            winner_unit_type,
            source_id,
            1,  # status=1 已发布
        ]
        batch.append(values)

        if len(batch) >= batch_size:
            cur.executemany(sql, batch)
            conn.commit()
            inserted += cur.rowcount
            print(f"  批次 +{len(batch)} → 新增 {cur.rowcount}（忽略重复）累计 {inserted}")
            batch = []

    if batch:
        cur.executemany(sql, batch)
        conn.commit()
        inserted += cur.rowcount
        print(f"  批次 +{len(batch)} → 新增 {cur.rowcount} 累计 {inserted}")

    # 4. 验证
    cur.execute("SELECT COUNT(*) FROM bid_info")
    total_now = cur.fetchone()[0]
    cur.execute("SELECT procure_type, COUNT(*) FROM bid_info GROUP BY procure_type ORDER BY COUNT(*) DESC")
    by_procure = cur.fetchall()
    cur.execute("SELECT MIN(publish_time), MAX(publish_time), MIN(winner_publish_time), MAX(winner_publish_time) FROM bid_info")
    time_range = cur.fetchone()

    cur.close()
    conn.close()

    print("\n" + "=" * 60)
    print(f"[完成] 转正 {inserted} 行，bid_info 合计 {total_now} 行")
    print(f"  正式表 proc_type 分布：")
    for k, c in by_procure:
        print(f"    · {k or '(空)':<12} {c:>5}")
    print(f"  publish_time 范围: {time_range[0]} ~ {time_range[1]}")
    print(f"  winner_publish_time 范围: {time_range[2]} ~ {time_range[3]}")
    print("=" * 60)


if __name__ == "__main__":
    main()
