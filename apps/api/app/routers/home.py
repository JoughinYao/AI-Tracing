from __future__ import annotations

from datetime import datetime, time, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import ContentItemRelation, CrawlBatch, DailyReport, DailyReportItem, Item, Source
from ..schemas import HomeTodayResponse, BatchRead, SourceRead, ItemRead, RelationUpdateRead
from ..services.ranking import SHANGHAI
from ..services.related_third_party import attach_related_third_party

router = APIRouter(prefix="/api", tags=["home"])


def get_session():
    with session_scope() as session:
        yield session


@router.get("/home/today", response_model=HomeTodayResponse)
def home_today(session: Session = Depends(get_session)):
    today = datetime.now(timezone.utc).astimezone(SHANGHAI).date()
    batch = session.scalar(
        select(CrawlBatch)
        .order_by(CrawlBatch.id.desc())
    )
    report = session.scalar(select(DailyReport).where(DailyReport.report_date == today))
    top6 = []
    if report:
        top6 = list(
            session.scalars(
                select(Item)
                .join(DailyReportItem, DailyReportItem.item_id == Item.id)
                .where(DailyReportItem.report_id == report.id)
                .order_by(DailyReportItem.sort_order.asc())
            ).all()
        )
    attach_related_third_party(session, top6)
    relation_updates = _relation_updates_today(session, today)
    sources = session.scalars(select(Source).order_by(Source.id.asc())).all()
    has_updates = len(top6) > 0 or len(relation_updates) > 0
    status_text = "今日暂无消息" if not has_updates else f"今日更新 {len(top6)} 条"
    return HomeTodayResponse(
        report_date=today,
        has_updates=has_updates,
        is_empty=not has_updates,
        status_text=status_text,
        batch=BatchRead.model_validate(batch) if batch else None,
        relation_updates=relation_updates,
        top6=[ItemRead.model_validate(item) for item in top6],
        sources=[SourceRead.model_validate(source) for source in sources],
    )


def _relation_updates_today(session: Session, today) -> list[RelationUpdateRead]:
    start = datetime.combine(today, time.min, tzinfo=SHANGHAI).astimezone(timezone.utc)
    end = datetime.combine(today, time.max, tzinfo=SHANGHAI).astimezone(timezone.utc)
    relations = list(
        session.scalars(
            select(ContentItemRelation)
            .where(ContentItemRelation.created_at >= start, ContentItemRelation.created_at <= end)
            .order_by(ContentItemRelation.created_at.desc(), ContentItemRelation.id.desc())
        ).all()
    )
    if not relations:
        return []

    official_ids = {relation.official_item_id for relation in relations}
    third_party_ids = {relation.third_party_item_id for relation in relations}
    official_items = {
        item.id: item
        for item in session.scalars(select(Item).where(Item.id.in_(official_ids))).all()
    }
    third_party_items = {
        item.id: item
        for item in session.scalars(select(Item).where(Item.id.in_(third_party_ids))).all()
    }
    source_names = {item.source_name for item in third_party_items.values()}
    source_display_names = {
        source.source_name: source.display_name
        for source in session.scalars(select(Source).where(Source.source_name.in_(source_names))).all()
    }

    grouped: dict[int, list[ContentItemRelation]] = {}
    for relation in relations:
        official_item = official_items.get(relation.official_item_id)
        if not official_item or not _is_old_official_item(official_item, today):
            continue
        grouped.setdefault(relation.official_item_id, []).append(relation)

    updates: list[RelationUpdateRead] = []
    for official_id, relation_rows in grouped.items():
        official_item = official_items[official_id]
        latest_relation = relation_rows[0]
        latest_third_party = third_party_items.get(latest_relation.third_party_item_id)
        updates.append(
            RelationUpdateRead(
                official_item_id=official_item.id,
                official_internal_id=_internal_item_id(official_item),
                official_title=official_item.title,
                last_relation_added_at=latest_relation.created_at,
                relation_update_count_today=len(relation_rows),
                latest_relation_title=latest_third_party.title if latest_third_party else None,
                latest_relation_source_name=latest_third_party.source_name if latest_third_party else None,
                latest_relation_source_display_name=source_display_names.get(latest_third_party.source_name, latest_third_party.source_name) if latest_third_party else None,
            )
        )
    return sorted(updates, key=lambda update: update.last_relation_added_at, reverse=True)[:6]


def _is_old_official_item(item: Item, today) -> bool:
    if item.published_at is None:
        return True
    published_at = item.published_at
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    return published_at.astimezone(SHANGHAI).date() != today


def _internal_item_id(item: Item) -> str:
    prefix = "repository" if item.source_origin == "repository" else "official"
    return f"{prefix}_{item.id}"
