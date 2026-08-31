"""依赖注入：get_db / get_current_user / get_current_user_id"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

import database.database_item as db_item
import database.database_operate as db_operate
from database.config import SessionLocal
from handle.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def get_db() -> Session:
    """数据库会话（由 database/config.py 根据 JSON 配置构建）"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> db_item.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db_operate.User_Get(db, int(user_id))
    if user is None:
        raise credentials_exception
    return user


def get_current_user_id(user: db_item.User = Depends(get_current_user)) -> int:
    return user.id