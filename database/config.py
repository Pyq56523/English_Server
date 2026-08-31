"""数据库配置模块

读取 app/config/database.json，构建 SQLAlchemy 引擎与 SessionLocal。
"""
import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.database_item import Base
from urllib.parse import quote_plus

def load_db_config() -> dict:
    path = Path(__file__).parent.parent / "config" / "database.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


_cfg = load_db_config()
DATABASE_URL = (
    f"mysql+pymysql://{quote_plus(_cfg['user'])}:{quote_plus(_cfg['password'])}"
    f"@{_cfg['host']}:{_cfg['port']}/{_cfg['database']}"
    f"?charset={_cfg['charset']}"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=_cfg.get("pool_size", 10),
    max_overflow=_cfg.get("max_overflow", 20),
    echo=_cfg.get("echo", False),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def create_all_tables() -> None:
    """开发阶段用于快速建表（生产环境请使用 Alembic 迁移）"""


    Base.metadata.create_all(bind=engine)