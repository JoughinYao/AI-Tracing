from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, date, timedelta
from sqlalchemy import delete, or_, select, func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from ..categories import category_for_item
from ..models import Source, CrawlBatch, CrawlSourceRun, Item, GitHubRepoMetrics, DailyReport, DailyReportItem, SystemLog, ContentComment, ContentItemRelation
from .crawler_client import crawl_source
from .ranking import RANKING_VERSION, SHANGHAI, rank_batch_items, rank_items


def ensure_today_batch(session: Session) -> CrawlBatch:
    today = datetime.now(timezone.utc)
    existing = session.scalar(
        select(CrawlBatch)
        .where(func.date(CrawlBatch.batch_date) == today.date())
        .order_by(CrawlBatch.id.desc())
    )
    if existing:
        return existing
    batch = CrawlBatch(batch_date=today, status="running", triggered_at=today, total_sources=0, success_sources=0, failed_sources=0, top6_count=0)
    session.add(batch)
    session.flush()
    return batch


@dataclass
class UpsertResult:
    saved_count: int = 0
    attached_count: int = 0
    dropped_count: int = 0
    metrics_count: int = 0


COMMENT_RELATION_TYPES = {"commentary", "benchmark", "tutorial", "related"}
ANCHOR_ORIGINS = {"official", "repository"}
MAX_SOURCE_ATTEMPTS = 3


def upsert_items(session: Session, batch: CrawlBatch, source_name: str, payload: dict) -> UpsertResult:
    result = UpsertResult()
    items = payload.get("items", [])
    source = session.scalar(select(Source).where(Source.source_name == source_name))
    incoming_hashes: set[str] = set()
    for raw in items:
        external_id = raw.get("external_id")
        if not external_id:
            continue
        metadata = raw.get("metadata") or {}
        if _is_metrics_only_item(raw):
            continue
        item_source_name = raw.get("source_name", source_name)
        item_source_type = raw.get("source_type", "github_repository")
        source_origin = raw.get("source_origin") or metadata.get("source_origin") or (source.source_origin if source else _infer_source_origin(item_source_name, item_source_type))
        company = _normalize_company(raw.get("company") or metadata.get("company"))
        domain = _normalize_domain(raw.get("domain") or metadata.get("domain"))
        relation_payload = _relation_payload(raw)
        relation_type = _relation_type(raw, relation_payload)
        original_url = raw.get("original_url")
        if _find_existing_item(session, item_source_name, external_id, original_url):
            result.dropped_count += 1
            continue
        content_hash = raw.get("content_hash")
        if content_hash:
            if content_hash in incoming_hashes:
                logger.info("dedup skip: content_hash=%s repeated in the crawler payload (skipping external_id=%s)", content_hash, external_id)
                result.dropped_count += 1
                continue
            hash_exists = session.scalar(select(Item).where(Item.content_hash == content_hash))
            if hash_exists:
                logger.info(
                    "dedup skip: content_hash=%s already exists (existing external_id=%s, skipping external_id=%s)",
                    content_hash,
                    hash_exists.external_id,
                    external_id,
                )
                result.dropped_count += 1
                continue
            incoming_hashes.add(content_hash)
        if source_origin == "third_party" and relation_type == "duplicate":
            result.dropped_count += 1
            session.add(
                SystemLog(
                    log_date=datetime.now(timezone.utc),
                    level="info",
                    source_name=item_source_name,
                    action="third_party_duplicate_dropped",
                    message=f"三方信源{item_source_name}重复转载已丢弃",
                    context={"external_id": external_id, "original_url": original_url, "relation": relation_payload},
                )
            )
            continue

        official_item = None
        matched_by = None
        if source_origin == "third_party" and relation_type in COMMENT_RELATION_TYPES:
            official_item = _find_relation_target_item(session, relation_payload)
            if official_item:
                matched_by = "relation_target_id"

        item = _build_item(
            batch=batch,
            source=source,
            raw=raw,
            source_name=item_source_name,
            source_type=item_source_type,
            source_origin=source_origin,
            company=company,
            domain=domain,
            relation_payload=relation_payload,
            relation_type=relation_type,
            related_official_item_id=official_item.id if official_item else None,
        )
        session.add(item)
        session.flush()
        result.saved_count += 1
        if official_item and relation_type in COMMENT_RELATION_TYPES:
            _attach_related_third_party(session, official_item, item, relation_type, relation_payload, matched_by)
            _attach_content_comment(session, official_item, item, raw, item_source_name, relation_type, relation_payload, metadata)
            result.attached_count += 1

    result.metrics_count = _save_metrics(session, batch, source_name, items)
    return result


