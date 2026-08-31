"""常用短语业务处理：列表 / 详情"""
from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

import database.database_item as db_item
import database.database_operate as db_operate
from utils.dependencies import get_db
from utils.exceptions import ok


def list_phrases(
    category: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
):
    """短语列表：可选按分类过滤、分页"""
    total = db_operate.Phrase_Count(db, category)
    phrases = db_operate.Phrase_List(db, category, offset=(page - 1) * page_size, limit=page_size)
    items = [db_operate.PhraseResponse.model_validate(p).model_dump(mode="json") for p in phrases]
    result = db_operate.PhrasePageResponse(total=total, page=page, page_size=page_size, items=items)
    return ok(data=result.model_dump(mode="json"))


def get_phrase(phrase_id: int, db: Session = Depends(get_db)):
    """短语详情"""
    phrase = db_operate.Phrase_Get(db, phrase_id)
    if phrase is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Phrase not found")
    return ok(data=db_operate.PhraseResponse.model_validate(phrase).model_dump(mode="json"))