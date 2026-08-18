from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import SystemLog
from ..schemas import SystemLogRead

router = APIRouter(prefix="/api", tags=["logs"])


def get_session():
    with session_scope() as session:
        yield session


@router.get("/system-logs", response_model=list[SystemLogRead])
def list_logs(
    date: str | None = Query(default=None),
    days: int | None = Query(default=None, ge=1, le=30),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    query = select(SystemLog)
    if date:
        query = query.where(func.date(SystemLog.log_date) == date)
    elif days:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.where(SystemLog.log_date >= since)
    rows = session.scalars(query.order_by(SystemLog.log_date.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    return [SystemLogRead.model_validate(row) for row in rows]
