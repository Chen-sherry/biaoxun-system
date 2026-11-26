# -*- coding: utf-8 -*-
"""回填 ggzy 占位正文：对 content_text 过短的记录重走三跳详情抓取

ggzy 的 a/ 壳页只有标题，b/ 页 #mycontent 是「公示内容」占位，
真实正文在 b/ 页「原文链接地址」指向的源站（三跳）。本脚本按此链路重抓并补字段。

用法: python refetch_ggzy_detail.py [--limit 0] [--sleep 0.5]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
from datetime import datetime

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (_BACKEND_ROOT, os.path.dirname(os.path.abspath(__file__))):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.services.crawl import _ggzy_detail  # noqa: E402
from app.services.data_clean import (  # noqa: E402
    strip_html, infer_industry_id, infer_procure_type, load_industries,
)
from fetch_missing_content import extract_deadline  # noqa: E402

MIN_TEXT = 50          # content_text 少于这个字数视为占位
_EXCLUDE_BEFORE = ("售卖", "获取", "发售", "下载", "购买", "报名", "注册")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=0.5)
    args = ap.parse_args()

    import pymysql
    from app.config import settings
    conn = pymysql.connect(host=settings.db_host, port=int(settings.db_port),
                           user=settings.db_user, password=settings.db_password,
                           database=settings.db_name, charset=settings.db_charset,
                           connect_timeout=10)
    cur = conn.cursor()

    sql = """SELECT b.id, b.title, b.source_url FROM bid_info b
             JOIN bid_source s ON s.id=b.source_id
             WHERE s.code='ggzy'
               AND b.content IS NOT NULL AND b.content<>''
               AND CHAR_LENGTH(b.content_text) < %d
               AND b.source_url IS NOT NULL AND b.source_url<>''
             ORDER BY b.id""" % MIN_TEXT
    if args.limit:
        sql += " LIMIT %d" % args.limit
    cur.execute(sql)
    rows = cur.fetchall()
    print("[待回填] %d 条" % len(rows))
    if not rows:
        return 0

    industries = load_industries(conn)
    ok = fail = 0

    for rid, title, url in rows:
        raw = None
        try:
            raw = _ggzy_detail(url, str(rid))
        except Exception as e:
            print("  [%s] 抓取异常: %s" % (rid, e))
        if not raw or len(raw.get("content_text") or "") < MIN_TEXT:
            fail += 1
            print("  [%s] 仍为占位，跳过" % rid)
            time.sleep(args.sleep)
            continue

        text = raw["content_text"]
        flat = re.sub(r"\s+", " ", text)

        cur.execute("""SELECT project_code, deadline, procure_type, industry_id
                       FROM bid_info WHERE id=%s""", (rid,))
        pc, dl, pt, iid = cur.fetchone()

        # 只补空，不覆盖已有值
        if not pc and raw.get("project_code"):
            pc = raw["project_code"]
        if dl is None:
            dl = extract_deadline(flat)
        if not pt:
            pt = infer_procure_type(title or "", flat)
        new_iid = infer_industry_id(title or "", text[:500], industries)
        if new_iid:
            iid = new_iid

        cur.execute(
            """UPDATE bid_info SET content=%s, content_text=%s, project_code=%s,
                      deadline=%s, procure_type=%s, industry_id=%s,
                      source_url=COALESCE(NULLIF(%s,''), source_url)
               WHERE id=%s""",
            (raw.get("content"), text, pc, dl, pt, iid,
             raw.get("source_url", ""), rid))
        conn.commit()
        ok += 1
        print("  [%s] OK %d 字 -> %s" % (rid, len(text), title[:34]))
        time.sleep(args.sleep)

    print("\n[完成] 成功 %d / 失败 %d" % (ok, fail))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
