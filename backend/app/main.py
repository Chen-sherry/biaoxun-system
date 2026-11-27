"""
FastAPI 应用主入口
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.logger import setup_logger
from app.utils.response import BusinessError
from app.api.v1 import api_v1


setup_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # === 启动时 ===
    # 初始化定时任务 / 连接 Redis / 预热缓存 ...
    try:
        import logging
        from app.database import SessionLocal
        from app.services.ai_setting_service import check_prompt_drift
        _log = logging.getLogger("app.main")
        _db = SessionLocal()
        try:
            _drift = check_prompt_drift(_db)
        finally:
            _db.close()
        if _drift:
            _log.warning("[ai_setting] 以下 Prompt 的 DB 值与源码默认不一致（实际以 DB 为准，"
                         "可在后台 /admin/ai/settings/{key}/reset 重置）：%s", ", ".join(_drift))
        else:
            _log.info("[ai_setting] Prompt 与源码默认一致")
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger("app.main").warning("[ai_setting] 启动时 Prompt 漂移检测失败: %s", e)
    yield
    # === 关闭时 ===


app = FastAPI(
    title=settings.app_name,
    description="标讯信息管理系统 API",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(BusinessError)
async def business_error_handler(request: Request, exc: BusinessError):
    return JSONResponse(status_code=200, content={"code": exc.code, "msg": exc.msg, "data": None})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    import traceback
    traceback.print_exc()
    return JSONResponse(
        status_code=500,
        content={"code": -999, "msg": f"服务器内部错误: {str(exc)}", "data": None},
    )


# 健康检查
@app.get("/healthz", summary="健康检查")
def healthz():
    return {"status": "ok", "app": settings.app_name, "env": settings.app_env}


@app.get("/", include_in_schema=False)
def root():
    return {"name": settings.app_name, "version": "0.1.0", "docs": "/docs"}


# 注册 v1 路由
app.include_router(api_v1)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "dev",
        workers=1,
    )
