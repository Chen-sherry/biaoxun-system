"""字典数据接口（公开）"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.dict import DictRegion, DictIndustry, DictNoticeType
from app.utils.response import ApiResponse

router = APIRouter(prefix="/dicts")


def _to_dict(o) -> dict:
    """ORM 对象 → dict（过滤 SQLAlchemy 内部属性）"""
    return {k: v for k, v in o.__dict__.items() if not k.startswith("_")}


@router.get("/regions", summary="地区字典（树形）")
def list_regions(db: Session = Depends(get_db), parent_id: int = 0):
    items = (
        db.query(DictRegion)
        .filter(DictRegion.parent_id == parent_id, DictRegion.status == 1)
        .order_by(DictRegion.sort.asc())
        .all()
    )
    return ApiResponse.ok([_to_dict(x) for x in items])


@router.get("/industries", summary="行业分类（树形）")
def list_industries(db: Session = Depends(get_db), parent_id: int = 0):
    items = (
        db.query(DictIndustry)
        .filter(DictIndustry.parent_id == parent_id, DictIndustry.status == 1)
        .order_by(DictIndustry.sort.asc())
        .all()
    )
    return ApiResponse.ok([_to_dict(x) for x in items])


@router.get("/notice-types", summary="公告类型字典")
def list_notice_types(db: Session = Depends(get_db), category: str | None = None):
    q = db.query(DictNoticeType).filter(DictNoticeType.status == 1)
    if category:
        q = q.filter(DictNoticeType.category == category)
    items = q.order_by(DictNoticeType.sort.asc()).all()
    return ApiResponse.ok([_to_dict(x) for x in items])
