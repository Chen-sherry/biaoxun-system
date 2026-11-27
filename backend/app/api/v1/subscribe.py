"""订阅管理 — 用户自己的 CRUD + admin 全量管理"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.subscribe import BidSubscribe
from app.models.user import SysUser
from app.api.deps import get_current_user, get_current_user_optional, require_role, require_member
from app.utils.response import ApiResponse, PageData

router = APIRouter(prefix="/subscribes")


def _to_dict(s: BidSubscribe, username: Optional[str] = None) -> dict:
    """把 BidSubscribe ORM 转成干净 dict。username 由 JOIN 预先查出，
    避免 ORM 没有定义 user backref 时 s.user 抛 AttributeError。"""
    return {
        "id": s.id,
        "user_id": s.user_id,
        "username": username,
        "keyword": s.keyword,
        "region_code": s.region_code,
        "industry_id": s.industry_id,
        "notice_type_id": s.notice_type_id,
        "push_email": bool(s.push_email),
        "push_wechat": bool(s.push_wechat),
        "frequency": s.frequency,
        "last_push_at": s.last_push_at.isoformat() if s.last_push_at else None,
        "status": s.status,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


# ===== 用户自己的订阅 =====

@router.get("/mine", summary="我的订阅列表（登录用户）")
def list_my_subscribes(
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_member(1)),
):
    items = (
        db.query(BidSubscribe)
        .filter(BidSubscribe.user_id == user.id)
        .order_by(BidSubscribe.id.desc())
        .all()
    )
    return ApiResponse.ok([_to_dict(s, username=user.username) for s in items])


class SubscribeIn(BaseModel):
    keyword: str
    region_code: Optional[str] = None
    industry_id: Optional[int] = None
    notice_type_id: Optional[int] = None
    push_email: bool = True
    push_wechat: bool = False
    frequency: str = "daily"
    status: int = 1


@router.post("", summary="新增订阅")
def create_subscribe(
    payload: SubscribeIn,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_member(1)),
):
    from app.services.subscribe_service import (
        get_user_max_subscribe, count_active_subscribes,
    )
    from datetime import datetime as _dt

    keyword = (payload.keyword or "").strip()
    if not keyword:
        return ApiResponse.fail(msg="关键词不能为空")

    max_sub = get_user_max_subscribe(db, user.id)
    used = count_active_subscribes(db, user.id)
    if used >= max_sub:
        return ApiResponse.fail(
            msg=f"当前套餐最多可创建 {max_sub} 个订阅，请升级会员后再试"
        )

    data = payload.model_dump()
    data["keyword"] = keyword
    sub = BidSubscribe(**data, user_id=user.id, last_push_at=_dt.now())
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return ApiResponse.ok(_to_dict(sub), msg="订阅创建成功")


_EDITABLE_FIELDS = {
    "keyword", "region_code", "industry_id", "notice_type_id",
    "push_email", "push_wechat", "frequency", "status",
}


@router.put("/{subscribe_id}", summary="修改订阅")
def update_subscribe(
    subscribe_id: int,
    payload: dict,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_member(1)),
):
    sub = db.query(BidSubscribe).filter(
        BidSubscribe.id == subscribe_id, BidSubscribe.user_id == user.id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    for k, v in payload.items():
        if k in _EDITABLE_FIELDS:
            setattr(sub, k, v)
    if not (sub.keyword or "").strip():
        return ApiResponse.fail(msg="关键词不能为空")
    db.commit()
    db.refresh(sub)
    return ApiResponse.ok(_to_dict(sub), msg="修改成功")


@router.delete("/{subscribe_id}", summary="删除订阅")
def delete_subscribe(
    subscribe_id: int,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_member(1)),
):
    sub = db.query(BidSubscribe).filter(
        BidSubscribe.id == subscribe_id, BidSubscribe.user_id == user.id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    db.delete(sub)
    db.commit()
    return ApiResponse.ok(msg="删除成功")


@router.post("/{subscribe_id}/push-now", summary="立即推送我的订阅（邮件）")
def push_my_subscribe_now(
    subscribe_id: int,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_member(1)),
):
    from app.services.subscribe_service import push_subscribe

    sub = db.query(BidSubscribe).filter(
        BidSubscribe.id == subscribe_id, BidSubscribe.user_id == user.id
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    r = push_subscribe(db, sub, ignore_last_push=True, trigger="manual")
    if r.get("sent"):
        return ApiResponse.ok(r, msg=f"已发送，命中 {r['matched']} 条")
    reason_msg = {
        "no_bids": "没有匹配到标讯",
        "email_disabled": "该订阅未开启邮件推送",
        "no_email": "账号未绑定邮箱，请先补充邮箱",
        "send_failed": "邮件发送失败（SMTP 未配置或异常）",
    }.get(r.get("reason"), "未发送")
    return ApiResponse.ok(r, msg=reason_msg)


@router.get("/my-records", response_model=ApiResponse, summary="我的推送记录")
def my_push_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_member(1)),
):
    from app.models.push import PushRecord

    q = db.query(PushRecord).filter(
        PushRecord.user_id == user.id,
        PushRecord.push_type == "subscribe",
        PushRecord.preview == 0,
    )
    total = q.count()
    rows = q.order_by(PushRecord.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

    # 批量取出命中标讯的简要信息（不查 TEXT 大字段）
    all_ids = set()
    for r in rows:
        if r.bid_ids:
            all_ids.update(int(x) for x in r.bid_ids.split(",") if x.strip().isdigit())
    from app.models.bid import BidInfo
    bid_map = {}
    if all_ids:
        brief_cols = db.query(
            BidInfo.id, BidInfo.title, BidInfo.publish_time, BidInfo.deadline, BidInfo.source_url
        ).filter(BidInfo.id.in_(all_ids)).all()
        bid_map = {b.id: b for b in brief_cols}

    items = []
    for r in rows:
        ids = [int(x) for x in r.bid_ids.split(",") if x.strip().isdigit()] if r.bid_ids else []
        bids = []
        for bid_id in ids:
            b = bid_map.get(bid_id)
            if b:
                bids.append({
                    "id": b.id,
                    "title": b.title,
                    "publish_time": b.publish_time.isoformat() if b.publish_time else None,
                    "deadline": b.deadline.isoformat() if b.deadline else None,
                    "source_url": b.source_url,
                })
        items.append({
            "id": r.id,
            "subscribe_id": r.subscribe_id,
            "channel": r.channel,
            "recipient": r.recipient,
            "subject": r.subject,
            "status": r.status,
            "error_msg": r.error_msg,
            "push_time": r.push_time.isoformat() if r.push_time else None,
            "bids": bids,
        })
    return ApiResponse.ok(PageData(total=total, page=page, page_size=page_size, items=items).model_dump())


# ===== Admin 全量管理 =====

def _match_bids(db: Session, s: BidSubscribe, days: int = 7, limit: int = 50,
                ignore_last_push: bool = False):
    """按订阅条件匹配标讯（委托公共实现 subscribe_service.match_bids）。"""
    from app.services.subscribe_service import match_bids
    return match_bids(db, s, days=days, limit=limit, ignore_last_push=ignore_last_push)


def _bid_brief(b) -> dict:
    return {
        "id": b.id,
        "title": b.title,
        "notice_type_id": b.notice_type_id,
        "region_code": b.region_code,
        "publish_time": b.publish_time.isoformat() if b.publish_time else None,
        "deadline": b.deadline.isoformat() if b.deadline else None,
        "source_url": b.source_url,
    }


@router.get("/{subscribe_id}/preview", summary="admin：该订阅的匹配标讯预览（U2）")
def admin_preview_subscribe(
    subscribe_id: int,
    days: int = 7,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "ops")),
):
    sub = db.query(BidSubscribe).filter(BidSubscribe.id == subscribe_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    rows = _match_bids(db, sub, days=days, ignore_last_push=True)
    return ApiResponse.ok({
        "subscribe": _to_dict(sub),
        "total": len(rows),
        "days": days,
        "items": [_bid_brief(b) for b in rows],
    })


@router.post("/{subscribe_id}/push", summary="admin：立即推送该订阅（U3，本期生成记录标记通道待接入）")
def admin_push_subscribe(
    subscribe_id: int,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_role("admin")),
):
    from app.services.push_template_service import save_record

    sub = db.query(BidSubscribe).filter(BidSubscribe.id == subscribe_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    rows = _match_bids(db, sub, ignore_last_push=True)
    # Q2=C：专用企微机器人通道后接，本期只生成记录 + 标记未实际发送
    rec_id = save_record(
        db, push_type="subscribe", preview=0, subscribe_id=sub.id,
        user_id=sub.user_id, operator_id=user.id, status=1,
        subject=f"订阅推送：{sub.keyword or '(无关键词)'}",
        bid_ids=[b.id for b in rows],
        error_msg="通道待接入，未实际发送",
    )
    db.commit()
    return ApiResponse.ok({
        "record_id": rec_id, "matched": len(rows),
        "sent": False, "note": "通道待接入（Q2=C），已生成推送记录",
    }, msg=f"已生成推送记录，命中 {len(rows)} 条（通道待接入，未实际发送）")


class AdminSubscribeIn(BaseModel):
    keyword: Optional[str] = None
    region_code: Optional[str] = None
    industry_id: Optional[int] = None
    notice_type_id: Optional[int] = None
    frequency: Optional[str] = None
    status: Optional[int] = None


@router.put("/{subscribe_id}/admin", summary="admin：修改订阅筛选条件（U5）")
def admin_update_subscribe(
    subscribe_id: int,
    payload: AdminSubscribeIn,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "ops")),
):
    sub = db.query(BidSubscribe).filter(BidSubscribe.id == subscribe_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    for k, v in payload.dict(exclude_unset=True).items():
        setattr(sub, k, v)
    db.commit()
    db.refresh(sub)
    return ApiResponse.ok(_to_dict(sub), msg="订阅条件已更新")


@router.post("/batch-push", summary="admin：批量立即推送（U4，本期生成记录标记通道待接入）")
def admin_batch_push(
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_role("admin")),
):
    from app.services.push_template_service import save_record

    subs = db.query(BidSubscribe).filter(BidSubscribe.status == 1).all()
    results = []
    for sub in subs:
        rows = _match_bids(db, sub, ignore_last_push=True)
        rec_id = save_record(
            db, push_type="subscribe", preview=0, subscribe_id=sub.id,
            user_id=sub.user_id, operator_id=user.id, status=1,
            subject=f"订阅推送：{sub.keyword or '(无关键词)'}",
            bid_ids=[b.id for b in rows],
            error_msg="通道待接入，未实际发送",
        )
        results.append({"subscribe_id": sub.id, "matched": len(rows), "record_id": rec_id})
    db.commit()
    return ApiResponse.ok({
        "total_subs": len(results),
        "total_matched": sum(r["matched"] for r in results),
        "sent": False, "note": "通道待接入（Q2=C）",
    }, msg=f"已为 {len(results)} 条订阅生成推送记录（通道待接入，未实际发送）")


@router.get("", response_model=ApiResponse[PageData[dict]], summary="admin：全量订阅列表")
def admin_list_subscribes(
    user_id: Optional[int] = None,
    status: Optional[int] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    user: SysUser = Depends(require_role("admin", "admin_role")),
):
    """admin 登录后可以看到所有用户订阅（带筛选 + 分页）。"""
    q = (
        db.query(BidSubscribe, SysUser.username)
        .outerjoin(SysUser, SysUser.id == BidSubscribe.user_id)
    )
    if user_id is not None:
        q = q.filter(BidSubscribe.user_id == user_id)
    if status is not None:
        q = q.filter(BidSubscribe.status == status)
    if keyword:
        q = q.filter(BidSubscribe.keyword.like(f"%{keyword}%"))
    total = q.count()
    rows = (
        q.order_by(BidSubscribe.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [_to_dict(s, username=u) for (s, u) in rows]

    # U6：补会员套餐信息（活跃订单 → 套餐），超限由前端标红
    from datetime import datetime
    from sqlalchemy import func
    from app.models.member import MemberOrder, MemberPackage
    user_ids = {it["user_id"] for it in items}
    pkg_map, sub_count = {}, {}
    if user_ids:
        now = datetime.now()
        active = (
            db.query(MemberOrder.user_id, MemberPackage.name, MemberPackage.max_subscribe,
                     MemberOrder.end_date)
            .join(MemberPackage, MemberPackage.id == MemberOrder.package_id)
            .filter(MemberOrder.user_id.in_(user_ids), MemberOrder.status == 1,
                    MemberOrder.end_date >= now)
            .order_by(MemberOrder.end_date.desc())
            .all()
        )
        for uid, pkg_name, max_sub, _end in active:
            if uid not in pkg_map:  # 取最晚到期的套餐
                pkg_map[uid] = {"package_name": pkg_name, "max_subscribe": max_sub}
        counts = (
            db.query(BidSubscribe.user_id, func.count(BidSubscribe.id))
            .filter(BidSubscribe.user_id.in_(user_ids), BidSubscribe.status == 1)
            .group_by(BidSubscribe.user_id).all()
        )
        sub_count = dict(counts)
    for it in items:
        info = pkg_map.get(it["user_id"], {})
        it["package_name"] = info.get("package_name")
        it["max_subscribe"] = info.get("max_subscribe")
        it["active_subscribe_count"] = sub_count.get(it["user_id"], 0)
        it["over_limit"] = bool(
            info.get("max_subscribe") is not None
            and sub_count.get(it["user_id"], 0) > info["max_subscribe"]
        )

    return ApiResponse.ok(PageData(
        total=total, page=page, page_size=page_size,
        items=items,
    ))


@router.put("/{subscribe_id}/toggle", summary="admin：启用/禁用订阅")
def toggle_subscribe(
    subscribe_id: int,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    sub = db.query(BidSubscribe).filter(BidSubscribe.id == subscribe_id).first()
    if not sub:
        raise HTTPException(status_code=404, detail="订阅不存在")
    sub.status = 0 if sub.status else 1
    db.commit()
    db.refresh(sub)
    return ApiResponse.ok(_to_dict(sub), msg="已更新")
