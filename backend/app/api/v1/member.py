"""会员套餐接口（前台浏览 + 后台管理）"""
from typing import Optional
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.member import MemberPackage
from app.utils.response import ApiResponse
from app.api.deps import get_current_user
from app.models.user import SysUser

router = APIRouter(prefix="/member-packages")


def _pkg_to_dict(p: MemberPackage) -> dict:
    """MemberPackage ORM → 干净 dict。"""
    return {
        "id": p.id,
        "name": p.name,
        "code": p.code,
        "price": float(p.price),
        "sale_price": float(p.sale_price),
        "duration_days": p.duration_days,
        "level": p.level,
        "max_subscribe": p.max_subscribe,
        "allow_export": p.allow_export,
        "allow_contact": p.allow_contact,
        "description": p.description,
        "sort": p.sort,
        "status": p.status,
        "created_at": p.created_at.isoformat() if getattr(p, "created_at", None) else None,
        "updated_at": p.updated_at.isoformat() if getattr(p, "updated_at", None) else None,
    }


@router.get("", response_model=ApiResponse, summary="套餐列表（公开）")
def list_packages(db: Session = Depends(get_db)):
    items = db.query(MemberPackage).filter(MemberPackage.status == 1).order_by(MemberPackage.sort.asc()).all()
    return ApiResponse.ok([_pkg_to_dict(p) for p in items])


@router.post("", response_model=ApiResponse, summary="新增套餐（后台）")
def create_package(payload: dict, db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    pkg = MemberPackage(**payload)
    db.add(pkg)
    db.commit()
    return ApiResponse.ok({"id": pkg.id}, msg="新增成功")


@router.put("/{pkg_id}", response_model=ApiResponse, summary="修改套餐")
def update_package(pkg_id: int, payload: dict, db: Session = Depends(get_db), _: SysUser = Depends(get_current_user)):
    pkg = db.query(MemberPackage).filter(MemberPackage.id == pkg_id).first()
    if not pkg:
        return ApiResponse.fail(msg="套餐不存在")
    for k, v in payload.items():
        setattr(pkg, k, v)
    db.commit()
    return ApiResponse.ok(msg="更新成功")
