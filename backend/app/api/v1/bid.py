"""标讯接口：列表 / 详情 / 新增 / 编辑 / 审核 / 下架"""
from datetime import datetime
from typing import Optional
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.bid import BidInfo
from app.models.dict import DictNoticeType, DictIndustry, DictRegion
from app.schemas.bid import (
    BidListItem, BidDetail, BidCreateIn, BidUpdateIn,
)
from app.utils.response import ApiResponse, PageData
from app.api.deps import get_current_user, require_role
from app.models.user import SysUser

router = APIRouter(prefix="/bids")


def _bid_to_dict(b: BidInfo, db: Session) -> dict:
    """统一 ORM → dict 转换（列表 + 详情复用）"""
    return {
        "id": b.id,
        "title": b.title,
        "project_code": b.project_code,
        "notice_type": db.query(DictNoticeType.name)
            .filter(DictNoticeType.id == b.notice_type_id).scalar() if b.notice_type_id else None,
        "notice_type_id": b.notice_type_id,
        "region_code": b.region_code,
        "region_name": db.query(DictRegion.name)
            .filter(DictRegion.code == b.region_code).scalar() if b.region_code else None,
        "publish_time": b.publish_time,
        "winner_publish_time": b.winner_publish_time,
        "deadline": b.deadline,
        "tenderee": b.tenderee,
        "agency": b.agency,
        "winner_unit": b.winner_unit,
        "win_amount": float(b.win_amount) if b.win_amount is not None else None,
        "procure_type": b.procure_type,
        "customer_group": b.customer_group,
        "winner_unit_type": b.winner_unit_type,
        "budget": b.budget,
        "status": b.status,
        "is_top": b.is_top,
        "source_url": b.source_url,
        "view_count": b.view_count or 0,
    }


