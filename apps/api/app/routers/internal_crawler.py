from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import session_scope
from ..models import Item, Source, SystemLog
from ..schemas import (
    OfficialCandidateRead,
    OfficialCandidatesRequest,
    OfficialCandidatesResponse,
    OfficialItemDetailRead,
    OfficialItemsDetailRequest,
    OfficialItemsDetailResponse,
)
from ..services.related_third_party import attach_related_third_party


router = APIRouter(prefix="/internal/crawler", tags=["internal-crawler"])
settings = get_settings()
ANCHOR_ORIGINS = {"official", "repository"}
logger = logging.getLogger(__name__)


def get_session():
    with session_scope() as session:
        yield session


def verify_internal_token(authorization: str | None = Header(default=None)) -> None:
    if not settings.system_internal_token:
        return
    if authorization != f"Bearer {settings.system_internal_token}":
        raise HTTPException(status_code=401, detail="Invalid internal token.")


@router.post("/official-candidates", response_model=OfficialCandidatesResponse, dependencies=[Depends(verify_internal_token)])
def official_candidates(request: OfficialCandidatesRequest, session: Session = Depends(get_session)):
    now = datetime.now(timezone.utc)
    logger.info("crawler -> system official candidates request query_count=%s", len(request.queries))
    session.add(
        SystemLog(
            log_date=now,
            level="info",
            source_name=None,
            action="crawler_official_candidates_requested",
            message="爬虫端请求官方候选消息",
            context={"query_count": len(request.queries)},
        )
    )
    rows: list[Item] = []
    seen_ids: set[int] = set()

    for query in request.queries:
        company = _normalize_company(query.company)
        domain = _normalize_domain(query.domain)
        if not company or not domain:
            continue
        cutoff = now - timedelta(days=query.since_days)
        candidates = session.scalars(
            select(Item)
            .where(
                Item.company == company,
                Item.domain == domain,
                Item.source_origin.in_(ANCHOR_ORIGINS),
                Item.related_official_item_id.is_(None),
                Item.published_at.is_not(None),
                Item.published_at >= cutoff,
            )
            .order_by(Item.published_at.desc(), Item.id.desc())
            .limit(20)
        ).all()
        for item in candidates:
            if item.id not in seen_ids:
                rows.append(item)
                seen_ids.add(item.id)

    source_display_names = _source_display_names(session, rows)
    return OfficialCandidatesResponse(
        items=[
            OfficialCandidateRead(
                id=_internal_item_id(item),
                company=item.company,
                domain=item.domain or "other",
                title=item.title,
                published_at=item.published_at,
                source_name=item.source_name,
                source_display_name=source_display_names.get(item.source_name, item.source_name),
            )
            for item in rows
        ]
    )


@router.post("/official-items/detail", response_model=OfficialItemsDetailResponse, dependencies=[Depends(verify_internal_token)])
def official_items_detail(request: OfficialItemsDetailRequest, session: Session = Depends(get_session)):
    now = datetime.now(timezone.utc)
    logger.info("crawler -> system official item detail request item_count=%s", len(request.ids))
    session.add(
        SystemLog(
            log_date=now,
            level="info",
            source_name=None,
            action="crawler_official_detail_requested",
            message="爬虫端请求官方消息详情",
            context={"item_count": len(request.ids)},
        )
    )
    items = _items_by_internal_ids(session, request.ids)
    attach_related_third_party(session, items)
    source_display_names = _source_display_names(session, items)
    return OfficialItemsDetailResponse(
        items=[
            OfficialItemDetailRead(
                id=_internal_item_id(item),
                company=item.company,
                domain=item.domain or "other",
                title=item.title,
                summary=item.summary,
                content_excerpt=item.content_excerpt,
                published_at=item.published_at,
                source_name=item.source_name,
                source_display_name=source_display_names.get(item.source_name, item.source_name),
                original_url=item.original_url,
                related_third_party=getattr(item, "related_third_party", []),
            )
            for item in items
        ]
    )


def _source_display_names(session: Session, items: list[Item]) -> dict[str, str]:
    source_names = {item.source_name for item in items}
    if not source_names:
        return {}
    return {
        source.source_name: source.display_name
        for source in session.scalars(select(Source).where(Source.source_name.in_(source_names))).all()
    }


def _items_by_internal_ids(session: Session, values: list[str]) -> list[Item]:
    items: list[Item] = []
    seen_ids: set[int] = set()
    for value in values:
        item = _item_by_internal_id(session, value)
        if item and item.id not in seen_ids and item.source_origin in ANCHOR_ORIGINS:
            items.append(item)
            seen_ids.add(item.id)
    return items


def _item_by_internal_id(session: Session, value: object) -> Item | None:
    target = str(value).strip()
    if not target:
        return None
    item_id = _parse_internal_item_id(target)
    if item_id is not None:
        return session.get(Item, item_id)
    return session.scalar(select(Item).where(Item.external_id == target).limit(1))


def _internal_item_id(item: Item) -> str:
    prefix = "repository" if item.source_origin == "repository" else "official"
    return f"{prefix}_{item.id}"


def _parse_internal_item_id(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    if "_" not in value:
        return None
    prefix, raw_id = value.rsplit("_", 1)
    if prefix in {"official", "repository"} and raw_id.isdigit():
        return int(raw_id)
    return None


def _normalize_company(value: object) -> str | None:
    company = str(value).strip().lower()
    return company or None


def _normalize_domain(value: object) -> str | None:
    domain = str(value).strip().lower()
    return domain if domain in {"agent", "llm", "other"} else None
