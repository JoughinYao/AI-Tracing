from __future__ import annotations

from datetime import datetime, date
from typing import Any
from pydantic import BaseModel, Field, ConfigDict


class SourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    source_name: str
    display_name: str
    default_category: str
    enabled: bool
    source_type: str
    source_origin: str = "official"
    crawl_strategy: str = "latest_only"
    source_url: str | None = None
    latest_status: str | None = None
    latest_checked_at: datetime | None = None
    last_success_at: datetime | None = None
    last_checkpoint_at: datetime | None = None
    last_error: str | None = None
    crawler_config: dict[str, Any] = Field(default_factory=dict)
    synced_to_crawler_at: datetime | None = None


class GitHubSourceCreate(BaseModel):
    source_name: str = Field(pattern=r"^[a-z0-9_]{2,64}$")
    repo_url: str
    is_official: bool = False


class ThirdPartySourceCreate(BaseModel):
    source_name: str = Field(pattern=r"^[a-z0-9_]{2,64}$")
    source_url: str
    platform: str
    list_container_xpath: str
    article_url_regex: str
    default_max_candidates: int = 20
    default_max_items: int = 10
    default_max_pages: int = 1
    render_list_page: bool = False
    render_article_page: bool = False
    source_tags: list[str] = Field(default_factory=list)
    blocked_url_keywords: list[str] = Field(default_factory=list)


class ContentCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    official_item_id: int
    third_party_item_id: int | None = None
    source_name: str
    original_url: str | None = None
    title: str
    summary: str | None = None
    sentiment: str = "unknown"
    relation_type: str = "commentary"
    published_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_metadata")
    created_at: datetime


class RelatedThirdPartyRead(BaseModel):
    relation_type: str
    relation_confidence: str | None = None
    relation_reason: str | None = None
    title: str
    summary: str | None = None
    author: str | None = None
    published_at: datetime | None = None
    source_name: str
    source_display_name: str
    original_url: str | None = None
    sentiment: str = "unknown"


class RelationUpdateRead(BaseModel):
    official_item_id: int
    official_internal_id: str
    official_title: str
    last_relation_added_at: datetime
    relation_update_count_today: int
    latest_relation_title: str | None = None
    latest_relation_source_name: str | None = None
    latest_relation_source_display_name: str | None = None


class OfficialCandidateQuery(BaseModel):
    company: str
    domain: str
    since_days: int = Field(default=7, ge=1, le=30)


class OfficialCandidatesRequest(BaseModel):
    queries: list[OfficialCandidateQuery] = Field(default_factory=list)


class OfficialCandidateRead(BaseModel):
    id: str
    company: str | None = None
    domain: str
    title: str
    published_at: datetime | None = None
    source_name: str
    source_display_name: str | None = None


class OfficialCandidatesResponse(BaseModel):
    items: list[OfficialCandidateRead]


class OfficialItemsDetailRequest(BaseModel):
    ids: list[str]


class OfficialItemDetailRead(BaseModel):
    id: str
    company: str | None = None
    domain: str
    title: str
    summary: str | None = None
    content_excerpt: str | None = None
    published_at: datetime | None = None
    source_name: str
    source_display_name: str
    original_url: str | None = None
    related_third_party: list[RelatedThirdPartyRead] = Field(default_factory=list)


class OfficialItemsDetailResponse(BaseModel):
    items: list[OfficialItemDetailRead]


class ItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    external_id: str
    source_name: str
    source_origin: str = "official"
    source_type: str
    source_url: str | None = None
    original_url: str | None = None
    title: str
    summary: str | None = None
    category: str | None = None
    company: str | None = None
    domain: str | None = None
    event_type: str | None = None
    entities: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    author: str | None = None
    language: str | None = None
    content_hash: str | None = None
    content_excerpt: str | None = None
    canonical_key: str | None = None
    product_key: str | None = None
    model_key: str | None = None
    version_key: str | None = None
    related_official_item_id: int | None = None
    relation_type: str | None = None
    relation: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="extra_metadata")
    llm_status: str
    processing_status: str
    key_points: list[str] = Field(default_factory=list)
    technical_details: list[dict[str, Any]] = Field(default_factory=list)
    value_interpretation: dict[str, Any] | None = None
    impact_scope: list[str] = Field(default_factory=list)
    risk_or_limitations: list[str] = Field(default_factory=list)
    recommended_action: str | None = None
    evidence_excerpts: list[dict[str, Any]] = Field(default_factory=list)
    information_gaps: list[str] = Field(default_factory=list)
    content_depth: str | None = None
    primary_image: dict[str, Any] | None = None
    image_candidates: list[dict[str, Any]] = Field(default_factory=list)
    crawl_batch_id: int | None = None
    created_at: datetime
    ranking_score: float | None = None
    ranking_version: str | None = None
    event_impact_score: int | None = None
    category_relevance_score: int | None = None
    freshness_score: int | None = None
    source_authority_score: int | None = None
    community_heat_score: int | None = None
    community_heat_applicable: bool = False
    score_breakdown: dict[str, Any] = Field(default_factory=dict)
    selection_reason: str | None = None
    comments: list[ContentCommentRead] = Field(default_factory=list, validation_alias="community_comments")
    related_third_party: list[RelatedThirdPartyRead] = Field(default_factory=list)


class ItemPage(BaseModel):
    items: list[ItemRead]
    page: int
    page_size: int
    total: int
    total_pages: int


class BatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    batch_date: datetime
    status: str
    triggered_at: datetime
    finished_at: datetime | None = None
    total_sources: int
    success_sources: int
    failed_sources: int
    top6_count: int
    raw_count: int = 0
    saved_count: int = 0
    comment_attached_count: int = 0
    duplicate_dropped_count: int = 0
    notes: str | None = None


class SystemLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    log_date: datetime
    level: str
    source_name: str | None = None
    action: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class HomeTodayResponse(BaseModel):
    report_date: date
    has_updates: bool
    is_empty: bool
    status_text: str
    batch: BatchRead | None = None
    relation_updates: list[RelationUpdateRead] = Field(default_factory=list)
    top6: list[ItemRead]
    sources: list[SourceRead]


class MetricsPoint(BaseModel):
    snapshot_at: datetime
    stars: int | None = None
    forks: int | None = None
    watchers: int | None = None
    subscribers: int | None = None
    open_issues: int | None = None
    pushed_at: datetime | None = None
    updated_at: datetime | None = None


class MetricsResponse(BaseModel):
    source_name: str
    series: list[MetricsPoint]


class AgentMetricsSeries(BaseModel):
    source_name: str
    display_name: str
    series: list[MetricsPoint]


class CoreAgentMetricsResponse(BaseModel):
    range: str
    agents: list[AgentMetricsSeries]


class CrawlRunResponse(BaseModel):
    batch_id: int
    status: str
    message: str
    top6_count: int


class CrawlRequest(BaseModel):
    source_name: str | None = "all"
    source_names: list[str] | None = None
