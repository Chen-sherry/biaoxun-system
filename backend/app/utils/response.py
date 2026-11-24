"""
统一响应体 & 业务异常
"""
from typing import Generic, Optional, TypeVar, Any
from pydantic import BaseModel, Field
from fastapi import HTTPException, status

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应结构"""
    code: int = Field(default=0, description="业务码：0-成功，非 0-失败")
    msg: str = Field(default="ok", description="提示信息")
    data: Optional[T] = Field(default=None, description="业务数据")

    @classmethod
    def ok(cls, data: Any = None, msg: str = "ok") -> "ApiResponse":
        return cls(code=0, msg=msg, data=data)

    @classmethod
    def fail(cls, code: int = -1, msg: str = "error", data: Any = None) -> "ApiResponse":
        return cls(code=code, msg=msg, data=data)


class PageData(BaseModel, Generic[T]):
    """分页包装"""
    total: int = 0
    page: int = 1
    page_size: int = 20
    items: list[T] = []


class BusinessError(Exception):
    """业务异常（返回 code != 0 的 JSON，而非 HTTP 4xx/5xx）"""

    def __init__(self, code: int = -1, msg: str = "业务错误"):
        self.code = code
        self.msg = msg
        super().__init__(msg)


def raise_http(code: int = status.HTTP_400_BAD_REQUEST, msg: str = "请求错误") -> None:
    raise HTTPException(status_code=code, detail=msg)
