"""统计业务处理：仪表盘（按当前所选词书过滤）/ 热力图 / 连续打卡"""
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends
from sqlalchemy.orm import Session

import database.database_item as db_item
import database.database_operate as db_operate
from utils.dependencies import get_current_user, get_db
from utils.exceptions import ok


# ---------- 内部工具 ----------

def _user_book_id(db: Session, user_id: int) -> Optional[int]:
    """读取用户当前选择的单词书 id（后端持久化）"""
    v = db_operate.Setting_Get(db, user_id, "current_book_id")
    return int(v) if v else None


def _book_word_ids(db: Session, book_id: int) -> set[int]:
    """返回某词书包含的所有 word_id"""
    rows = db_operate._list(
        db, db_item.WordBookWord,
        filters=[db_item.WordBookWord.book_id == book_id],
    )
    return {r.word_id for r in rows}


def _filter_by_book(records: list, word_ids: set[int]) -> list:
    """把 record 列表过滤到属于某词书的子集"""
    if not word_ids:
        return records
    return [r for r in records if r.word_id in word_ids]


def _streak(db: Session, user_id: int, word_ids: Optional[set[int]] = None) -> db_operate.StreakStat:
    records = db_operate.Record_ListByUser(db, user_id, review_only=True)
    if word_ids is None:
        records = []
    elif word_ids:
        records = _filter_by_book(records, word_ids)
    active_days = {r.last_review_at.strftime("%Y-%m-%d") for r in records if r.last_review_at}

    # 当前连续（含今天或昨天）
    cursor = datetime.now().date()
    if cursor.strftime("%Y-%m-%d") not in active_days:
        cursor -= timedelta(days=1)
    current = 0
    while cursor.strftime("%Y-%m-%d") in active_days:
        current += 1
        cursor -= timedelta(days=1)

    # 最大连续
    max_streak = 0
    run = 0
    prev = None
    for day in sorted(active_days):
        d = datetime.strptime(day, "%Y-%m-%d").date()
        run = run + 1 if (prev is not None and (d - prev).days == 1) else 1
        max_streak = max(max_streak, run)
        prev = d

    return db_operate.StreakStat(current_streak_days=current, max_streak_days=max_streak)


def _learning_days(db: Session, user_id: int, word_ids: Optional[set[int]] = None) -> int:
    """累计学习天数（distinct 有过 last_review_at 的日期）"""
    records = db_operate.Record_ListByUser(db, user_id, review_only=True)
    if word_ids is None:
        records = []
    elif word_ids:
        records = _filter_by_book(records, word_ids)
    days = {r.last_review_at.strftime("%Y-%m-%d") for r in records if r.last_review_at}
    return len(days)


# ---------- 端点函数 ----------

def _parse_date(s: str):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _daily_series(db: Session, user_id: int, start_date, end_date, word_ids=None) -> list:
    """返回 [start, end] 内每天的学习记录"""
    if end_date is None:
        end_date = datetime.now().date()
    if start_date is None:
        start_date = end_date - timedelta(days=6)  # 默认一周

    all_records = db_operate.Record_ListByUser(db, user_id)
    records = (
        []
        if word_ids is None
        else _filter_by_book(all_records, word_ids)
    )

    learned_by_day: dict[str, int] = {}
    reviewed_by_day: dict[str, int] = {}
    for r in records:
        if r.learned_at:
            key = r.learned_at.strftime("%Y-%m-%d")
            learned_by_day[key] = learned_by_day.get(key, 0) + 1
        if r.last_review_at:
            key = r.last_review_at.strftime("%Y-%m-%d")
            reviewed_by_day[key] = reviewed_by_day.get(key, 0) + 1

    days: list[db_operate.DayStat] = []
    cursor = start_date
    while cursor <= end_date:
        key = cursor.strftime("%Y-%m-%d")
        days.append(
            db_operate.DayStat(
                date=key,
                learned=learned_by_day.get(key, 0),
                reviewed=reviewed_by_day.get(key, 0),
            )
        )
        cursor += timedelta(days=1)
    return days


def dashboard(
    start_date: str = "",
    end_date: str = "",
    user: db_item.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """学习仪表盘统计（按当前所选词书过滤，未选词书时数据为 0）"""
    book_id = _user_book_id(db, user.id)
    word_ids = _book_word_ids(db, book_id) if book_id else None

    local_today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    all_records = db_operate.Record_ListByUser(db, user.id)
    # 未选词书时返回空，不展示任何历史残留数据
    if word_ids is None:
        records = []
    else:
        records = _filter_by_book(all_records, word_ids)

    # 今日学习（本地时区）
    today_records = [
        r for r in records
        if r.last_review_at is not None and r.last_review_at >= local_today_start
    ]
    reviewed = len(today_records)
    learned = len([r for r in today_records if r.repetition <= 1])

    # 总数
    words_total = len(records)  # 所选词书已建记录数
    words_learned = len([r for r in records if r.learned_at is not None])
    accuracy = round(learned / max(reviewed, 1), 2) if reviewed else 0.0

    result = db_operate.DashboardStats(
        today=db_operate.TodayStat(learned=learned, reviewed=reviewed, accuracy_rate=accuracy),
        total=db_operate.TotalStat(
            words_total=words_total,
            words_learned=words_learned,
            days_total=_learning_days(db, user.id, word_ids),
        ),
        streak=_streak(db, user.id, word_ids),
        days=_daily_series(db, user.id, _parse_date(start_date), _parse_date(end_date), word_ids),
    )
    return ok(data=result.model_dump(mode="json"))


def heatmap(user: db_item.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """近 365 天每天复习数热力图"""
    days = 365
    records = db_operate.Record_ListByUser(
        db, user.id, since=datetime.now() - timedelta(days=days)
    )
    by_date: dict[str, int] = {}
    for r in records:
        if r.last_review_at:
            key = r.last_review_at.strftime("%Y-%m-%d")
            by_date[key] = by_date.get(key, 0) + 1

    dates: list[str] = []
    counts: list[int] = []
    for i in range(days - 1, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        dates.append(d)
        counts.append(by_date.get(d, 0))
    return ok(data=db_operate.HeatmapData(dates=dates, counts=counts).model_dump(mode="json"))


def streak(user: db_item.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """连续打卡统计（全局）"""
    return ok(data=_streak(db, user.id).model_dump(mode="json"))