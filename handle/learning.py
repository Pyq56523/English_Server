"""学习业务处理：今日卡片 / 开始学习 / 提交复习(SM-2) / 进度"""
from datetime import datetime, timedelta

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

import database.database_item as db_item
import database.database_operate as db_operate
from utils.dependencies import get_current_user, get_db
from utils.exceptions import ok


# ---------- SM-2 核心（纯函数，无 DB 依赖） ----------

def sm2_update(record: db_item.UserWordRecord, quality: int) -> db_item.UserWordRecord:
    """SM-2 核心计算（纯函数，便于单元测试）

    见 docs/ARCHITECTURE.md 第 4 节算法伪代码。
    """
    quality = int(quality)
    # 1. 更新难度因子 E-Factor
    record.ease_factor = max(
        db_item.MIN_EASE_FACTOR,
        record.ease_factor
        + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)),
    )

    # 2. 根据评分调整间隔
    if quality >= 3:
        if record.repetition == 0:
            record.interval_days = 1
        elif record.repetition == 1:
            record.interval_days = 6
        else:
            record.interval_days = round(record.interval_days * record.ease_factor)
        record.repetition += 1
        record.status = db_item.STATUS_MASTERED if record.repetition >= 5 else db_item.STATUS_LEARNING
    else:
        # 没记住 → 重置
        record.repetition = 0
        record.interval_days = 1
        record.status = db_item.STATUS_LEARNING

    # 3. 更新时间
    now = datetime.utcnow()
    record.last_review_at = now
    record.next_review_at = now + timedelta(days=record.interval_days)
    return record


# ---------- 内部工具 ----------

def _to_word_card(db: Session, record: db_item.UserWordRecord, with_record: bool) -> db_operate.WordCard:
    word = db_operate.Word_Get(db, record.word_id)
    return db_operate.WordCard(
        word_id=record.word_id,
        word=word.word,
        phonetic=word.phonetic,
        meaning=word.meaning,
        example=word.example,
        record_id=record.id if with_record else None,
        repetition=record.repetition if with_record else None,
        interval_days=record.interval_days if with_record else None,
    )


def _get_today_cards(db: Session, user_id: int) -> db_operate.TodayCardsResponse:
    today = datetime.utcnow()
    day_start = today.replace(hour=0, minute=0, second=0, microsecond=0)
    # 每日新学目标取自用户设置；复习不限量，按遗忘曲线到期全部取出
    daily_target = int(
        db_operate.Setting_Get(
            db, user_id, "daily_target", str(db_item.DEFAULT_DAILY_TARGET)
        )
    )
    # 今日已学新词数：达到计划后不再发放新词
    learned_today = db_operate.Record_CountLearnedSince(db, user_id, day_start)
    remaining = max(0, daily_target - learned_today)
    new_cards = [_to_word_card(db, r, True) for r in db_operate.Record_ListNew(db, user_id, remaining)]
    due_cards = [_to_word_card(db, r, True) for r in db_operate.Record_ListDue(db, user_id, today)]
    total_new = db_operate.Record_Count(db, user_id, db_item.STATUS_NEW)
    return db_operate.TodayCardsResponse(
        new_cards=new_cards,
        due_cards=due_cards,
        learned_cards=[
            _to_word_card(db, r, True)
            for r in db_operate.Record_ListLearnedSince(db, user_id, day_start)
        ],
        summary=db_operate.TodaySummary(
            daily_target=daily_target,
            learn_count=len(new_cards),
            total_new=total_new,
            total_due=len(due_cards),
            mastered=db_operate.Record_Count(db, user_id, db_item.STATUS_MASTERED),
        ),
    )


# ---------- 端点函数 ----------

def today_cards(user: db_item.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """今日学习卡片（新卡 + 到期复习卡）"""
    return ok(data=_get_today_cards(db, user.id).model_dump(mode="json"))


def start_learning(
    payload: db_operate.StartLearningRequest,
    user: db_item.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """初始化某本单词书的学习记录，返回新增条数"""
    if db_operate.WordBook_Get(db, payload.book_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "WordBook not found")

    existing = {r.word_id for r in db_operate.Record_ListByUser(db, user.id)}
    record_list = [
        db_item.UserWordRecord(
            user_id=user.id,
            word_id=w.id,
            status=db_item.STATUS_NEW,
            ease_factor=2.5,
            interval_days=0,
            repetition=0,
        )
        for w in db_operate.Word_ListByBook(db, payload.book_id)
        if w.id not in existing
    ]
    count = db_operate.Record_AddAll(db, record_list) if record_list else 0
    return ok(data={"initialized": count}, message="Learning started")


def review(
    payload: db_operate.ReviewRequest,
    user: db_item.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """提交复习评分并执行 SM-2 算法"""
    record = db_operate.Record_Get(db, payload.record_id)
    if record is None or record.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Record not found")

    was_new = record.status == db_item.STATUS_NEW
    sm2_update(record, payload.quality)
    # 首次学习（从 new 转出）时记录今天，用于计算今日已学新词数
    if was_new and record.learned_at is None:
        record.learned_at = datetime.utcnow()
    db_operate.DB_Commit(db)
    result = db_operate.ReviewResponse(
        record_id=record.id,
        word_id=record.word_id,
        new_ease_factor=round(record.ease_factor, 2),
        new_interval_days=record.interval_days,
        next_review_at=record.next_review_at,
        status=record.status,
    )
    return ok(data=result.model_dump(mode="json"), message="Review saved")


def get_progress(
    book_id: int,
    user: db_item.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """某本书的学习进度"""
    word_ids = [w.id for w in db_operate.Word_ListByBook(db, book_id)]
    if not word_ids:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No words in this book")

    records = db_operate.Record_ListInBook(db, user.id, word_ids)
    learning = len([r for r in records if r.status == db_item.STATUS_LEARNING])
    mastered = len([r for r in records if r.status == db_item.STATUS_MASTERED])
    result = db_operate.LearningProgressResponse(
        book_id=book_id,
        total=len(word_ids),
        learning=learning,
        mastered=mastered,
        progress_rate=round((learning + mastered) / len(word_ids), 2),
    )
    return ok(data=result.model_dump(mode="json"))