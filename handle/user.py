"""用户认证业务处理：注册 / 登录 / 刷新令牌 / 当前用户"""
from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

import database.database_item as db_item
import database.database_operate as db_operate
from handle.security import create_access_token, decode_token, hash_password, verify_password
from utils.dependencies import get_current_user, get_db
from utils.exceptions import ok


def register(payload: db_operate.UserCreate, db: Session = Depends(get_db)):
    """注册新用户"""
    if db_operate.User_GetByUsername(db, payload.username):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username already taken")
    if db_operate.User_GetByEmail(db, payload.email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")

    user = db_operate.User_Add(
        db,
        db_item.User(
            username=payload.username,
            email=payload.email,
            password=hash_password(payload.password),
        ),
    )
    return ok(data=db_operate.UserResponse.model_validate(user).model_dump(mode="json"), message="Registered")


def login(payload: db_operate.LoginRequest, db: Session = Depends(get_db)):
    """登录：用户名或邮箱 + 密码"""
    user = db_operate.User_GetByUsername(db, payload.username) or db_operate.User_GetByEmail(db, payload.username)
    if user is None or not verify_password(payload.password, user.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password")

    result = db_operate.UserTokenResponse(
        access_token=create_access_token(str(user.id)),
        user=db_operate.UserResponse.model_validate(user),
    )
    return ok(data=result.model_dump(mode="json"), message="Login success")


def refresh(payload: db_operate.RefreshRequest, db: Session = Depends(get_db)):
    """刷新 Token：校验旧 Token 有效后签发新 Token"""
    try:
        user_id = int(decode_token(payload.token).get("sub"))
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")

    user = db_operate.User_Get(db, user_id)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

    result = db_operate.UserTokenResponse(
        access_token=create_access_token(str(user.id)),
        user=db_operate.UserResponse.model_validate(user),
    )
    return ok(data=result.model_dump(mode="json"), message="Refreshed")


def me(user: db_item.User = Depends(get_current_user)):
    """获取当前登录用户信息"""
    return ok(data=db_operate.UserResponse.model_validate(user).model_dump(mode="json"))