def _build_item(
    *,
    batch: CrawlBatch,
    source: Source | None,
    raw: dict,
    source_name: str,
    source_type: str,
    source_origin: str,
    company: str | None,
    domain: str | None,
    relation_payload: dict | None,
    relation_type: str | None,
    related_official_item_id: int | None,
) -> Item:
    item_category = category_for_item(source_name, source_type, raw.get("category") or (source.default_category if source else None))
    metadata = dict(raw.get("metadata") or {})
    if raw.get("sentiment") is not None and "sentiment" not in metadata:
        metadata["sentiment"] = raw.get("sentiment")
    return Item(
        external_id=raw.get("external_id"),
        source_name=source_name,
        source_origin=source_origin,
        source_type=source_type,
        source_url=raw.get("source_url"),
        original_url=raw.get("original_url"),
        title=raw.get("title") or "未命名",
        summary=raw.get("summary"),
        category=item_category,
        company=company,
        domain=domain,
        event_type=raw.get("event_type"),
        entities=raw.get("entities") or [],
        tags=raw.get("tags") or [],
        published_at=_parse_dt(raw.get("published_at")),
        author=raw.get("author"),
        language=raw.get("language"),
        content_hash=raw.get("content_hash"),
        content_excerpt=raw.get("content_excerpt"),
        related_official_item_id=related_official_item_id,
        relation_type=relation_type,
        relation=relation_payload,
        extra_metadata=metadata,
        llm_status=raw.get("llm_status", "skipped"),
        processing_status=raw.get("processing_status", "normalized"),
        key_points=raw.get("key_points") or [],
        technical_details=raw.get("technical_details") or [],
        value_interpretation=raw.get("value_interpretation"),
        impact_scope=raw.get("impact_scope") or [],
        risk_or_limitations=raw.get("risk_or_limitations") or [],
        recommended_action=raw.get("recommended_action"),
        evidence_excerpts=raw.get("evidence_excerpts") or [],
        information_gaps=raw.get("information_gaps") or [],
        content_depth=raw.get("content_depth") or metadata.get("content_depth"),
        primary_image=raw.get("primary_image"),
        image_candidates=raw.get("image_candidates") or [],
        crawl_batch_id=batch.id,
        created_at=datetime.now(timezone.utc),
    )


def _find_existing_item(session: Session, source_name: str, external_id: str, original_url: str | None) -> Item | None:
    filters = [Item.external_id == external_id]
    if original_url:
        filters.append((Item.source_name == source_name) & (Item.original_url == original_url))
    return session.scalar(select(Item).where(or_(*filters)).limit(1))


def _normalize_company(value: object) -> str | None:
    if value is None:
        return None
    company = str(value).strip().lower()
    return company or None


def _normalize_domain(value: object) -> str | None:
    if value is None:
        return None
    domain = str(value).strip().lower()
    return domain if domain in {"agent", "llm", "other"} else None


def _relation_payload(raw: dict) -> dict | None:
    relation = raw.get("relation")
    return relation if isinstance(relation, dict) else None


def _relation_type(raw: dict, relation: dict | None) -> str | None:
    if relation:
        relation_type = relation.get("relation_type")
        return str(relation_type).strip() if relation_type else None
    relation_type = raw.get("relation_type")
    return str(relation_type).strip() if relation_type else None


def _find_relation_target_item(session: Session, relation: dict | None) -> Item | None:
    if not relation:
        return None
    target_id = relation.get("target_id")
    if not target_id:
        return None
    target = str(target_id).strip()
    if not target:
        return None

    item_id = _parse_internal_item_id(target)
    if item_id is not None:
        item = session.get(Item, item_id)
        return item if item and _is_anchor_item(item) else None

    item = session.scalar(select(Item).where(Item.external_id == target).limit(1))
    return item if item and _is_anchor_item(item) else None


