"""推送定时任务：每日汇总 + 到期预警 + 归档通知 + 自定义定时推送
全部从 push_template 读库渲染；执行时间存 schedule_time，beat 每 5 分钟自检，
到点（15 分钟窗口）且未发过才真正发 —— 后台改时间/启停即时生效，无需重启服务。
"""
import logging
from datetime import datetime, timedelta

from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _due_gate(db, code: str) -> tuple:
    """到点闸门：返回 (tpl, target) 表示应该执行；否则 (None, None)。
    处理：模板存在、已启用、当前在执行窗口内、本窗口未发过（防重）。"""
    from app.services.push_template_service import get_template, due_window, already_pushed

    tpl = get_template(db, code)
    if not tpl:
        logger.warning(f"[push] 模板 {code} 不存在，跳过")
        return None, None
    if not tpl.enabled:
        logger.info(f"[push] 模板 {code} 已停用，SKIP")
        return None, None
    target = due_window(db, tpl)
    if not target:
        return None, None  # 未到点（每 5 分钟都会来一次，正常静默）
    if already_pushed(db, tpl.id, target):
        return None, None  # 本窗口已发过
    return tpl, target


def _send(db, *, code: str, variables: dict, push_type: str = "scheduled",
          tpl=None) -> dict:
    """渲染 → 长度校验 → 发企微群 → 落记录（tpl 由 _due_gate 传入避免重复查询）"""
    from app.services.push_template_service import render_push_message, check_length, save_record
    from app.services.wecom_push import send_markdown_sync

    msg = render_push_message(code, variables, db=db)
    if not msg:
        logger.warning(f"[push] 模板 {code} 不存在，跳过")
        return {"pushed": False, "reason": "template_missing", "code": code}
    if not msg["enabled"]:
        logger.info(f"[push] 模板 {code} 已停用，SKIP")
        return {"pushed": False, "reason": "template_disabled", "code": code}

    length = check_length(msg["full"])
    if not length["ok"]:
        save_record(db, push_type=push_type, status=1, preview=0,
                    template_id=msg["template_id"], subject=msg["title"],
                    error_msg=f"内容超长 {length['bytes']}/{length['limit']} 字节")
        db.commit()
        logger.error(f"[push] 模板 {code} 渲染超长 {length['bytes']} 字节，未发送")
        return {"pushed": False, "reason": "too_long", "bytes": length["bytes"]}

    result = send_markdown_sync(msg["title"], msg["content"])
    ok = bool(result and result.get("errcode") == 0)
    err = None if ok else str(result or "send_failed")[:500]
    save_record(db, push_type=push_type, status=0 if ok else 1, preview=0,
                template_id=msg["template_id"], subject=msg["title"], error_msg=err)
    db.commit()
    logger.info(f"[push] 模板 {code} 发送 pushed={ok}")
    return {"pushed": ok, "code": code, "bytes": length["bytes"]}


# ============================================================
# 每天 08:00 每日汇总（原占位 → 真实实现）
# ============================================================

@celery_app.task(name="app.tasks.push_tasks.push_daily_subscriptions")
def push_daily_subscriptions():
    from app.database import SessionLocal
    from app.models.bid import BidInfo

    db = SessionLocal()
    try:
        tpl, _target = _due_gate(db, "daily_summary")
        if not tpl:
            return {"pushed": False, "reason": "not_due_or_disabled"}

        # 口径（2026-11-26 用户指定格式）：近 24 小时新增 → 「今日新增X条标讯 + 最新3条带链接」
        since = datetime.now() - timedelta(hours=24)
        rows = (
            db.query(BidInfo)
            .filter(BidInfo.status == 1, BidInfo.created_at >= since)
            .order_by(BidInfo.publish_time.desc())
            .all()
        )
        bid_list = "\n".join(
            f"- [{(r.title or '')[:60]}]({r.source_url or ''})" for r in rows[:3]
        ) or "（无）"

        return _send(db, code="daily_summary", variables={
            "date": datetime.now().strftime("%Y-%m-%d"),
            "count": str(len(rows)),
            "bid_list": bid_list,
        })
    except Exception as e:
        logger.exception(f"[push] daily summary failed: {e}")
        return {"pushed": False, "error": str(e)}
    finally:
        db.close()


