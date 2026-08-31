"""与数据库交接的函数 + Pydantic Schema 数据项。

- 与数据库交接的函数（User_Get / Word_List / Record_AddAll ...）
- Pydantic Schema 数据项（LoginRequest / WordCard / DashboardStats ...）

ORM 模型与状态常量统一放在 database_item.py 中。
"""
from datetime import datetime
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pydantic import BaseModel, EmailStr, Field

import database.database_item as db_item


# ================================================================
# 内部通用工具
# ================================================================

def _get(db: Session, model, oid) -> Optional[object]:
    return db.get(model, oid)


def _get_by(db: Session, model, field, value) -> Optional[object]:
    stmt = select(model).where(field == value)
    return db.execute(stmt).scalars().first()


def _list(
    db: Session,
    model,
    filters: Sequence = (),
    order_by: Sequence = (),
    offset: int = 0,
    limit: Optional[int] = None,
) -> List[object]:
    stmt = select(model)
    if filters:
        stmt = stmt.where(*filters)
    if order_by:
        stmt = stmt.order_by(*order_by)
    if limit is not None:
        stmt = stmt.offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


def _count(db: Session, model, filters: Sequence = ()) -> int:
    stmt = select(func.count()).select_from(model)
    if filters:
        stmt = stmt.where(*filters)
    return db.execute(stmt).scalar_one()


def _add(db: Session, obj) -> object:
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def _add_all(db: Session, objs: Iterable) -> int:
    objs = list(objs)
    db.add_all(objs)
    db.commit()
    return len(objs)


def _commit(db: Session) -> None:
    db.commit()


# ================================================================
# 用户 User
# ================================================================

def User_Get(db: Session, uid) -> Optional[db_item.User]:
    return _get(db, db_item.User, uid)


def User_GetByUsername(db: Session, username: str) -> Optional[db_item.User]:
    return _get_by(db, db_item.User, db_item.User.username, username)


def User_GetByEmail(db: Session, email: str) -> Optional[db_item.User]:
    return _get_by(db, db_item.User, db_item.User.email, email)


def User_Add(db: Session, user: db_item.User) -> db_item.User:
    return _add(db, user)


# ================================================================
# 单词书 WordBook
# ================================================================

def WordBook_List(db: Session, category: Optional[str] = None) -> List[db_item.WordBook]:
    filters = ([db_item.WordBook.category == category] if category else [])
    return _list(db, db_item.WordBook, filters=filters)


def WordBook_Get(db: Session, book_id) -> Optional[db_item.WordBook]:
    return _get(db, db_item.WordBook, book_id)


# ================================================================
# 单词 Word
# ================================================================

def Word_List(
    db: Session,
    book_id: Optional[int] = None,
    keyword: Optional[str] = None,
    offset: int = 0,
    limit: Optional[int] = None,
) -> List[db_item.Word]:
    filters = []
    if book_id:
        filters.append(db_item.Word.book_id == book_id)
    if keyword:
        filters.append(db_item.Word.word.like(f"%{keyword}%"))
    return _list(db, db_item.Word, filters=filters, offset=offset, limit=limit)


def Word_Count(db: Session, book_id: Optional[int] = None, keyword: Optional[str] = None) -> int:
    filters = []
    if book_id:
        filters.append(db_item.Word.book_id == book_id)
    if keyword:
        filters.append(db_item.Word.word.like(f"%{keyword}%"))
    return _count(db, db_item.Word, filters)


def Word_ListByBook(db: Session, book_id: int) -> List[db_item.Word]:
    return _list(db, db_item.Word, filters=[db_item.Word.book_id == book_id])


def Word_Get(db: Session, word_id) -> Optional[db_item.Word]:
    return _get(db, db_item.Word, word_id)


# ================================================================
# 学习记录 UserWordRecord
# ================================================================

def Record_Get(db: Session, record_id) -> Optional[db_item.UserWordRecord]:
    return _get(db, db_item.UserWordRecord, record_id)


def Record_ListByUser(
    db: Session,
    user_id: int,
    since=None,
    review_only: bool = False,
) -> List[db_item.UserWordRecord]:
    filters = [db_item.UserWordRecord.user_id == user_id]
    if since is not None:
        filters.append(db_item.UserWordRecord.last_review_at >= since)
    if review_only:
        filters.append(db_item.UserWordRecord.last_review_at.isnot(None))
    return _list(db, db_item.UserWordRecord, filters=filters)


def Record_ListNew(db: Session, user_id: int, limit: int) -> List[db_item.UserWordRecord]:
    return _list(
        db,
        db_item.UserWordRecord,
        filters=[db_item.UserWordRecord.user_id == user_id, db_item.UserWordRecord.status == db_item.STATUS_NEW],
        limit=limit,
    )


def Record_ListDue(db: Session, user_id: int, now) -> List[db_item.UserWordRecord]:
    return _list(
        db,
        db_item.UserWordRecord,
        filters=[db_item.UserWordRecord.user_id == user_id, db_item.UserWordRecord.next_review_at <= now],
    )


def Record_Count(db: Session, user_id: int, status: Optional[str] = None) -> int:
    filters = [db_item.UserWordRecord.user_id == user_id]
    if status:
        filters.append(db_item.UserWordRecord.status == status)
    return _count(db, db_item.UserWordRecord, filters)


