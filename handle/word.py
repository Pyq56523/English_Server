"""单词业务处理：分页搜索 / 详情"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

import database.database_item as db_item
import database.database_operate as db_operate
from utils.dependencies import get_db
from utils.exceptions import ok


def list_words(
    book_id: Optional[int] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """单词列表：按书 / 关键词过滤、分页"""
    total = db_operate.Word_Count(db, book_id, keyword)
    words = db_operate.Word_List(db, book_id, keyword, offset=(page - 1) * page_size, limit=page_size)
    items = [db_operate.WordResponse.model_validate(w).model_dump(mode="json") for w in words]
    result = db_operate.WordPageResponse(total=total, page=page, page_size=page_size, items=items)
    return ok(data=result.model_dump(mode="json"))


def get_word(word_id: int, db: Session = Depends(get_db)):
    """单词详情"""
    word = db_operate.Word_Get(db, word_id)
    if word is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Word not found")
    return ok(data=db_operate.WordResponse.model_validate(word).model_dump(mode="json"))