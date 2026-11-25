# -*- coding: utf-8 -*-
"""后台推送管理接口：模板 / 临时推送 / AI 生成 / 推送记录
对应设计文档 docs/06-推送模块设计-关系书与功能书.md"""
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import require_role, get_current_user
from app.models.push import PushRecord, PushTemplate
from app.models.user import SysUser
from app.services import push_template_service as pts
from app.services.wecom_push import send_markdown_sync, send_text_sync
from app.utils.response import ApiResponse, PageData

router = APIRouter(prefix="/admin/push", tags=["后台：推送管理"])

# admin / ops 均可进推送模块（设计 3.6）
PushRole = Depends(require_role("admin", "ops"))
AdminRole = Depends(require_role("admin"))


# ============================================================
# 模板
# ============================================================

@router.get("/templates", summary="模板列表（含启用状态）")
def list_templates(db: Session = Depends(get_db), _: SysUser = PushRole):
    return ApiResponse.ok([pts.template_to_dict(t) for t in pts.list_templates(db)])


@router.get("/templates/{code}", summary="模板详情")
def get_template(code: str, db: Session = Depends(get_db), _: SysUser = PushRole):
    t = pts.get_template(db, code)
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    return ApiResponse.ok(pts.template_to_dict(t))


class TemplateIn(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    enabled: Optional[bool] = None
    name: Optional[str] = None
    schedule_time: Optional[str] = None   # HH:MM（M5 执行时间调整）
    frequency: Optional[str] = None       # daily / weekly（custom）
    weekday: Optional[int] = None         # 0=周一..6=周日
    apply_default: Optional[bool] = None  # True=同时把当前文案存为默认快照


class TemplateCreateIn(BaseModel):
    code: str                 # 自定义编码（唯一，如 custom_xxx）
    name: str
    schedule_time: str        # HH:MM
    title: str
    content: str
    frequency: str = "daily"
    weekday: Optional[int] = None
    enabled: bool = True


@router.put("/templates/{code}", summary="保存模板（S4：变量校验 + M5 执行时间）")
def save_template(code: str, payload: TemplateIn, db: Session = Depends(get_db),
                  user: SysUser = Depends(get_current_user)):
    if not user.is_admin and "ops" not in {r.code for r in user.roles}:
        raise HTTPException(status_code=403, detail="权限不足")
    t = pts.get_template(db, code)
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    if payload.content is not None:
        allowed = [v for v in (t.variables or "").split(",") if v]
        bad = pts.validate_variables(payload.content, allowed)
        if bad:
            raise HTTPException(status_code=400, detail=f"模板含允许清单外的变量：{', '.join(bad)}")
        t.content = payload.content
    if payload.title is not None:
        bad = pts.validate_variables(payload.title, [v for v in (t.variables or "").split(",") if v])
        if bad:
            raise HTTPException(status_code=400, detail=f"标题含允许清单外的变量：{', '.join(bad)}")
        t.title = payload.title
    if payload.enabled is not None:
        t.enabled = 1 if payload.enabled else 0
    if payload.name is not None:
        t.name = payload.name[:64]
    if payload.schedule_time is not None:
        if not pts.is_valid_time(payload.schedule_time):
            raise HTTPException(status_code=400, detail="执行时间格式须为 HH:MM（00:00~23:59）")
        t.schedule_time = payload.schedule_time
    if payload.frequency is not None:
        if payload.frequency not in ("daily", "weekly"):
            raise HTTPException(status_code=400, detail="频率仅支持 daily / weekly")
        t.frequency = payload.frequency
    if payload.weekday is not None:
        if not 0 <= payload.weekday <= 6:
            raise HTTPException(status_code=400, detail="weekday 取值 0~6（周一~周日）")
        t.weekday = payload.weekday
    t.updated_by = user.id
    from datetime import datetime
    t.updated_at = datetime.now()
    if payload.apply_default:
        # 「应用为默认模板」：把保存后的文案同时写入默认快照
        t.default_title = t.title
        t.default_content = t.content
    db.commit()
    return ApiResponse.ok(pts.template_to_dict(t), msg="模板已保存（执行时间即时生效）")


@router.post("/templates", summary="新增自定义定时推送（kind=custom）")
def create_template(payload: TemplateCreateIn, db: Session = Depends(get_db),
                    user: SysUser = Depends(get_current_user)):
    if not user.is_admin and "ops" not in {r.code for r in user.roles}:
        raise HTTPException(status_code=403, detail="权限不足")
    import re as _re
    code = (payload.code or "").strip()
    if not _re.match(r"^[a-z][a-z0-9_]{2,31}$", code):
        raise HTTPException(status_code=400, detail="code 须为小写字母开头的 3~32 位字母数字下划线")
    if pts.get_template(db, code):
        raise HTTPException(status_code=400, detail=f"code 已存在：{code}")
    if not pts.is_valid_time(payload.schedule_time):
        raise HTTPException(status_code=400, detail="执行时间格式须为 HH:MM（00:00~23:59）")
    if payload.frequency not in ("daily", "weekly"):
        raise HTTPException(status_code=400, detail="频率仅支持 daily / weekly")
    if payload.frequency == "weekly" and payload.weekday is None:
        raise HTTPException(status_code=400, detail="每周执行需选择星期几")
    # 自定义模板可用变量固定为 date/count
    bad = pts.validate_variables(payload.content, ["date", "count"]) + \
          pts.validate_variables(payload.title, ["date", "count"])
    if bad:
        raise HTTPException(status_code=400,
                            detail=f"自定义模板仅支持变量 {{date}} {{count}}，发现：{', '.join(sorted(set(bad)))}")
    if not payload.title.strip() or not payload.content.strip():
        raise HTTPException(status_code=400, detail="标题和内容不能为空")

    t = PushTemplate(
        code=code, name=payload.name[:64], kind="custom",
        schedule_time=payload.schedule_time, frequency=payload.frequency,
        weekday=payload.weekday if payload.frequency == "weekly" else None,
        title=payload.title, content=payload.content,
        variables="date,count", enabled=1 if payload.enabled else 0,
        updated_by=user.id,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return ApiResponse.ok(pts.template_to_dict(t), msg="自定义定时推送已创建")


@router.delete("/templates/{code}", summary="删除自定义定时推送（内置模板不可删）")
def delete_template(code: str, db: Session = Depends(get_db),
                    user: SysUser = Depends(get_current_user)):
    if not user.is_admin and "ops" not in {r.code for r in user.roles}:
        raise HTTPException(status_code=403, detail="权限不足")
    t = pts.get_template(db, code)
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    if t.kind != "custom":
        raise HTTPException(status_code=400, detail="内置模板不可删除，只能停用")
    # 清掉关联记录的外键引用风险：push_record.template_id 是 FK，先置空
    from app.models.push import PushRecord
    db.query(PushRecord).filter(PushRecord.template_id == t.id).update(
        {PushRecord.template_id: None})
    db.delete(t)
    db.commit()
    return ApiResponse.ok(msg="已删除")


class RenderIn(BaseModel):
    title: Optional[str] = None      # 用编辑中的未保存内容预览
    content: Optional[str] = None


def _build_real_vars(db: Session, code: str) -> dict:
    """用真实数据构造模板变量（预览/测试发送共用）"""
    from datetime import datetime, timedelta
    from app.models.bid import BidInfo

    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    if code == "expiring_alert":
        cutoff = now + timedelta(hours=24)
        rows = (db.query(BidInfo)
                .filter(BidInfo.status == 1, BidInfo.deadline.isnot(None),
                        BidInfo.deadline >= now, BidInfo.deadline <= cutoff)
                .order_by(BidInfo.deadline.asc()).limit(15).all())
        bid_list = "\n".join(
            f"- [{(r.title or '')[:40]}]({r.source_url or ''}) · "
            f"{r.deadline.strftime('%m-%d %H:%M') if r.deadline else '?'}"
            for r in rows) or "（暂无 24h 内截止的标讯）"
        return {"date": now.strftime("%Y-%m-%d"), "count": str(len(rows)),
                "bid_list": bid_list}

    if code == "archive_notice":
        cutoff = now - timedelta(days=30)
        rows = (db.query(BidInfo)
                .filter(BidInfo.status == 3, BidInfo.deadline.isnot(None),
                        BidInfo.deadline < cutoff)
                .order_by(BidInfo.deadline.desc()).limit(15).all())
        bid_list = "\n".join(
            f"- [{(r.title or '')[:40]}]({r.source_url or ''})" for r in rows) or "（暂无归档标讯）"
        return {"date": now.strftime("%Y-%m-%d"), "count": str(len(rows)),
                "bid_list": bid_list}

    # daily_summary：近 24h 新增 X 条 + 最新 3 条结构化卡片（与任务同一实现）
    from app.services.push_template_service import count_recent, build_latest_bids_list
    return {"date": datetime.now().strftime("%Y-%m-%d"),
            "count": str(count_recent(24)),
            "bid_list": build_latest_bids_list(db, limit=3)}


@router.post("/templates/{code}/preview", summary="预览（真实数据渲染，不发送；Q6=落库 preview 记录）")
def preview_template(code: str, payload: RenderIn, db: Session = Depends(get_db),
                     user: SysUser = Depends(get_current_user)):
    if not user.is_admin and "ops" not in {r.code for r in user.roles}:
        raise HTTPException(status_code=403, detail="权限不足")
    t = pts.get_template(db, code)
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    variables = _build_real_vars(db, code)
    # 支持编辑中的未保存内容直接预览
    title = pts.render_template(payload.title if payload.title is not None else t.title, variables)
    content = pts.render_template(payload.content if payload.content is not None else t.content, variables)
    full = f"## {title}\n{content}"
    length = pts.check_length(full)
    # Q6：预览也落库（preview=1）
    pts.save_record(db, push_type="test", preview=1, template_id=t.id,
                    operator_id=user.id, status=0, subject=title,
                    error_msg=None if length["ok"] else f"超长 {length['bytes']}/{length['limit']}")
    db.commit()
    return ApiResponse.ok({"title": title, "content": content, "full": full,
                           "length": length, "variables": variables})


@router.post("/templates/{code}/test", summary="测试发送到企微群（push_type=test）")
def test_template(code: str, payload: RenderIn, db: Session = Depends(get_db),
                  user: SysUser = Depends(get_current_user)):
    if not user.is_admin and "ops" not in {r.code for r in user.roles}:
        raise HTTPException(status_code=403, detail="权限不足")
    t = pts.get_template(db, code)
    if not t:
        raise HTTPException(status_code=404, detail="模板不存在")
    variables = _build_real_vars(db, code)
    title = pts.render_template(payload.title if payload.title is not None else t.title, variables)
    content = pts.render_template(payload.content if payload.content is not None else t.content, variables)
    full = f"## [测试] {title}\n{content}"
    length = pts.check_length(full)
    if not length["ok"]:
        pts.save_record(db, push_type="test", preview=0, template_id=t.id,
                        operator_id=user.id, status=1, subject=title,
                        error_msg=f"超长 {length['bytes']}/{length['limit']} 字节")
        db.commit()
        raise HTTPException(status_code=400, detail=f"内容超长 {length['bytes']}/{length['limit']} 字节")

    result = send_markdown_sync(f"[测试] {title}", content)
    ok = bool(result and result.get("errcode") == 0)
    err = None if ok else str(result or "webhook 未配置或发送失败")[:500]
    pts.save_record(db, push_type="test", preview=0, template_id=t.id,
                    operator_id=user.id, status=0 if ok else 1, subject=title, error_msg=err)
    db.commit()
    if not ok:
        return ApiResponse.fail(msg=f"发送失败：{err}")
    return ApiResponse.ok(msg="测试消息已发送到企微群")


# ============================================================
# 临时推送（M 模式 A/B）
# ============================================================

class ManualBidsIn(BaseModel):
    bid_ids: List[int]
    header: str = ""          # 自定义开头
    format: str = "markdown"  # markdown / text


class ManualTextIn(BaseModel):
    content: str
    format: str = "markdown"  # markdown / text


def _build_bids_message(db: Session, bid_ids: List[int], header: str, fmt: str) -> str:
    from app.models.bid import BidInfo
    rows = (db.query(BidInfo)
            .filter(BidInfo.id.in_(bid_ids))
            .all())
    order = {b: i for i, b in enumerate(bid_ids)}
    rows.sort(key=lambda r: order.get(r.id, 999))
    if fmt == "text":
        lines = [f"{i+1}. {(r.title or '')[:60]}" for i, r in enumerate(rows)]
    else:
        lines = [f"- [{(r.title or '')[:60]}]({r.source_url or ''})" for r in rows]
    body = "\n".join(lines)
    return f"{header}\n\n{body}" if header else body


@router.post("/manual/preview", summary="临时推送预览（含长度校验，Q6 落库 preview）")
def manual_preview(payload: dict, db: Session = Depends(get_db),
                   user: SysUser = Depends(get_current_user)):
    if not user.is_admin and "ops" not in {r.code for r in user.roles}:
        raise HTTPException(status_code=403, detail="权限不足")
    kind = payload.get("kind", "bids")  # bids / text
    if kind == "text":
        content = payload.get("content", "")
        bid_ids = []
    else:
        bid_ids = payload.get("bid_ids") or []
        if len(bid_ids) > pts.MANUAL_BID_LIMIT:
            raise HTTPException(status_code=400,
                                detail=f"单次最多 {pts.MANUAL_BID_LIMIT} 条（当前 {len(bid_ids)} 条）")
        content = _build_bids_message(db, bid_ids, payload.get("header", ""),
                                      payload.get("format", "markdown"))
    length = pts.check_length(content)
    pts.save_record(db, push_type="manual", preview=1, operator_id=user.id,
                    status=0, subject=content[:40],
                    bid_ids=bid_ids or None,
                    error_msg=None if length["ok"] else f"超长 {length['bytes']}/{length['limit']}")
    db.commit()
    return ApiResponse.ok({"content": content, "length": length, "count": len(bid_ids)})


def _do_manual_send(db, user, *, content: str, push_type: str, bid_ids: list,
                    subject: str, fmt: str) -> dict:
    """共用发送逻辑：长度校验 → 发送 → 落记录"""
    length = pts.check_length(content)
    if not length["ok"]:
        pts.save_record(db, push_type=push_type, preview=0, operator_id=user.id,
                        status=1, subject=subject, bid_ids=bid_ids or None,
                        error_msg=f"超长 {length['bytes']}/{length['limit']} 字节")
        db.commit()
        raise HTTPException(status_code=400,
                            detail=f"内容超长 {length['bytes']}/{length['limit']} 字节，禁止发送")

    if fmt == "text":
        ok = bool(send_text_sync(content))
        err = None if ok else "webhook 未配置或发送失败"
    else:
        result = send_markdown_sync(subject, content)
        ok = bool(result and result.get("errcode") == 0)
        err = None if ok else str(result or "webhook 未配置或发送失败")[:500]

    pts.save_record(db, push_type=push_type, preview=0, operator_id=user.id,
                    status=0 if ok else 1, subject=subject, bid_ids=bid_ids or None,
                    error_msg=err)
    db.commit()
    return {"pushed": ok, "error": err, "bytes": length["bytes"]}


@router.post("/manual/bids", summary="按勾选标讯推送（M4，push_type=manual）")
def manual_send_bids(payload: ManualBidsIn, db: Session = Depends(get_db),
                     user: SysUser = Depends(get_current_user)):
    if not user.is_admin and "ops" not in {r.code for r in user.roles}:
        raise HTTPException(status_code=403, detail="权限不足")
    if not payload.bid_ids:
        raise HTTPException(status_code=400, detail="未选择标讯")
    if len(payload.bid_ids) > pts.MANUAL_BID_LIMIT:
        raise HTTPException(status_code=400,
                            detail=f"单次最多 {pts.MANUAL_BID_LIMIT} 条（当前 {len(payload.bid_ids)} 条）")
    content = _build_bids_message(db, payload.bid_ids, payload.header, payload.format)
    result = _do_manual_send(db, user, content=content, push_type="manual",
                             bid_ids=payload.bid_ids, subject="标讯推送",
                             fmt=payload.format)
    if not result["pushed"]:
        return ApiResponse.fail(msg=f"发送失败：{result['error']}")
    return ApiResponse.ok(result, msg="已发送到企微群")


@router.post("/manual/text", summary="自由文本通知（M6，push_type=manual）")
def manual_send_text(payload: ManualTextIn, db: Session = Depends(get_db),
                     user: SysUser = Depends(get_current_user)):
    if not user.is_admin and "ops" not in {r.code for r in user.roles}:
        raise HTTPException(status_code=403, detail="权限不足")
    if not payload.content.strip():
        raise HTTPException(status_code=400, detail="内容不能为空")
    subject = payload.content.strip().splitlines()[0][:40]
    result = _do_manual_send(db, user, content=payload.content, push_type="manual",
                             bid_ids=[], subject=subject, fmt=payload.format)
    if not result["pushed"]:
        return ApiResponse.fail(msg=f"发送失败：{result['error']}")
    return ApiResponse.ok(result, msg="已发送到企微群")


# ============================================================
# AI 生成（3.7）
# ============================================================

class AiChatMessage(BaseModel):
    role: str     # user / assistant
    content: str


class AiGenerateIn(BaseModel):
    messages: List[AiChatMessage]


@router.post("/ai/generate", summary="AI 对话生成推送文案（function calling 调标讯检索）")
async def ai_generate(payload: AiGenerateIn, db: Session = Depends(get_db),
                      user: SysUser = Depends(get_current_user)):
    if not user.is_admin and "ops" not in {r.code for r in user.roles}:
        raise HTTPException(status_code=403, detail="权限不足")
    cleaned = [{"role": m.role if m.role in ("user", "assistant") else "user",
                "content": m.content} for m in payload.messages]
    if not cleaned:
        raise HTTPException(status_code=400, detail="messages 不能为空")
    from app.services.ai_push import generate_push
    result = await generate_push(cleaned[-16:])
    return ApiResponse.ok(result)


class AiSendIn(BaseModel):
    content: str
    bid_ids: List[int] = []
    format: str = "markdown"


@router.post("/ai/send", summary="发送 AI 生成文案（人工确认后，push_type=ai）")
def ai_send(payload: AiSendIn, db: Session = Depends(get_db),
            user: SysUser = Depends(get_current_user)):
    if not user.is_admin and "ops" not in {r.code for r in user.roles}:
        raise HTTPException(status_code=403, detail="权限不足")
    if not payload.content.strip():
        raise HTTPException(status_code=400, detail="内容不能为空")
    if len(payload.bid_ids) > pts.MANUAL_BID_LIMIT:
        raise HTTPException(status_code=400,
                            detail=f"引用标讯最多 {pts.MANUAL_BID_LIMIT} 条")
    subject = payload.content.strip().splitlines()[0][:40]
    result = _do_manual_send(db, user, content=payload.content, push_type="ai",
                             bid_ids=payload.bid_ids, subject=subject, fmt=payload.format)
    if not result["pushed"]:
        return ApiResponse.fail(msg=f"发送失败：{result['error']}")
    return ApiResponse.ok(result, msg="AI 推送已发送到企微群")


# ============================================================
# 推送记录（3.4，只读审计）
# ============================================================

@router.get("/records", summary="推送记录（分页筛选）")
def list_records(
    push_type: Optional[str] = None,
    status: Optional[int] = None,
    include_preview: bool = False,   # 默认筛掉预览记录
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
    _: SysUser = PushRole,
):
    q = db.query(PushRecord)
    if push_type:
        q = q.filter(PushRecord.push_type == push_type)
    if status is not None:
        q = q.filter(PushRecord.status == status)
    if not include_preview:
        q = q.filter(PushRecord.preview == 0)
    total = q.count()
    rows = (q.order_by(PushRecord.id.desc())
            .offset((page - 1) * page_size).limit(page_size).all())

    # 批量补操作人名 / 模板 code（避免 N+1）
    op_ids = {r.operator_id for r in rows if r.operator_id}
    tpl_ids = {r.template_id for r in rows if r.template_id}
    users = {}
    if op_ids:
        users = {u.id: u.nickname or u.username
                 for u in db.query(SysUser).filter(SysUser.id.in_(op_ids)).all()}
    tpls = {}
    if tpl_ids:
        tpls = {t.id: t.code
                for t in db.query(PushTemplate).filter(PushTemplate.id.in_(tpl_ids)).all()}

    items = [pts.record_to_dict(r, operator_name=users.get(r.operator_id),
                                template_code=tpls.get(r.template_id)) for r in rows]
    return ApiResponse.ok(PageData(total=total, page=page, page_size=page_size, items=items))


@router.get("/channels", summary="通道状态（不返回密钥）")
def channel_status(_: SysUser = PushRole):
    from app.config import settings
    return ApiResponse.ok({
        "wecom_configured": bool((settings.wecom_webhook or "").strip()),
        "ai_enabled": bool(settings.deepseek_api_key),
        "manual_bid_limit": pts.MANUAL_BID_LIMIT,
        "wecom_md_limit": pts.WECOM_MD_LIMIT,
    })
