"""采集源管理"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.bid import BidSource
from app.api.deps import get_current_user
from app.models.user import SysUser
from app.utils.response import ApiResponse

router = APIRouter(prefix="/sources")


def _to_dict(orm) -> dict:
    """SQLAlchemy ORM → 干净 dict（去掉 _sa_instance_state）"""
    if orm is None:
        return {}
    out = {}
    for k, v in orm.__dict__.items():
        if k.startswith("_"):
            continue
        if hasattr(v, "isoformat"):
            v = v.isoformat()
        out[k] = v
    return out


@router.get("", summary="采集源列表")
def list_sources(db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    items = db.query(BidSource).order_by(BidSource.id.desc()).all()
    return ApiResponse.ok([_to_dict(i) for i in items])


@router.post("", summary="新增采集源")
def create_source(payload: dict, db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    source = BidSource(**payload)
    db.add(source)
    db.commit()
    db.refresh(source)
    return ApiResponse.ok(_to_dict(source), msg="新增成功")


@router.put("/{source_id}", summary="更新采集源")
def update_source(source_id: int, payload: dict, db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    source = db.query(BidSource).filter(BidSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="采集源不存在")
    for k, v in payload.items():
        if not k.startswith("_"):
            setattr(source, k, v)
    db.commit()
    db.refresh(source)
    return ApiResponse.ok(_to_dict(source), msg="更新成功")


@router.delete("/{source_id}", summary="删除采集源")
def delete_source(source_id: int, db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    source = db.query(BidSource).filter(BidSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="采集源不存在")
    db.delete(source)
    db.commit()
    return ApiResponse.ok(msg="删除成功")