# ============================================================
# 每天 09:00 到期预警（改造为读库渲染）
# ============================================================

@celery_app.task(name="app.tasks.push_tasks.send_expiring_bid_daily")
def send_expiring_bid_daily():
    from app.config import settings
    from app.database import SessionLocal
    from app.models.bid import BidInfo

    db = SessionLocal()
    try:
        tpl, _target = _due_gate(db, "expiring_alert")
        if not tpl:
            return {"pushed": False, "reason": "not_due_or_disabled"}

        now = datetime.now()
        cutoff = now + timedelta(hours=24)
        rows = (
            db.query(BidInfo)
            .filter(
                BidInfo.status == 1,
                BidInfo.deadline.isnot(None),
                BidInfo.deadline >= now,
                BidInfo.deadline <= cutoff,
            )
            .order_by(BidInfo.deadline.asc())
            .all()
        )
        count = len(rows)
        send_zero = getattr(settings, "wecom_send_zero_summary", False)

        # 0 条默认不发（防打扰群），WECOM_SEND_ZERO_SUMMARY=true 可开
        if count == 0 and not send_zero:
            logger.info("[push] expiring summary: 0 due bids, SKIP")
            return {"count": 0, "pushed": False, "skipped_reason": "no_expiring_bids"}

        bid_list = "\n".join(
            f"- [{(r.title or '')[:40]}]({r.source_url or ''}) · "
            f"{r.deadline.strftime('%m-%d %H:%M') if r.deadline else '?'}"
            for r in rows[:15]
        ) or "（无）"

        return _send(db, code="expiring_alert", variables={
            "date": now.strftime("%Y-%m-%d"),
            "count": str(count),
            "bid_list": bid_list,
        })
    except Exception as e:
        logger.exception(f"[push] send_expiring_bid_daily failed: {e}")
        return {"count": 0, "pushed": False, "error": str(e)}
    finally:
        db.close()


# ============================================================
# 每天 02:00 归档（原纯数据任务 → 归档后发 archive_notice，已定 Q3=发）
# ============================================================

@celery_app.task(name="app.tasks.push_tasks.push_hourly_subscriptions")
def push_hourly_subscriptions():
    """每小时推送（Q7 已定：本期不启用，保留占位）"""
    return {"status": "placeholder"}


@celery_app.task(name="app.tasks.push_tasks.push_custom_templates")
def push_custom_templates():
    """自定义定时推送：遍历 kind=custom 且启用的模板，到点窗口内逐个发送。
    变量支持 {date} 与 {count}（近 24 小时新增标讯数）。"""
    from app.database import SessionLocal
    from app.models.push import PushTemplate
    from app.services.push_template_service import due_window, already_pushed

    db = SessionLocal()
    try:
        rows = (db.query(PushTemplate)
                .filter(PushTemplate.kind == "custom", PushTemplate.enabled == 1)
                .all())
        results = []
        for tpl in rows:
            target = due_window(db, tpl)
            if not target:
                continue
            if already_pushed(db, tpl.id, target):
                continue

            # {count} = 近 24 小时新增标讯数
            from app.models.bid import BidInfo
            since = datetime.now() - timedelta(hours=24)
            count = db.query(BidInfo.id).filter(
                BidInfo.status == 1, BidInfo.created_at >= since).count()

            r = _send(db, code=tpl.code, variables={
                "date": datetime.now().strftime("%Y-%m-%d"),
                "count": str(count),
            }, push_type="scheduled", tpl=tpl)
            results.append({"code": tpl.code, **r})
        return {"checked": len(rows), "results": results}
    except Exception as e:
        logger.exception(f"[push] custom templates failed: {e}")
        return {"error": str(e)}
    finally:
        db.close()


@celery_app.task(name="app.tasks.push_tasks.send_email")
def send_email(to_addr: str, subject: str, html_body: str):
    """发送单封邮件（底层 SMTP，占位）"""
    return {"to": to_addr, "status": "placeholder"}
