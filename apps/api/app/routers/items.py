from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..db import session_scope
from ..categories import category_for_section
from ..models import CrawlBatch, Item
from ..schemas import ItemPage, ItemRead
from ..services.related_third_party import attach_related_third_party

router = APIRouter(prefix="/api", tags=["items"])


def get_session():
    with session_scope() as session:
        yield session


@router.get("/items", response_model=ItemPage)
def list_items(
    section: str = Query(default="core-agent"),
    date: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    query = select(Item).where(Item.related_official_item_id.is_(None))
    category = category_for_section(section)
    if category:
        query = query.where(Item.category == category)

    if date:
        batch_ids = select(CrawlBatch.id).where(func.date(CrawlBatch.batch_date) == date)
        query = query.where(Item.crawl_batch_id.in_(batch_ids))

    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    total_pages = max(1, (total + page_size - 1) // page_size)
    rows = session.scalars(query.order_by(Item.published_at.desc().nullslast(), Item.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    attach_related_third_party(session, rows)
    return ItemPage(items=[ItemRead.model_validate(item) for item in rows], page=page, page_size=page_size, total=total, total_pages=total_pages)
