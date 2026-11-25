# -*- coding: utf-8 -*-
"""补抓正文 + 从正文提取空字段

针对 bid_info 中「有 source_url 但无 content」的记录：
  1. 抓取原始 HTML → content / content_text
  2. 从正文补空字段：project_code / deadline / region_code / procure_type
  3. 用真实正文重推 industry_id（原先只能用标题推）

幂等可续跑：只处理 content 为空的记录，抓过的自动跳过。

用法:
  python fetch_missing_content.py --limit 200          # 先跑一小批看效果
  python fetch_missing_content.py                      # 全量
  python fetch_missing_content.py --workers 4 --sleep 0.5
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Optional

import httpx

_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND_ROOT not in sys.path:
    sys.path.insert(0, _BACKEND_ROOT)

from app.services.data_clean import (  # noqa: E402
    strip_html, clean_date, infer_industry_id, infer_procure_type, load_industries)

DEFAULT_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
}


# ---------------------------------------------------------------- 抓取

def detect_charset(raw: bytes) -> str:
    """从 HTML 头部猜编码：meta charset > HTTP 头 > utf-8 > gbk"""
    head = raw[:4000].decode("ascii", errors="ignore").lower()
    m = re.search(r"charset=[\"']?([\w-]+)", head)
    if m:
        cs = m.group(1)
        if cs in ("gb2312", "gbk", "gb18030", "utf-8", "utf8", "big5"):
            return "gb18030" if cs in ("gb2312", "gbk") else cs
    for cs in ("utf-8", "gb18030"):
        try:
            raw.decode(cs)
            return cs
        except (UnicodeDecodeError, LookupError):
            continue
    return "utf-8"


def fetch(url: str, timeout: float = 20.0, retries: int = 2) -> Optional[str]:
    for attempt in range(retries + 1):
        try:
            with httpx.Client(timeout=timeout, headers=DEFAULT_HEADERS,
                              follow_redirects=True, verify=False) as client:
                r = client.get(url)
            if r.status_code == 200 and r.content:
                return r.content.decode(detect_charset(r.content), errors="replace")
            if r.status_code in (404, 410, 403):
                return None            # 硬失败，不再重试
        except Exception:
            if attempt == retries:
                return None
            time.sleep(2 * (attempt + 1))
    return None


# ---------------------------------------------------------------- 提取

# 编号值：字母/数字/括号/连字符等，可带「号」尾；不含中文，避免吞掉「二、项目名称」
_CODE_VAL = r"([\[\(（]?[A-Za-z0-9][A-Za-z0-9\-_（）()\[\]\.\/]{1,44}号?)"
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
_DEADLINE_LABELS = ("提交投标文件截止时间", "投标文件递交截止时间", "投标截止时间",
                   "递交投标文件截止时间", "响应文件递交截止时间", "磋商截止时间",
                   "报价截止时间", "截止时间", "投标截止日期", "开标时间")
_CN_DATE = r"(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日\s*(?:\d{1,2}\s*[:：]\s*\d{2})?)"
_ISO_DATE = r"(\d{4}[-/]\d{1,2}[-/]\d{1,2}\s*\d{1,2}[:：]\d{2}(?::\d{2})?)"

_REGION_RES = [
    re.compile(r"行政区域[：:]\s*([一-龥]{2,10}?(?:省|市|自治区|特别行政区))"),
    re.compile(r"项目所在地[：:]\s*([一-龥]{2,10}?(?:省|市|自治区))"),
    re.compile(r"采购单位地址[：:]\s*(?:[一-龥]{2,6}省|)?([一-龥]{2,6}市)"),
]


def extract_project_code(text: str) -> Optional[str]:
    for rx in _PROJECT_CODE_RES:
        m = rx.search(text)
        if not m:
            continue
        v = m.group(1).strip().rstrip("。；;，,、")
        if len(v) >= 5 and _HAS_ALNUM.search(v):
            return v
    return None


def _parse_cn_date(s: str) -> Optional[datetime]:
    s = re.sub(r"\s+", "", s).replace("：", ":")
    s = s.replace("年", "-").replace("月", "-").replace("日", "")
    s = re.sub(r"(\d)-(\d)(?=\d)", r"\1-0\2", s)
    for fmt in ("%Y-%m-%d%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def extract_deadline(text: str) -> Optional[datetime]:
    for label in _DEADLINE_LABELS:
        idx = text.find(label)
        if idx < 0:
            continue
        window = text[idx: idx + 120]
        for rx in (_CN_DATE, _ISO_DATE):
            m = re.search(rx, window)
            if m:
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


# ---------------------------------------------------------------- 主流程

def load_region_index(cur) -> dict:
    """省份名 -> code（含简称）"""
    cur.execute("SELECT code, name FROM dict_region WHERE level=1")
    idx = {name: code for code, name in cur.fetchall()}
    alias = {"内蒙古自治区": "内蒙古", "广西壮族自治区": "广西", "西藏自治区": "西藏",
             "宁夏回族自治区": "宁夏", "新疆维吾尔自治区": "新疆",
             "香港特别行政区": "香港", "澳门特别行政区": "澳门"}
    for full, short in alias.items():
        if full in idx:
            idx[short] = idx[full]
    return idx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="最多处理多少条（0=全部）")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--sleep", type=float, default=0.4, help="每个域名的最小间隔秒数")
    ap.add_argument("--commit-every", type=int, default=20)
    ap.add_argument("--reextract", action="store_true",
                    help="不抓取，只对已有正文但缺字段的记录重跑提取")
    args = ap.parse_args()

    import pymysql
    from app.config import settings
    conn = pymysql.connect(host=settings.db_host, port=int(settings.db_port),
                           user=settings.db_user, password=settings.db_password,
                           database=settings.db_name, charset=settings.db_charset,
                           connect_timeout=10)
    cur = conn.cursor()

    if args.reextract:
        sql = """SELECT id, title, content FROM bid_info
                 WHERE content IS NOT NULL AND content<>''
                   AND (project_code IS NULL OR project_code=''
                        OR deadline IS NULL) ORDER BY id"""
    else:
        sql = """SELECT id, title, source_url FROM bid_info
                 WHERE (content IS NULL OR content='')
                   AND source_url IS NOT NULL AND source_url<>'' ORDER BY id"""
    if args.limit:
        sql += f" LIMIT {int(args.limit)}"
    cur.execute(sql)
    rows = cur.fetchall()
    print(f"[待抓] {len(rows)} 条（workers={args.workers} sleep={args.sleep}）")
    if not rows:
        return 0

    industries = load_industries(conn)
    region_idx = load_region_index(cur)
    print(f"[字典] 行业 {len(industries)}  省级地区 {len(region_idx)}")

    host_locks: dict[str, threading.Lock] = {}
    host_next: dict[str, float] = {}
    global_lock = threading.Lock()
    stats = {"ok": 0, "fail": 0, "pc": 0, "dl": 0, "rg": 0, "ind": 0}
    pending: list = []

    def grab_host(url: str) -> str:
        try:
            return url.split("/")[2]
        except Exception:
            return ""

    def work(item):
        if args.reextract:
            rid, title, stored = item
            return rid, title, stored          # 直接用库里已有的 HTML
        rid, title, url = item
        host = grab_host(url)
        lock = host_locks.setdefault(host, threading.Lock())
        with lock:
            wait = host_next.get(host, 0.0) - time.time()
            if wait > 0:
                time.sleep(wait)
            host_next[host] = time.time() + args.sleep
            html = fetch(url)
        return rid, title, html

    def flush():
        if not pending:
            return
        cur.executemany(
            """UPDATE bid_info SET content=%s, content_text=%s, project_code=%s,
                      deadline=%s, region_code=%s, procure_type=%s, industry_id=%s
               WHERE id=%s""", pending)
        conn.commit()
        pending.clear()

    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = [ex.submit(work, r) for r in rows]
        for fut in as_completed(futs):
            rid, title, html = fut.result()
            done += 1
            if not html:
                stats["fail"] += 1
                if done % 100 == 0:
                    print(f"  [{done}/{len(rows)}] 成功 {stats['ok']} 失败 {stats['fail']}")
                continue

            text = strip_html(html)
            if not text:
                stats["fail"] += 1
                continue
            stats["ok"] += 1
            # 提取用压平副本：标签与值之间可能夹换行/制表符
            flat = re.sub(r"\s+", " ", text)

            cur.execute("""SELECT project_code, deadline, region_code, procure_type,
                                  industry_id FROM bid_info WHERE id=%s""", (rid,))
            pc, dl, rc, pt, iid = cur.fetchone()

            if not pc:
                npc = extract_project_code(flat)
                if npc:
                    pc, stats["pc"] = npc, stats["pc"] + 1
            if dl is None:
                ndl = extract_deadline(flat)
                if ndl:
                    dl, stats["dl"] = ndl, stats["dl"] + 1
            if not rc or rc == "-1":
                nname = extract_region_name(flat)
                if nname and nname in region_idx:
                    rc, stats["rg"] = region_idx[nname], stats["rg"] + 1
            if not pt:
                npt = infer_procure_type(title or "", flat)
                if npt:
                    pt = npt
            # 用真实正文重推行业
            niid = infer_industry_id(title or "", text[:500], industries)
            if niid and niid != iid:
                stats["ind"] += 1
                iid = niid

            pending.append((html, text, pc, dl, rc, pt, iid, rid))
            if len(pending) >= args.commit_every:
                flush()
                el = time.time() - t0
                rate = done / el if el else 0
                eta = (len(rows) - done) / rate / 60 if rate else 0
                print(f"  [{done}/{len(rows)}] 成功 {stats['ok']} 失败 {stats['fail']} "
                      f"| 项目编号 +{stats['pc']} 截止 +{stats['dl']} 地区 +{stats['rg']} "
                      f"行业改 {stats['ind']} | {rate:.1f} 条/秒 剩 {eta:.0f} 分钟")

    flush()
    el = time.time() - t0
    print(f"\n[完成] 用时 {el/60:.1f} 分钟")
    print(f"  成功 {stats['ok']} / 失败 {stats['fail']}")
    print(f"  项目编号 +{stats['pc']}   投标截止 +{stats['dl']}   地区 +{stats['rg']}   行业改判 {stats['ind']}")
    conn.close()
    return 0


if __name__ == "__main__":
    import urllib3
    urllib3.disable_warnings()
    sys.exit(main())
