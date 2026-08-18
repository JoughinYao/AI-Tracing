from __future__ import annotations

from datetime import datetime
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    default_category: Mapped[str] = mapped_column(String(80), default="其他")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    source_type: Mapped[str] = mapped_column(String(40), default="github_repository")
    source_origin: Mapped[str] = mapped_column(String(40), default="official")
    crawl_strategy: Mapped[str] = mapped_column(String(40), default="latest_only")
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latest_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    latest_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checkpoint_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    crawler_config: Mapped[dict] = mapped_column(JSON, default=dict)
    synced_to_crawler_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    runs: Mapped[list["CrawlSourceRun"]] = relationship(back_populates="source")


class CrawlBatch(Base):
    __tablename__ = "crawl_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(40), default="running")
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    total_sources: Mapped[int] = mapped_column(Integer, default=0)
    success_sources: Mapped[int] = mapped_column(Integer, default=0)
    failed_sources: Mapped[int] = mapped_column(Integer, default=0)
    top6_count: Mapped[int] = mapped_column(Integer, default=0)
    raw_count: Mapped[int] = mapped_column(Integer, default=0)
    saved_count: Mapped[int] = mapped_column(Integer, default=0)
    comment_attached_count: Mapped[int] = mapped_column(Integer, default=0)
    duplicate_dropped_count: Mapped[int] = mapped_column(Integer, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    source_runs: Mapped[list["CrawlSourceRun"]] = relationship(back_populates="batch")


class CrawlSourceRun(Base):
    __tablename__ = "crawl_source_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("crawl_batches.id"))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_count: Mapped[int] = mapped_column(Integer, default=0)
    returned_count: Mapped[int] = mapped_column(Integer, default=0)
    saved_count: Mapped[int] = mapped_column(Integer, default=0)
    attached_count: Mapped[int] = mapped_column(Integer, default=0)
    dropped_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    batch: Mapped["CrawlBatch"] = relationship(back_populates="source_runs")
    source: Mapped["Source"] = relationship(back_populates="runs")


class Item(Base):
    __tablename__ = "items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    source_name: Mapped[str] = mapped_column(String(80), index=True)
    source_origin: Mapped[str] = mapped_column(String(40), default="official", index=True)
    source_type: Mapped[str] = mapped_column(String(40))
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    original_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    company: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    domain: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    event_type: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    entities: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    author: Mapped[str | None] = mapped_column(String(120), nullable=True)
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    content_excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_key: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    product_key: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    model_key: Mapped[str | None] = mapped_column(String(160), nullable=True, index=True)
    version_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    related_official_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True, index=True)
    relation_type: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    relation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    llm_status: Mapped[str] = mapped_column(String(40), default="skipped")
    processing_status: Mapped[str] = mapped_column(String(40), default="normalized")
    key_points: Mapped[list[str]] = mapped_column(JSON, default=list)
    technical_details: Mapped[list[dict]] = mapped_column(JSON, default=list)
    value_interpretation: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    impact_scope: Mapped[list[str]] = mapped_column(JSON, default=list)
    risk_or_limitations: Mapped[list[str]] = mapped_column(JSON, default=list)
    recommended_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_excerpts: Mapped[list[dict]] = mapped_column(JSON, default=list)
    information_gaps: Mapped[list[str]] = mapped_column(JSON, default=list)
    content_depth: Mapped[str | None] = mapped_column(String(40), nullable=True)
    primary_image: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    image_candidates: Mapped[list[dict]] = mapped_column(JSON, default=list)
    crawl_batch_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_batches.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    ranking_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    ranking_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    event_impact_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    category_relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    freshness_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_authority_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    community_heat_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    community_heat_applicable: Mapped[bool] = mapped_column(Boolean, default=False)
    score_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    selection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)

    community_comments: Mapped[list["ContentComment"]] = relationship(
        foreign_keys="ContentComment.official_item_id",
        back_populates="official_item",
    )
    related_relations: Mapped[list["ContentItemRelation"]] = relationship(
        foreign_keys="ContentItemRelation.official_item_id",
        back_populates="official_item",
    )


class ContentComment(Base):
    __tablename__ = "content_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    official_item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    third_party_item_id: Mapped[int | None] = mapped_column(ForeignKey("items.id"), nullable=True, index=True)
    source_name: Mapped[str] = mapped_column(String(80), index=True)
    original_url: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    sentiment: Mapped[str] = mapped_column(String(40), default="unknown")
    relation_type: Mapped[str] = mapped_column(String(40), default="commentary")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    official_item: Mapped["Item"] = relationship(foreign_keys=[official_item_id], back_populates="community_comments")


class ContentItemRelation(Base):
    __tablename__ = "content_item_relations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    official_item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    third_party_item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    relation_type: Mapped[str] = mapped_column(String(40), default="commentary", index=True)
    relation_confidence: Mapped[str | None] = mapped_column(String(40), nullable=True)
    relation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    canonical_key: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True)
    matched_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    official_item: Mapped["Item"] = relationship(foreign_keys=[official_item_id], back_populates="related_relations")
    third_party_item: Mapped["Item"] = relationship(foreign_keys=[third_party_item_id])


class GitHubRepoMetrics(Base):
    __tablename__ = "github_repo_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(80), index=True)
    crawl_batch_id: Mapped[int | None] = mapped_column(ForeignKey("crawl_batches.id"), nullable=True)
    stars: Mapped[int | None] = mapped_column(Integer, nullable=True)
    forks: Mapped[int | None] = mapped_column(Integer, nullable=True)
    watchers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subscribers: Mapped[int | None] = mapped_column(Integer, nullable=True)
    open_issues: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pushed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metrics_snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSON, default=dict)


class DailyReport(Base):
    __tablename__ = "daily_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_date: Mapped[Date] = mapped_column(Date, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(40), default="published")
    top6_count: Mapped[int] = mapped_column(Integer, default=0)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class DailyReportItem(Base):
    __tablename__ = "daily_report_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("daily_reports.id"))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    ranking_score_snapshot: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_breakdown_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    selection_reason_snapshot: Mapped[str | None] = mapped_column(String(255), nullable=True)


class SystemLog(Base):
    __tablename__ = "system_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    log_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    level: Mapped[str] = mapped_column(String(20), default="info")
    source_name: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(80))
    message: Mapped[str] = mapped_column(Text)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
