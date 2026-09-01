"""用户设置业务处理：每日学习目标等（按用户持久化到后端）"""
from fastapi import Depends
from sqlalchemy.orm import Session

import database.database_item as db_item
import database.database_operate as db_operate
from utils.dependencies import get_current_user, get_db
from utils.exceptions import ok


def get_settings(
    user: db_item.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """读取当前用户设置"""
    daily_target = int(
        db_operate.Setting_Get(
            db, user.id, "daily_target", str(db_item.DEFAULT_DAILY_TARGET)
        )
    )
    return ok(
        data=db_operate.SettingsResponse(daily_target=daily_target).model_dump(mode="json")
    )


def update_settings(
    payload: db_operate.SettingsUpdateRequest,
    user: db_item.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """更新当前用户设置"""
    db_operate.Setting_Set(db, user.id, "daily_target", str(payload.daily_target))
    return ok(
        data=db_operate.SettingsResponse(daily_target=payload.daily_target).model_dump(mode="json"),
        message="Settings saved",
    )