def Record_ListInBook(db: Session, user_id: int, word_ids: Sequence) -> List[db_item.UserWordRecord]:
    return _list(
        db,
        db_item.UserWordRecord,
        filters=[db_item.UserWordRecord.user_id == user_id, db_item.UserWordRecord.word_id.in_(word_ids)],
    )


def Record_AddAll(db: Session, records: Iterable[db_item.UserWordRecord]) -> int:
    return _add_all(db, records)


# ================================================================
# 常用短语 Phrase
# ================================================================

def Phrase_List(
    db: Session,
    category: Optional[str] = None,
    offset: int = 0,
    limit: Optional[int] = None,
) -> List[db_item.Phrase]:
    filters = ([db_item.Phrase.category == category] if category else [])
    return _list(db, db_item.Phrase, filters=filters, offset=offset, limit=limit)


def Phrase_Count(db: Session, category: Optional[str] = None) -> int:
    filters = ([db_item.Phrase.category == category] if category else [])
    return _count(db, db_item.Phrase, filters)


def Phrase_Get(db: Session, phrase_id) -> Optional[db_item.Phrase]:
    return _get(db, db_item.Phrase, phrase_id)


# ================================================================
# 统计辅助
# ================================================================

def DB_Commit(db: Session) -> None:
    _commit(db)


def UserMastered_Count(db: Session, user_id: int) -> int:
    return _count(
        db,
        db_item.UserWordRecord,
        [db_item.UserWordRecord.user_id == user_id, db_item.UserWordRecord.status == db_item.STATUS_MASTERED],
    )


# ================================================================
# Pydantic Schema 数据项
# ================================================================

# ---------------- 用户 / 认证 ----------------

class LoginRequest(BaseModel):
    """登录请求：支持用户名或邮箱 + 密码"""
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)


class UserCreate(BaseModel):
    """注册请求"""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class RefreshRequest(BaseModel):
    """刷新令牌请求"""
    token: str


class UserResponse(BaseModel):
    """用户信息响应"""
    id: int
    username: str
    email: str
    created_at: datetime

    model_config = {"from_attributes": True}


class UserTokenResponse(BaseModel):
    """登录成功响应（含 Token）"""
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ---------------- 单词书 ----------------

class WordBookCreate(BaseModel):
    name: str
    category: str
    description: Optional[str] = None


class WordBookResponse(BaseModel):
    id: int
    name: str
    category: str
    description: Optional[str]
    word_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


class WordBookDetailResponse(WordBookResponse):
    """详情 + 学习进度"""
    learned_count: int = 0
    mastered_count: int = 0


# ---------------- 单词 ----------------

class WordResponse(BaseModel):
    id: int
    word: str
    phonetic: Optional[str]
    meaning: str
    example: Optional[str]
    book_id: int

    model_config = {"from_attributes": True}


class WordPageResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[WordResponse]


# ---------------- 学习 / SM-2 ----------------

class StartLearningRequest(BaseModel):
    """开始学习某本单词书"""
    book_id: int


class ReviewRequest(BaseModel):
    """提交复习评分"""
    record_id: int
    quality: int = Field(..., ge=0, le=5, description="用户自评分 0-5")
    time_spent_ms: Optional[int] = Field(0, ge=0)


class ReviewResponse(BaseModel):
    """复习响应（SM-2 计算后结果）"""
    record_id: int
    word_id: int
    new_ease_factor: float
    new_interval_days: int
    next_review_at: Optional[datetime]
    status: str


class WordCard(BaseModel):
    """今日学习卡片"""
    word_id: int
    word: str
    phonetic: Optional[str]
    meaning: str
    example: Optional[str]
    # due_cards 专属字段
    record_id: Optional[int] = None
    repetition: Optional[int] = None
    interval_days: Optional[int] = None


class TodaySummary(BaseModel):
    total_new: int
    total_due: int
    mastered: int


class TodayCardsResponse(BaseModel):
    new_cards: list[WordCard]
    due_cards: list[WordCard]
    summary: TodaySummary


class LearningProgressResponse(BaseModel):
    """某本书学习进度"""
    book_id: int
    total: int
    learning: int
    mastered: int
    progress_rate: float  # 0-1


# ---------------- 常用短语 ----------------

class PhraseResponse(BaseModel):
    id: int
    phrase: str
    meaning: str
    example: Optional[str]
    category: Optional[str]

    model_config = {"from_attributes": True}


class PhrasePageResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[PhraseResponse]


# ---------------- 统计 ----------------

class TodayStat(BaseModel):
    learned: int = 0
    reviewed: int = 0
    accuracy_rate: float = 0.0


class TotalStat(BaseModel):
    words_learned: int = 0
    words_mastered: int = 0
    phrases_learned: int = 0


class StreakStat(BaseModel):
    current_streak_days: int = 0
    max_streak_days: int = 0


class DashboardStats(BaseModel):
    today: TodayStat
    total: TotalStat
    streak: StreakStat


class HeatmapData(BaseModel):
    """近 365 天学习热力图"""
    dates: list[str]      # ISO 日期
    counts: list[int]     # 对应学习数