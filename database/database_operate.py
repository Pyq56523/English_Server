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


def User_Update(db: Session, user: db_item.User) -> db_item.User:
    """更新用户信息"""
    db.commit()
    db.refresh(user)
    return user


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
    """单词列表：可按书（经关联表）/ 关键词过滤、分页"""
    stmt = select(db_item.Word)
    if book_id:
        stmt = stmt.join(
            db_item.WordBookWord, db_item.WordBookWord.word_id == db_item.Word.id
        ).where(db_item.WordBookWord.book_id == book_id)
    if keyword:
        stmt = stmt.where(db_item.Word.word.like(f"%{keyword}%"))
    if limit is not None:
        stmt = stmt.offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all())


def Word_Count(db: Session, book_id: Optional[int] = None, keyword: Optional[str] = None) -> int:
    """单词计数：可按书（经关联表）/ 关键词过滤"""
    stmt = select(func.count()).select_from(db_item.Word)
    if book_id:
        stmt = stmt.join(
            db_item.WordBookWord, db_item.WordBookWord.word_id == db_item.Word.id
        ).where(db_item.WordBookWord.book_id == book_id)
    if keyword:
        stmt = stmt.where(db_item.Word.word.like(f"%{keyword}%"))
    return db.execute(stmt).scalar_one()


def Word_ListByBook(db: Session, book_id: int) -> List[db_item.Word]:
    """取某书全部词，经 word_book_words 关联并按 position 排序"""
    stmt = (
        select(db_item.Word)
        .join(db_item.WordBookWord, db_item.WordBookWord.word_id == db_item.Word.id)
        .where(db_item.WordBookWord.book_id == book_id)
        .order_by(db_item.WordBookWord.position)
    )
    return list(db.execute(stmt).scalars().all())


def Word_CountByBook(db: Session, book_id: int) -> int:
    """某书包含的单词数（经关联表统计）"""
    return _count(db, db_item.WordBookWord, [db_item.WordBookWord.book_id == book_id])


def WordBook_AddWord(
    db: Session, book_id: int, word_id: int, position: int
) -> db_item.WordBookWord:
    """把词加入某书（写关联表）并递增 word_books.word_count"""
    rel = db_item.WordBookWord(book_id=book_id, word_id=word_id, position=position)
    db.add(rel)
    book = db.get(db_item.WordBook, book_id)
    if book is not None:
        book.word_count += 1
    db.commit()
    db.refresh(rel)
    return rel


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


def Record_CountLearnedSince(db: Session, user_id: int, since) -> int:
    """统计首次学习时间落在 since 之后的记录数（今日已学新词数）"""
    return _count(
        db,
        db_item.UserWordRecord,
        [
            db_item.UserWordRecord.user_id == user_id,
            db_item.UserWordRecord.learned_at >= since,
        ],
    )


def Record_ListLearnedSince(db: Session, user_id: int, since) -> List[db_item.UserWordRecord]:
    """今日已学（learned_at 落在 since 之后）的记录，供拼写练习使用"""
    return _list(
        db,
        db_item.UserWordRecord,
        filters=[
            db_item.UserWordRecord.user_id == user_id,
            db_item.UserWordRecord.learned_at >= since,
        ],
    )


def Record_ListInBook(db: Session, user_id: int, word_ids: Sequence) -> List[db_item.UserWordRecord]:
    return _list(
        db,
        db_item.UserWordRecord,
        filters=[db_item.UserWordRecord.user_id == user_id, db_item.UserWordRecord.word_id.in_(word_ids)],
    )


def Record_AddAll(db: Session, records: Iterable[db_item.UserWordRecord]) -> int:
    return _add_all(db, records)


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
# 用户设置 UserSetting
# ================================================================

def Setting_Get(db: Session, user_id: int, key: str, default: str | None = None) -> str | None:
    """读取用户某项设置；不存在返回 default"""
    row = _get_by(db, db_item.UserSetting, db_item.UserSetting.key, key)
    if row is None or row.user_id != user_id:
        return default
    return row.value


def Setting_Set(db: Session, user_id: int, key: str, value: str) -> str:
    """写入用户设置（存在则更新），返回写入后的值"""
    row = (
        db.query(db_item.UserSetting)
        .filter_by(user_id=user_id, key=key)
        .first()
    )
    if row is None:
        row = db_item.UserSetting(user_id=user_id, key=key, value=value)
        db.add(row)
    else:
        row.value = value
    db.commit()
    return value


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
    avatar: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    bio: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    """更新个人信息（部分字段，不传则不修改）"""
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    email: Optional[EmailStr] = None
    avatar: Optional[str] = None
    age: Optional[int] = Field(None, ge=1, le=150)
    gender: Optional[str] = Field(None, pattern="^(male|female|other)$")
    bio: Optional[str] = Field(None, max_length=500)


class ChangePasswordRequest(BaseModel):
    """修改密码"""
    old_password: str = Field(..., min_length=6, max_length=128)
    new_password: str = Field(..., min_length=6, max_length=128)


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
    # 词可属多本书，不再有单一 book_id；如需书内上下文字段请另行提供
    id: int
    word: str
    phonetic: Optional[str]
    meaning: str
    example: Optional[str]

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
    daily_target: int
    learn_count: int    # 今日可学新词数 = min(未学总数, daily_target)
    total_new: int      # 全部未学新词数（含未分配到今日的）
    total_due: int      # 到期复习数
    mastered: int


class TodayCardsResponse(BaseModel):
    new_cards: list[WordCard]
    due_cards: list[WordCard]
    learned_cards: list[WordCard]  # 今日已学新词，供拼写练习
    summary: TodaySummary


class LearningProgressResponse(BaseModel):
    """某本书学习进度"""
    book_id: int
    total: int
    learning: int
    mastered: int
    progress_rate: float  # 0-1


# ---------------- 统计 ----------------

class TodayStat(BaseModel):
    learned: int = 0
    reviewed: int = 0
    accuracy_rate: float = 0.0


class TotalStat(BaseModel):
    words_total: int = 0    # 所选词书单词总数（学习目标）
    words_learned: int = 0  # 已学（learned_at 已标记）
    words_mastered: int = 0
    days_total: int = 0     # 累计学习天数


class DayStat(BaseModel):
    """某一天的学习记录"""
    date: str
    learned: int  # 当天新学
    reviewed: int  # 当天学习/复习总数


class StreakStat(BaseModel):
    current_streak_days: int = 0
    max_streak_days: int = 0


class DashboardStats(BaseModel):
    today: TodayStat
    total: TotalStat
    streak: StreakStat
    days: list[DayStat]


# ---------------- 设置 ----------------

class SettingsUpdateRequest(BaseModel):
    """更新用户设置"""
    daily_target: int = Field(..., ge=1, le=500)
    current_book_id: Optional[int] = None


class SettingsResponse(BaseModel):
    """用户设置响应"""
    daily_target: int
    current_book_id: Optional[int] = None


class HeatmapData(BaseModel):
    """近 365 天学习热力图"""
    dates: list[str]      # ISO 日期
    counts: list[int]     # 对应学习数