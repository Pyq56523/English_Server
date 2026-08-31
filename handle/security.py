"""安全工具：JWT 生成/验证 + bcrypt 密码哈希

SECRET_KEY 从 app/config/main_leaner.json 读取。
"""
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext


def load_app_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "main_leaner.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


_app_cfg = load_app_config()
SECRET_KEY = _app_cfg["jwt"]["secret_key"]
ALGORITHM = _app_cfg["jwt"]["algorithm"]
ACCESS_TOKEN_EXPIRE_DAYS = _app_cfg["jwt"]["expire_days"]

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(sub: str, expires_delta: Optional[timedelta] = None) -> str:
    expire = datetime.utcnow() + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode = {"sub": sub, "exp": expire}
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])