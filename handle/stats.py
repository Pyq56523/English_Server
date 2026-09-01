"""统计业务处理：仪表盘 / 热力图 / 连续打卡"""
from datetime import datetime, timedelta

from fastapi import Depends
from sqlalchemy.orm import Session

import database.database_item as db_item
import database.database_operate as db_operate
from utils.dependencies import get_current_user, get_db
from utils.exceptions import ok


# ---------- 内部工具 ----------

def _streak(db: Session, user_id: int) -> db_operate.StreakStat:
    records = db_operate.Record_ListByUser(db, user_id, review_only=True)
    active_days = {r.last_review_at.strftime("%Y-%m-%d") for r in records}

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


# ---------- 端点函数 ----------

def dashboard(user: db_item.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """学习仪表盘统计

    口径说明：
    - 今日数据仅统计今日实际复习过的记录（last_review_at 落在今天）：
      选中词书只会在 user_word_records 生成 new 记录（last_review_at 为空），
      不会计入今日新学/复习，因此未学习时今日新学 = 0。
    - words_learned 只统计用户真正复习过的词，而非所选词书包含的全部词。
    """
    today = db_operate.Record_ListByUser(
        db,
        user.id,
        since=datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0),
    )
    reviewed = len(today)
    learned = len([r for r in today if r.repetition <= 1])

    words_learned = len(db_operate.Record_ListByUser(db, user.id, review_only=True))
    mastered = db_operate.UserMastered_Count(db, user.id)
    accuracy = round(learned / max(reviewed, 1), 2) if reviewed else 0.0

    result = db_operate.DashboardStats(
        today=db_operate.TodayStat(learned=learned, reviewed=reviewed, accuracy_rate=accuracy),
        total=db_operate.TotalStat(
            words_learned=words_learned,
            words_mastered=mastered,
        ),
        streak=_streak(db, user.id),
    )
    return ok(data=result.model_dump(mode="json"))


def heatmap(user: db_item.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """近 365 天每天复习数热力图"""
    days = 365
    records = db_operate.Record_ListByUser(db, user.id, since=datetime.utcnow() - timedelta(days=days))
    by_date: dict[str, int] = {}
    for r in records:
        if r.last_review_at:
            key = r.last_review_at.strftime("%Y-%m-%d")
            by_date[key] = by_date.get(key, 0) + 1

    dates: list[str] = []
    counts: list[int] = []
    for i in range(days - 1, -1, -1):
        d = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        dates.append(d)
        counts.append(by_date.get(d, 0))
    return ok(data=db_operate.HeatmapData(dates=dates, counts=counts).model_dump(mode="json"))


def streak(user: db_item.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """连续打卡统计"""
    return ok(data=_streak(db, user.id).model_dump(mode="json"))