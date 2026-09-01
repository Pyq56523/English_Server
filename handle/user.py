"""用户认证业务处理：注册 / 登录 / 刷新令牌 / 当前用户 / 头像上传"""
import uuid
from pathlib import Path

from fastapi import Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session

import database.database_item as db_item
import database.database_operate as db_operate
from handle.security import create_access_token, decode_token, hash_password, verify_password
from utils.dependencies import get_current_user, get_db
from utils.exceptions import ok

# 允许的图片扩展名
ALLOWED_IMG_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
MAX_AVATAR_SIZE = 5 * 1024 * 1024  # 5 MB
UPLOAD_DIR = Path(__file__).parent.parent / "uploads" / "avatars"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


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


def update_me(
    payload: db_operate.UserUpdateRequest,
    user: db_item.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新当前用户个人信息"""
    # username 重复检查
    if payload.username and payload.username != user.username:
        if db_operate.User_GetByUsername(db, payload.username):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username already taken")
        user.username = payload.username

    # email 重复检查
    if payload.email and payload.email != user.email:
        if db_operate.User_GetByEmail(db, payload.email):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered")
        user.email = payload.email

    # 其他可选字段
    if payload.avatar is not None:
        user.avatar = payload.avatar
    if payload.age is not None:
        user.age = payload.age
    if payload.gender is not None:
        user.gender = payload.gender
    if payload.bio is not None:
        user.bio = payload.bio
    if payload.province is not None:
        user.province = payload.province or None
    if payload.city is not None:
        user.city = payload.city or None

    db_operate.User_Update(db, user)
    return ok(data=db_operate.UserResponse.model_validate(user).model_dump(mode="json"), message="Updated")


def change_password(
    payload: db_operate.ChangePasswordRequest,
    user: db_item.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """修改密码"""
    if not verify_password(payload.old_password, user.password):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Incorrect old password")
    user.password = hash_password(payload.new_password)
    db_operate.User_Update(db, user)
    return ok(message="Password changed")


def upload_avatar(
    file: UploadFile = File(...),
    user: db_item.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """上传头像：保存到 uploads/avatars/，返回可访问的 URL"""
    # 1. 校验扩展名
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMG_EXTS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"不支持的图片格式: {ext}，仅支持 jpg/jpeg/png/gif/bmp/webp")

    # 2. 校验文件大小
    content = file.file.read()
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "图片不能超过 5MB")

    # 3. 生成唯一文件名：<user_id>_<uuid><ext>
    new_name = f"{user.id}_{uuid.uuid4().hex[:12]}{ext}"
    save_path = UPLOAD_DIR / new_name
    save_path.write_bytes(content)

    # 4. 构造前端可访问的 URL（静态挂载点在 main.py）
    avatar_url = f"/uploads/avatars/{new_name}"

    # 5. 更新用户头像
    user.avatar = avatar_url
    db_operate.User_Update(db, user)

    return ok(data={"avatar": avatar_url}, message="Avatar uploaded")