"""统一业务异常与统一响应工具

响应格式：{ "code": 0, "data": {...}, "message": "ok" }
"""
from typing import Any

from fastapi import HTTPException


def ok(data: Any = None, message: str = "ok") -> dict:
    """统一成功响应"""
    return {"code": 0, "data": data, "message": message}


class BusinessException(HTTPException):
    """业务异常（Router 层捕获后返回统一格式）"""

    def __init__(self, status_code: int = 400, message: str = "Business error", code: int = 1):
        super().__init__(status_code=status_code, detail=message)
        self.code = code
        self.error_message = message