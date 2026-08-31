"""语法课业务处理：列表 / 详情"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

import database.database_item as db_item
import database.database_operate as db_operate
from utils.dependencies import get_db
from utils.exceptions import ok


def list_lessons(
    category: Optional[str] = None,
    level: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """语法课列表：可选按分类 / 难度过滤"""
    lessons = db_operate.Grammar_List(db, category, level)
    return ok(data=[db_operate.GrammarLessonList.model_validate(l).model_dump(mode="json") for l in lessons])


def get_lesson(lesson_id: int, db: Session = Depends(get_db)):
    """语法课详情"""
    lesson = db_operate.Grammar_Get(db, lesson_id)
    if lesson is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson not found")
    return ok(data=db_operate.GrammarLessonDetail.model_validate(lesson).model_dump(mode="json"))