"""admin 数据清洗管理入口"""
from datetime import datetime
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import asyncio

from app.database import get_db
from app.models.user import SysUser
from app.api.deps import require_role
from app.utils.response import ApiResponse

router = APIRouter(prefix="/admin/data-clean")


# 内存里存一下上次清洗结果（实际生产应该用 Redis / 任务表）
_LAST_RESULT = {"at": None, "stats": None, "running": False}


@router.post("/run", summary="手动触发数据清洗（全量 bid_info）")
async def run_data_clean(
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    """
    后台立即跑 data_clean.clean_all_seed()，同步返回。
    8000 行约 5-10 秒。
    """
    from app.services.data_clean import clean_all_seed

    global _LAST_RESULT
    if _LAST_RESULT["running"]:
        return ApiResponse.fail("已有清洗任务正在进行")

    _LAST_RESULT["running"] = True
    try:
        # 放到线程池里跑，避免阻塞 uvicorn
        import concurrent.futures
        loop = asyncio.get_event_loop()
        with concurrent.futures.ThreadPoolExecutor() as ex:
            stats = await loop.run_in_executor(ex, clean_all_seed)
        _LAST_RESULT = {"at": datetime.now().isoformat(), "stats": stats, "running": False}
        return ApiResponse.ok(stats, msg="清洗完成")
    except Exception as e:
        _LAST_RESULT["running"] = False
        return ApiResponse.fail(f"清洗失败: {e}")


@router.get("/status", summary="查询清洗状态")
def data_clean_status(
    db: Session = Depends(get_db),
    _: SysUser = Depends(require_role("admin", "admin_role")),
):
    return ApiResponse.ok(_LAST_RESULT)
