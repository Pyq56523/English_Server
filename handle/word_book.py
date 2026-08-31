"""单词书业务处理：列表 / 详情含学习进度"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

import database.database_item as db_item
import database.database_operate as db_operate
from utils.dependencies import get_current_user, get_db
from utils.exceptions import ok


def list_books(category: Optional[str] = None, db: Session = Depends(get_db)):
    """单词书列表：可选按分类过滤"""
    books = db_operate.WordBook_List(db, category)
    return ok(data=[db_operate.WordBookResponse.model_validate(b).model_dump(mode="json") for b in books])


def get_book(book_id: int, user: db_item.User = Depends(get_current_user), db: Session = Depends(get_db)):
    """单词书详情 + 当前用户学习进度"""
    book = db_operate.WordBook_Get(db, book_id)
    if book is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "WordBook not found")

    detail = db_operate.WordBookDetailResponse.model_validate(book)
    word_ids = [w.id for w in db_operate.Word_ListByBook(db, book_id)]
    if word_ids:
        records = db_operate.Record_ListInBook(db, user.id, word_ids)
        detail.learned_count = len([r for r in records if r.status != "new"])
        detail.mastered_count = len([r for r in records if r.status == "mastered"])
    return ok(data=detail.model_dump(mode="json"))