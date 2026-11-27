"""会员套餐接口（前台公开列表 + 后台管理由 admin_member 负责）"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.member import MemberPackage
from app.utils.response import ApiResponse

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


@router.get("", response_model=ApiResponse, summary="套餐列表（公开，仅上架）")
def list_packages(db: Session = Depends(get_db)):
    items = db.query(MemberPackage).filter(MemberPackage.status == 1).order_by(MemberPackage.sort.asc()).all()
    return ApiResponse.ok([_pkg_to_dict(p) for p in items])