def _parse_internal_item_id(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    if "_" not in value:
        return None
    prefix, raw_id = value.rsplit("_", 1)
    if prefix in {"official", "repository"} and raw_id.isdigit():
        return int(raw_id)
    return None


def _is_metrics_only_item(raw: dict) -> bool:
    metadata = raw.get("metadata") or {}
    return (
        raw.get("source_type") == "github_repository"
        and raw.get("event_type") == "repo_metric_change"
        and metadata.get("metrics_only") is True
    )


def _infer_source_origin(source_name: str | None, source_type: str | None) -> str:
    if source_name == "github_trending" or source_type == "github_trending":
        return "community"
    if source_type == "third_party_article":
        return "third_party"
    if source_type == "github_repository":
        return "repository"
    return "official"


def _is_anchor_item(item: Item) -> bool:
    return item.source_origin in ANCHOR_ORIGINS or item.source_type in {"github_repository", "official_changelog"}


def _attach_related_third_party(
    session: Session,
    official_item: Item,
    third_party_item: Item,
    relation_type: str,
    relation_payload: dict | None,
    matched_by: str | None,
) -> None:
    exists = session.scalar(
        select(ContentItemRelation)
        .where(
            ContentItemRelation.official_item_id == official_item.id,
            ContentItemRelation.third_party_item_id == third_party_item.id,
        )
        .limit(1)
    )
    if exists:
        return
    session.add(
        ContentItemRelation(
            official_item_id=official_item.id,
            third_party_item_id=third_party_item.id,
            relation_type=relation_type,
            relation_confidence=(relation_payload or {}).get("confidence"),
            relation_reason=(relation_payload or {}).get("reason"),
            matched_by=matched_by,
            extra_metadata={"relation": relation_payload or {}},
            created_at=datetime.now(timezone.utc),
        )
    )


def _attach_content_comment(
    session: Session,
    official_item: Item,
    third_party_item: Item,
    raw: dict,
    source_name: str,
    relation_type: str,
    relation_payload: dict | None,
    metadata: dict,
) -> None:
    original_url = third_party_item.original_url
    if original_url:
        exists = session.scalar(
            select(ContentComment)
            .where(ContentComment.official_item_id == official_item.id, ContentComment.source_name == source_name, ContentComment.original_url == original_url)
            .limit(1)
        )
        if exists:
            return
    session.add(
        ContentComment(
            official_item_id=official_item.id,
            third_party_item_id=third_party_item.id,
            source_name=source_name,
            original_url=original_url,
            title=third_party_item.title,
            summary=third_party_item.summary,
            sentiment=raw.get("sentiment") or metadata.get("sentiment") or (relation_payload or {}).get("sentiment") or "unknown",
            relation_type=relation_type,
            published_at=third_party_item.published_at,
            extra_metadata={**metadata, "relation": relation_payload or {}},
            created_at=datetime.now(timezone.utc),
        )
    )


def _save_metrics(session: Session, batch: CrawlBatch, source_name: str, items: list[dict]) -> int:
    now = datetime.now(timezone.utc)
    updated_count = 0
    for raw in items:
        metadata = raw.get("metadata") or {}
        if metadata.get("platform") != "GitHub" and raw.get("source_type") != "github_repository":
            continue
        metrics = metadata.get("metrics") if isinstance(metadata.get("metrics"), dict) else {}
        item_source_name = raw.get("source_name") or source_name
        snapshot_at = _parse_dt(metrics.get("metrics_snapshot_at") or metadata.get("metrics_snapshot_at")) or now
        metric_row = _find_existing_metrics_for_day(session, item_source_name, snapshot_at)
        if metric_row is None:
            metric_row = GitHubRepoMetrics(source_name=item_source_name, crawl_batch_id=batch.id)
            session.add(metric_row)
        metric_row.crawl_batch_id = batch.id
        metric_row.stars = _metric_value(metadata, metrics, "stars")
        metric_row.forks = _metric_value(metadata, metrics, "forks")
        metric_row.watchers = _metric_value(metadata, metrics, "watchers")
        metric_row.subscribers = _metric_value(metadata, metrics, "subscribers")
        metric_row.open_issues = _metric_value(metadata, metrics, "open_issues")
        metric_row.pushed_at = _parse_dt(metadata.get("pushed_at"))
        metric_row.updated_at = _parse_dt(metadata.get("updated_at"))
        metric_row.metrics_snapshot_at = snapshot_at
        metric_row.extra_metadata = metadata
        updated_count += 1
    return updated_count


def _metric_value(metadata: dict, metrics: dict, key: str) -> int | None:
    value = metrics.get(key) if key in metrics else metadata.get(key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _find_existing_metrics_for_day(session: Session, source_name: str, snapshot_at: datetime) -> GitHubRepoMetrics | None:
    session.flush()
    target_date = _local_date(snapshot_at, naive_timezone=SHANGHAI)
    rows = session.scalars(select(GitHubRepoMetrics).where(GitHubRepoMetrics.source_name == source_name)).all()
    for row in rows:
        if _local_date(row.metrics_snapshot_at, naive_timezone=SHANGHAI) == target_date:
            return row
    return None


def _local_date(value: datetime, *, naive_timezone=timezone.utc) -> date:
    if value.tzinfo is None:
        value = value.replace(tzinfo=naive_timezone)
    return value.astimezone(SHANGHAI).date()


def _parse_dt(value: object):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def build_top6(session: Session, report_date: date | None = None, batch_id: int | None = None) -> list[Item]:
    if batch_id:
        batch = session.get(CrawlBatch, batch_id)
        return rank_batch_items(session, batch) if batch else []
    if report_date:
        report = session.scalar(select(DailyReport).where(DailyReport.report_date == report_date))
        if report:
            return list(
                session.scalars(
                    select(Item)
                    .join(DailyReportItem, DailyReportItem.item_id == Item.id)
                    .where(DailyReportItem.report_id == report.id)
                    .order_by(DailyReportItem.sort_order.asc())
                ).all()
            )
    return []


def publish_daily_report(session: Session, batch: CrawlBatch) -> list[Item]:
    report_date = (batch.finished_at or datetime.now(timezone.utc)).astimezone(SHANGHAI).date()
    report = session.scalar(select(DailyReport).where(DailyReport.report_date == report_date))
    top6 = rank_batch_items(session, batch)
    if report:
        # A published daily report is an immutable historical record. Later
        # manual runs may score new items, but never rewrite its TOP6 snapshot.
        preserved_top6 = list(
            session.scalars(
                select(Item)
                .join(DailyReportItem, DailyReportItem.item_id == Item.id)
                .where(DailyReportItem.report_id == report.id)
                .order_by(DailyReportItem.sort_order.asc())
            ).all()
        )
        batch.top6_count = len(preserved_top6)
        return preserved_top6
    if not report:
        report = DailyReport(report_date=report_date, status="published", top6_count=len(top6), generated_at=datetime.now(timezone.utc))
        session.add(report)
        session.flush()

    for index, item in enumerate(top6, start=1):
        session.add(
            DailyReportItem(
                report_id=report.id,
                item_id=item.id,
                sort_order=index,
                ranking_score_snapshot=item.ranking_score,
                score_breakdown_snapshot=dict(item.score_breakdown or {}),
                selection_reason_snapshot=item.selection_reason,
            )
        )
    batch.top6_count = len(top6)
    return top6


def rerank_latest_daily_report(session: Session) -> tuple[CrawlBatch, list[Item]]:
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.astimezone(SHANGHAI).date(), datetime.min.time(), tzinfo=SHANGHAI).astimezone(timezone.utc)
    tomorrow_start = today_start + timedelta(days=1)
    items = list(
        session.scalars(
            select(Item)
            .where(
                Item.created_at >= today_start,
                Item.created_at < tomorrow_start,
                Item.related_official_item_id.is_(None),
            )
            .order_by(Item.created_at.asc(), Item.id.asc())
        ).all()
    )
    if not items:
        raise ValueError("No today items are available for reranking.")

    batch = session.scalar(
        select(CrawlBatch)
        .where(CrawlBatch.status != "running")
        .order_by(CrawlBatch.finished_at.desc().nullslast(), CrawlBatch.id.desc())
        .limit(1)
    )
    if not batch:
        batch = session.scalar(select(CrawlBatch).order_by(CrawlBatch.id.desc()).limit(1))
    if not batch:
        raise ValueError("No crawl batch is available for reranking.")

    top6 = rank_items(session, batch, items)
    report_date = now.astimezone(SHANGHAI).date()
    report = session.scalar(select(DailyReport).where(DailyReport.report_date == report_date))
    if not report:
        report = DailyReport(report_date=report_date, status="published", top6_count=0, generated_at=datetime.now(timezone.utc))
        session.add(report)
        session.flush()
    else:
        session.execute(delete(DailyReportItem).where(DailyReportItem.report_id == report.id))

    for index, item in enumerate(top6, start=1):
        session.add(
            DailyReportItem(
                report_id=report.id,
                item_id=item.id,
                sort_order=index,
                ranking_score_snapshot=item.ranking_score,
                score_breakdown_snapshot=dict(item.score_breakdown or {}),
                selection_reason_snapshot=item.selection_reason,
            )
        )
    report.status = "published"
    report.top6_count = len(top6)
    report.generated_at = datetime.now(timezone.utc)
    batch.top6_count = len(top6)
    session.add(
        SystemLog(
            log_date=datetime.now(timezone.utc),
            level="info",
            source_name=None,
            action="manual_rerank_completed",
            message="已手动重新排序今日 TOP6。",
            context={"batch_id": batch.id, "top6_count": len(top6), "ranking_version": RANKING_VERSION},
        )
    )
    return batch, top6


def run_daily_batch(session: Session, batch_id: int | None = None, source_names: list[str] | None = None) -> CrawlBatch:
    batch = session.get(CrawlBatch, batch_id) if batch_id is not None else ensure_today_batch(session)
    if batch is None:
        batch = ensure_today_batch(session)
    batch.status = "running"
    source_query = select(Source).where(Source.enabled.is_(True))
    if source_names:
        source_query = source_query.where(Source.source_name.in_(source_names))
    source_rows = list(session.scalars(source_query.order_by(Source.id.asc())).all())
    batch.total_sources = len(source_rows)
    batch.success_sources = 0
    batch.failed_sources = 0
    batch.raw_count = 0
    batch.saved_count = 0
    batch.comment_attached_count = 0
    batch.duplicate_dropped_count = 0
    session.flush()

    runs_by_source: dict[str, CrawlSourceRun] = {}
    for source in source_rows:
        run = CrawlSourceRun(batch_id=batch.id, source_id=source.id, attempt_count=0, status="running", started_at=datetime.now(timezone.utc))
        session.add(run)
        session.flush()
        runs_by_source[source.source_name] = run

    anchor_sources, community_sources, third_party_sources = _split_sources_for_aggregation(source_rows)
    _run_source_phase(session, batch, anchor_sources, runs_by_source, phase_name="anchor")
    session.flush()
    _run_source_phase(session, batch, community_sources, runs_by_source, phase_name="community")
    session.flush()
    _run_source_phase(session, batch, third_party_sources, runs_by_source, phase_name="third_party")

    batch.finished_at = datetime.now(timezone.utc)
    session.flush()
    try:
        publish_daily_report(session, batch)
        batch.status = "completed"
    except Exception as exc:
        logger.exception("ranking failed for batch_id=%s", batch.id)
        batch.status = "degraded"
        session.add(SystemLog(log_date=datetime.now(timezone.utc), level="error", source_name=None, action="ranking_failed", message="Ranking failed; publishing fallback order.", context={"batch_id": batch.id, "error": str(exc)[:300], "ranking_version": RANKING_VERSION}))
        _publish_fallback_report(session, batch)
    return batch


def _split_sources_for_aggregation(source_rows: list[Source]) -> tuple[list[Source], list[Source], list[Source]]:
    anchor_sources: list[Source] = []
    community_sources: list[Source] = []
    third_party_sources: list[Source] = []
    for source in source_rows:
        if source.source_type == "third_party_article" or source.source_origin == "third_party":
            third_party_sources.append(source)
        elif source.source_type == "github_trending" or source.source_origin == "community":
            community_sources.append(source)
        else:
            anchor_sources.append(source)
    return anchor_sources, community_sources, third_party_sources


def _run_source_phase(
    session: Session,
    batch: CrawlBatch,
    source_rows: list[Source],
    runs_by_source: dict[str, CrawlSourceRun],
    *,
    phase_name: str,
) -> None:
    if not source_rows:
        return
    for source in source_rows:
        run = runs_by_source[source.source_name]
        last_payload: dict | None = None
        for attempt in range(1, MAX_SOURCE_ATTEMPTS + 1):
            request_options = _crawler_request_options(source)
            logger.info(
                "system -> crawler request start batch_id=%s phase=%s source_name=%s attempt=%s options=%s",
                batch.id,
                phase_name,
                source.source_name,
                attempt,
                request_options,
            )
            session.add(
                SystemLog(
                    log_date=datetime.now(timezone.utc),
                    level="info",
                    source_name=source.source_name,
                    action="source_request_started",
                    message=f"已向爬虫端请求信源 {source.source_name} 的数据",
                    context={"batch_id": batch.id, "phase": phase_name, "attempt": attempt, "options": request_options},
                )
            )
            session.flush()
            payload = crawl_source(source.source_name, **request_options)
            last_payload = payload
            payload_status = payload.get("status")
            logger.info(
                "system <- crawler request finished batch_id=%s phase=%s source_name=%s attempt=%s status=%s returned_count=%s",
                batch.id,
                phase_name,
                source.source_name,
                attempt,
                payload_status,
                len(payload.get("items") or []),
            )
            if payload_status in {"success", "partial_success", "llm_failed"}:
                _process_source_payload(session, batch, source, run, payload, attempt_count=attempt)
                break
            run.attempt_count = attempt
            run.error_code = (payload.get("error") or {}).get("code")
            run.error_message = (payload.get("error") or {}).get("message")
            session.flush()
        else:
            _mark_source_failed(
                session,
                batch,
                source,
                run,
                (last_payload or {}).get("error") or {"code": (last_payload or {}).get("status") or "UNKNOWN_ERROR", "message": "crawl failed"},
                attempt_count=MAX_SOURCE_ATTEMPTS,
            )


def _crawler_request_options(source: Source) -> dict:
    config = source.crawler_config or {}
    options: dict = {}
    if source.crawl_strategy == "daily_incremental" and source.last_checkpoint_at:
        checkpoint = source.last_checkpoint_at
        if checkpoint.tzinfo is None:
            checkpoint = checkpoint.replace(tzinfo=timezone.utc)
        options["since"] = checkpoint.isoformat()
    max_pages = config.get("default_max_pages")
    max_items = config.get("default_max_items")
    if isinstance(max_pages, int) and max_pages > 0:
        options["max_pages"] = max_pages
    if isinstance(max_items, int) and max_items > 0:
        options["max_items"] = max_items
    return options


def _process_source_payload(session: Session, batch: CrawlBatch, source: Source, run: CrawlSourceRun, payload: dict, *, attempt_count: int = 1) -> None:
    run.attempt_count = attempt_count
    payload_status = payload.get("status")
    stats = payload.get("stats") or {}
    run.raw_count = _int_stat(stats, "raw_count")
    run.returned_count = _int_stat(stats, "returned_count") or len(payload.get("items") or [])
    batch.raw_count += run.raw_count
    if payload_status in {"success", "partial_success", "llm_failed"}:
        result = upsert_items(session, batch, source.source_name, payload)
        run.saved_count = result.saved_count
        run.attached_count = result.attached_count
        run.dropped_count = result.dropped_count
        batch.saved_count += result.saved_count
        batch.comment_attached_count += result.attached_count
        batch.duplicate_dropped_count += result.dropped_count
        if result.saved_count > 0 or result.attached_count > 0 or result.metrics_count > 0:
            session.add(
                SystemLog(
                    log_date=datetime.now(timezone.utc),
                    level="info",
                    source_name=source.source_name,
                    action="source_updated",
                    message=f"已更新信源{source.source_name}的数据",
                    context={
                        "inserted_count": result.saved_count,
                        "attached_count": result.attached_count,
                        "metrics_count": result.metrics_count,
                        "dropped_count": result.dropped_count,
                        "status": payload_status,
                        "batch_id": batch.id,
                    },
                )
            )
        if payload_status == "llm_failed":
            session.add(
                SystemLog(
                    log_date=datetime.now(timezone.utc),
                    level="warn",
                    source_name=source.source_name,
                    action="source_request_failed",
                    message=f"信源{source.source_name}数据请求失败：llm_failed",
                    context={"status": payload_status, "batch_id": batch.id},
                )
            )
        source.latest_status = payload_status
        source.latest_checked_at = datetime.now(timezone.utc)
        source.last_error = None
        source.last_success_at = datetime.now(timezone.utc)
        source.last_checkpoint_at = _latest_published_at(payload) or source.last_checkpoint_at
        run.status = payload_status or "success"
        run.error_code = None
        run.error_message = None
        run.finished_at = datetime.now(timezone.utc)
        batch.success_sources += 1
        return

    _mark_source_failed(
        session,
        batch,
        source,
        run,
        payload.get("error") or {"code": payload_status or "UNKNOWN_ERROR", "message": "crawl failed"},
    )


def _mark_source_failed(session: Session, batch: CrawlBatch, source: Source, run: CrawlSourceRun, error: dict, *, attempt_count: int | None = None) -> None:
    batch.failed_sources += 1
    source.latest_status = "failed"
    source.latest_checked_at = datetime.now(timezone.utc)
    source.last_error = error.get("message") or error.get("code")
    run.attempt_count = attempt_count or max(run.attempt_count, 1)
    run.status = "failed"
    run.error_code = error.get("code")
    run.error_message = error.get("message")
    run.finished_at = datetime.now(timezone.utc)
    failure_code = error.get("code") or "crawl_failed"
    session.add(
        SystemLog(
            log_date=datetime.now(timezone.utc),
            level="error",
            source_name=source.source_name,
            action="source_request_failed",
            message=f"信源{source.source_name}数据请求失败：{failure_code}",
            context={"error": error, "batch_id": batch.id},
        )
    )


def _int_stat(stats: dict, key: str) -> int:
    value = stats.get(key)
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _latest_published_at(payload: dict) -> datetime | None:
    values = [_parse_dt(item.get("published_at")) for item in payload.get("items") or []]
    values = [value for value in values if value is not None]
    return max(values) if values else None


def _publish_fallback_report(session: Session, batch: CrawlBatch) -> None:
    report_date = (batch.finished_at or datetime.now(timezone.utc)).astimezone(SHANGHAI).date()
    report = session.scalar(select(DailyReport).where(DailyReport.report_date == report_date))
    if not report:
        report = DailyReport(report_date=report_date, status="degraded", top6_count=0, generated_at=datetime.now(timezone.utc))
        session.add(report)
        session.flush()
    else:
        batch.top6_count = session.scalar(select(func.count()).select_from(DailyReportItem).where(DailyReportItem.report_id == report.id)) or 0
        return
    candidates = list(session.scalars(select(Item).where(Item.crawl_batch_id == batch.id, Item.related_official_item_id.is_(None))).all())
    candidates.sort(key=lambda item: (item.published_at is None, -(item.published_at.timestamp() if item.published_at else 0), -item.created_at.timestamp(), item.id))
    for index, item in enumerate(candidates[:6], start=1):
        reason = "排序计算异常，按发布时间降级排序。"
        item.selection_reason = reason
        session.add(DailyReportItem(report_id=report.id, item_id=item.id, sort_order=index, ranking_score_snapshot=item.ranking_score, score_breakdown_snapshot=dict(item.score_breakdown or {}), selection_reason_snapshot=reason))
    report.top6_count = min(6, len(candidates))
    report.generated_at = datetime.now(timezone.utc)
    batch.top6_count = report.top6_count