@router.get("", response_model=ApiResponse[PageData[dict]], summary="标讯列表")
def list_bids(
    keyword: Optional[str] = Query(None, description="关键词（标题/正文模糊）"),
    region_code: Optional[str] = None,
    industry_id: Optional[int] = None,
    notice_type_id: Optional[int] = None,
    procure_type: Optional[str] = None,
    winner_unit: Optional[str] = None,
    customer_group: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    winner_date_from: Optional[str] = None,
    winner_date_to: Optional[str] = None,
    status: int = 1,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    q = db.query(BidInfo).filter(BidInfo.status == status)

    if keyword:
        like = f"%{keyword}%"
        q = q.filter(or_(BidInfo.title.like(like), BidInfo.content_text.like(like)))
    if region_code:
        q = q.filter(BidInfo.region_code == region_code)
    if industry_id:
        q = q.filter(BidInfo.industry_id == industry_id)
    if notice_type_id:
        q = q.filter(BidInfo.notice_type_id == notice_type_id)
    if procure_type:
        q = q.filter(BidInfo.procure_type == procure_type)
    if winner_unit:
        q = q.filter(BidInfo.winner_unit.like(f"%{winner_unit}%"))
    if customer_group:
        q = q.filter(BidInfo.customer_group == customer_group)
    if date_from:
        q = q.filter(BidInfo.publish_time >= date_from)
    if date_to:
        q = q.filter(BidInfo.publish_time <= date_to)
    if winner_date_from:
        q = q.filter(BidInfo.winner_publish_time >= winner_date_from)
    if winner_date_to:
        q = q.filter(BidInfo.winner_publish_time <= winner_date_to)

    total = q.count()
    items = (
        q.order_by(BidInfo.is_top.desc(), BidInfo.publish_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return ApiResponse.ok(PageData(
        total=total, page=page, page_size=page_size,
        items=[_bid_to_dict(b, db) for b in items],
    ))


@router.get("/{bid_id}", summary="标讯详情")
def get_bid(bid_id: int, db: Session = Depends(get_db)):
    b = db.query(BidInfo).filter(BidInfo.id == bid_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="标讯不存在")
    b.view_count = (b.view_count or 0) + 1
    db.commit()
    b = db.query(BidInfo).filter(BidInfo.id == bid_id).first()  # 刷 view_count

    data = _bid_to_dict(b, db)
    data["content"] = b.content
    data["content_text"] = b.content_text
    data["ai_processed"] = bool(b.ai_processed)
    data["source_id"] = b.source_id
    data["attachments"] = [
        {"id": a.id, "file_name": a.file_name, "is_require_member": a.is_require_member}
        for a in b.attachments
    ]
    return ApiResponse.ok(data)


@router.post("", response_model=ApiResponse, summary="新增标讯（后台）")
def create_bid(
    payload: BidCreateIn,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    kw = payload.model_dump(exclude_unset=True)
    bid = BidInfo(**kw, status=0 if not payload.source_id else 1)
    db.add(bid)
    db.commit()
    db.refresh(bid)
    return ApiResponse.ok({"id": bid.id}, msg="新增成功")


@router.put("", response_model=ApiResponse, summary="编辑标讯")
def update_bid(
    payload: BidUpdateIn,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    bid = db.query(BidInfo).filter(BidInfo.id == payload.id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="标讯不存在")
    for k, v in payload.model_dump(exclude={"id"}, exclude_unset=True).items():
        setattr(bid, k, v)
    db.commit()
    db.refresh(bid)
    return ApiResponse.ok({"id": bid.id}, msg="更新成功")


@router.get("/{bid_id}/suggestions", summary="待审核编辑：从正文/标题提取建议值")
def bid_suggestions(
    bid_id: int,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    """人工审核辅助：返回规则/源站专用提取器给出的候选值（不落库）。

    前端把这些值渲染成「建议」标签，点击即可填入表单，减少手工复制。
    """
    import re as _re
    from app.models.bid import BidSource
    from app.services.data_clean import (
        extract_tenderee, extract_budget, extract_deadline,
        extract_project_code, extract_winner, extract_candidate_table,
        is_result_notice,
    )
    from app.services.source_specs import extract_via_spec

    b = db.query(BidInfo).filter(BidInfo.id == bid_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="标讯不存在")

    ct = b.content_text or ""
    flat = _re.sub(r"\s+", " ", ct)
    fields: dict = {}
    if flat:
        td = extract_tenderee(flat)
        if td:
            fields["tenderee"] = td
        bg = extract_budget(flat)
        if bg:
            fields["budget"] = bg
        dl = extract_deadline(flat)
        if dl:
            fields["deadline"] = dl.isoformat() if hasattr(dl, "isoformat") else str(dl)
        pc = extract_project_code((b.title or "") + " " + flat)
        if pc:
            fields["project_code"] = pc
        if is_result_notice(b.title or "", ct):
            win = extract_winner(flat)
            fields.update({k: v for k, v in win.items() if v})
            tab = extract_candidate_table(ct)
            for k, v in tab.items():
                fields.setdefault(k, v)

    # 源站专用提取器（优先级更高，覆盖规则值）
    if b.source_id:
        src = db.query(BidSource).filter(BidSource.id == b.source_id).first()
        if src:
            try:
                spec = extract_via_spec(src.code, b.content or ct, {})
                for k, v in (spec or {}).items():
                    if v:
                        fields[k] = v
            except Exception:
                pass

    return ApiResponse.ok({
        "fields": fields,
        "is_result_notice": is_result_notice(b.title or "", ct),
    })


@router.post("/{bid_id}/reextract", response_model=ApiResponse, summary="待审核：按当前正文重新提取字段")
def reextract_bid(
    bid_id: int,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    """人工审核时点「重新提取」：规则 → 源站专用 →（开关开启时）AI 兜底。

    只补空字段，不覆盖已人工修改的值；返回本次新填的字段。
    """
    import re as _re
    from app.models.bid import BidSource
    from app.services.data_clean import extract_fields_from_text, is_result_notice
    from app.services.source_specs import fill_gaps_via_spec
    from app.services import ai_setting_service as ai_svc

    b = db.query(BidInfo).filter(BidInfo.id == bid_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="标讯不存在")
    ct = b.content_text or ""
    if not ct:
        return ApiResponse.ok({"updated": {}, "msg": "正文为空，无法提取"})

    FIELDS = ("tenderee", "agency", "budget", "deadline", "winner_unit",
              "win_amount", "project_code", "region_code")
    current = {k: getattr(b, k, None) for k in FIELDS}
    merged = dict(current)

    conn = db.get_bind().raw_connection()
    try:
        extra = extract_fields_from_text(b.title or "", ct, conn=conn.cursor(), current=merged)
        merged.update(extra)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if b.source_id:
        src = db.query(BidSource).filter(BidSource.id == b.source_id).first()
        if src:
            spec = fill_gaps_via_spec(
                src.code, b.content or ct, merged,
                allow_winner=is_result_notice(b.title or "", ct))
            merged.update(spec)

    # AI 兜底（开关开启且仍缺关键字段）
    if bool(ai_svc.get("param.ai_extract_enabled", True)):
        try:
            from app.services.ai_extract import missing_fields, ai_extract_missing
            miss = missing_fields(merged)
            if miss:
                ai_vals, ai_ok = ai_extract_missing(b.title or "", ct, miss)
                if ai_ok:
                    b.ai_processed = 1
                    for f in ("tenderee", "winner_unit", "win_amount"):
                        if ai_vals.get(f) is not None:
                            merged[f] = ai_vals[f]
        except Exception:
            pass

    updated = {}
    for k, v in merged.items():
        if v and current.get(k) in (None, "", 0):
            setattr(b, k, v)
            updated[k] = v
    db.commit()
    db.refresh(b)
    return ApiResponse.ok({"updated": updated, "msg": f"补全 {len(updated)} 个字段"})


@router.post("/{bid_id}/force-ai", response_model=ApiResponse, summary="强制走 AI 提取（无视开关）")
def force_ai_extract(
    bid_id: int,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    """无论总开关是否开启，都强制调 AI 补提取缺失字段。规则/源站专用先跑一遍，
    然后强制 AI 兜底（不等开关）。只补空字段，不覆盖已有人工值。"""
    import re as _re
    from app.models.bid import BidSource
    from app.services.data_clean import extract_fields_from_text, is_result_notice
    from app.services.source_specs import fill_gaps_via_spec
    from app.services.ai_extract import missing_fields, ai_extract_missing

    b = db.query(BidInfo).filter(BidInfo.id == bid_id).first()
    if not b:
        raise HTTPException(status_code=404, detail="标讯不存在")
    ct = b.content_text or ""
    if not ct:
        return ApiResponse.ok({"updated": {}, "ai_ok": False, "msg": "正文为空，无法转 AI"})

    FIELDS = ("tenderee", "agency", "budget", "deadline", "winner_unit",
              "win_amount", "project_code", "region_code")
    current = {k: getattr(b, k, None) for k in FIELDS}
    merged = dict(current)

    # 规则 + 源站专用（和 reextract 一样）
    conn = db.get_bind().raw_connection()
    try:
        extra = extract_fields_from_text(b.title or "", ct, conn=conn.cursor(), current=merged)
        merged.update(extra)
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if b.source_id:
        src = db.query(BidSource).filter(BidSource.id == b.source_id).first()
        if src:
            spec = fill_gaps_via_spec(
                src.code, b.content or ct, merged,
                allow_winner=is_result_notice(b.title or "", ct))
            merged.update(spec)

    # 强制 AI（不等开关）—— 把仍缺失的关键字段交给 AI
    miss = missing_fields({**merged, "content_text": ct})
    ai_ok = True
    if miss:
        ai_vals, ai_ok = ai_extract_missing(b.title or "", ct, miss)
        if ai_ok:
            b.ai_processed = 1
            for f in ("tenderee", "winner_unit", "win_amount"):
                if ai_vals.get(f) is not None:
                    merged[f] = ai_vals[f]

    updated = {}
    for k, v in merged.items():
        if v and current.get(k) in (None, "", 0):
            setattr(b, k, v)
            updated[k] = v

    # AI 确认提完（ok）→ 直接过；AI 失败（ok=False）→ 留待审核
    auto_approved = False
    if ai_ok:
        b.status = 1
        auto_approved = True

    db.commit()
    db.refresh(b)

    if auto_approved:
        msg = f"AI 补全 {len(updated)} 个字段，已自动通过"
    elif ai_ok:
        msg = f"AI 没找到更多可补的字段，已自动通过"
    else:
        msg = "AI 调用失败，请稍后重试"
    return ApiResponse.ok({"updated": updated, "ai_ok": ai_ok, "auto_approved": auto_approved, "msg": msg})


@router.post("/{bid_id}/audit", response_model=ApiResponse, summary="审核通过")
def audit_bid(
    bid_id: int,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    bid = db.query(BidInfo).filter(BidInfo.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="标讯不存在")
    bid.status = 1
    db.commit()
    return ApiResponse.ok(msg="审核通过")


@router.post("/{bid_id}/offline", response_model=ApiResponse, summary="下架")
def offline_bid(
    bid_id: int,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    bid = db.query(BidInfo).filter(BidInfo.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="标讯不存在")
    bid.status = 2
    db.commit()
    return ApiResponse.ok(msg="已下架")


@router.post("/{bid_id}/top", response_model=ApiResponse, summary="置顶/取消置顶")
def toggle_top(
    bid_id: int,
    top: Optional[bool] = None,
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    bid = db.query(BidInfo).filter(BidInfo.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="标讯不存在")
    bid.is_top = top if top is not None else not bid.is_top
    db.commit()
    return ApiResponse.ok(msg=f"已{'置顶' if bid.is_top else '取消置顶'}")
