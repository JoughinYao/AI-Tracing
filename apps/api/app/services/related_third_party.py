from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ContentItemRelation, Item, Source


def attach_related_third_party(session: Session, items: list[Item]) -> None:
    official_ids = [item.id for item in items]
    if not official_ids:
        return

    relations = list(
        session.scalars(
            select(ContentItemRelation)
            .where(ContentItemRelation.official_item_id.in_(official_ids))
            .order_by(ContentItemRelation.created_at.desc(), ContentItemRelation.id.desc())
        ).all()
    )
    if not relations:
        for item in items:
            item.related_third_party = []
        return

    third_party_ids = [relation.third_party_item_id for relation in relations]
    third_party_items = {
        item.id: item
        for item in session.scalars(select(Item).where(Item.id.in_(third_party_ids))).all()
    }
    source_names = {item.source_name for item in third_party_items.values()}
    source_display_names = {
        source.source_name: source.display_name
        for source in session.scalars(select(Source).where(Source.source_name.in_(source_names))).all()
    }

    by_official_id: dict[int, list[dict]] = {item.id: [] for item in items}
    for relation in relations:
        third_party_item = third_party_items.get(relation.third_party_item_id)
        if not third_party_item:
            continue
        metadata = third_party_item.extra_metadata or {}
        by_official_id.setdefault(relation.official_item_id, []).append(
            {
                "relation_type": relation.relation_type,
                "relation_confidence": relation.relation_confidence,
                "relation_reason": relation.relation_reason,
                "title": third_party_item.title,
                "summary": third_party_item.summary,
                "author": third_party_item.author,
                "published_at": third_party_item.published_at,
                "source_name": third_party_item.source_name,
                "source_display_name": source_display_names.get(third_party_item.source_name, third_party_item.source_name),
                "original_url": third_party_item.original_url,
                "sentiment": metadata.get("sentiment") or "unknown",
            }
        )

    for item in items:
        item.related_third_party = by_official_id.get(item.id, [])
