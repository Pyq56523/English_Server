"""ORM 模型与状态常量：

- ORM 模型（users / word_books / words / user_word_records）
- 状态常量与 SM-2 初始参数

与数据库交接的函数（User_Get / Word_List / Record_AddAll ...）与
Pydantic Schema 数据项统一放在 database_operate.py 中。
"""
from datetime import datetime

from sqlalchemy import (BigInteger,Column,DateTime,Enum,Float,ForeignKey,Index,Integer,String,Text,UniqueConstraint,)
from sqlalchemy.orm import declarative_base

Base = declarative_base()

# 状态常量
STATUS_NEW = "new"
STATUS_LEARNING = "learning"
STATUS_MASTERED = "mastered"

# SM-2 初始参数
DEFAULT_EASE_FACTOR = 2.5
DEFAULT_INTERVAL_DAYS = 0
DEFAULT_REPETITION = 0
MIN_EASE_FACTOR = 1.3


# ================================================================
# ORM 模型
# ================================================================

class User(Base):
    """用户表"""
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password = Column(String(255), nullable=False)  # bcrypt 哈希
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WordBook(Base):
    """单词书"""
    __tablename__ = "word_books"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    category = Column(String(50), index=True)  # CET4 / CET6 / IELTS / TOEFL / GRE
    description = Column(Text)
    word_count = Column(Integer, default=0)  # 冗余字段，加速查询
    created_at = Column(DateTime, default=datetime.utcnow)


class Word(Base):
    """单词"""
    __tablename__ = "words"
    __table_args__ = (
        Index("idx_words_book_id", "book_id"),
        Index("idx_words_word", "word"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    word = Column(String(100), nullable=False)
    phonetic = Column(String(100))
    meaning = Column(Text, nullable=False)
    example = Column(Text)
    book_id = Column(BigInteger, ForeignKey("word_books.id"), nullable=False, index=True)


class UserWordRecord(Base):
    """用户单词学习记录（SM-2 算法核心表）"""
    __tablename__ = "user_word_records"
    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uk_user_word"),
        Index("idx_user_next_review", "user_id", "next_review_at"),
        Index("idx_user_status", "user_id", "status"),
    )

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id"), nullable=False)
    word_id = Column(BigInteger, ForeignKey("words.id"), nullable=False)
    status = Column(
        Enum(STATUS_NEW, STATUS_LEARNING, STATUS_MASTERED, name="record_status"),
        default=STATUS_NEW,
        nullable=False,
    )
    ease_factor = Column(Float, default=DEFAULT_EASE_FACTOR, nullable=False)
    interval_days = Column(Integer, default=0, nullable=False)
    repetition = Column(Integer, default=0, nullable=False)
    next_review_at = Column(DateTime, index=True)
    last_review_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)