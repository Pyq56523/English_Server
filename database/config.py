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
    f"mysql+pymysql://{quote_plus(_cfg['mysql']['user'])}:{quote_plus(_cfg['mysql']['password'])}"
    f"@{_cfg['mysql']['host']}:{_cfg['mysql']['port']}/{_cfg['mysql']['database']}"
    f"?charset={_cfg['mysql']['charset']}"
)

engine = create_engine(
    DATABASE_URL,
    pool_size=_cfg['mysql']['pool_size'],
    max_overflow=_cfg['mysql']['max_overflow'],
    echo=_cfg['mysql']['echo'],
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def create_all_tables() -> None:
    """开发阶段用于快速建表（生产环境请使用 Alembic 迁移）"""


    Base.metadata.create_all(bind=engine)