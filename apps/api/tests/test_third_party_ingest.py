from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import ContentComment, ContentItemRelation, CrawlBatch, GitHubRepoMetrics, Item, Source
from app.services.batch_runner import upsert_items


def make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def make_batch(session):
    now = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
    batch = CrawlBatch(batch_date=now, triggered_at=now, status="running")
    session.add(batch)
    session.flush()
    return batch


def test_third_party_duplicate_is_dropped():
    session = make_session()
    batch = make_batch(session)
    session.add(
        Source(
            source_name="machine_heart",
            display_name="机器之心",
            source_type="third_party_article",
            source_origin="third_party",
            default_category="llm",
            crawl_strategy="daily_incremental",
        )
    )
    session.flush()

    result = upsert_items(
        session,
        batch,
        "machine_heart",
        {
            "items": [
                {
                    "external_id": "mh-dup-1",
                    "source_name": "machine_heart",
                    "source_type": "third_party_article",
                    "source_origin": "third_party",
                    "original_url": "https://example.com/dup",
                    "title": "转载官方公告",
                    "category": "llm",
                    "company": "deepseek",
                    "domain": "llm",
                    "relation": {"target_id": "official_1", "relation_type": "duplicate", "confidence": "high"},
                    "metadata": {},
                }
            ]
        },
    )

    assert result.saved_count == 0
    assert result.dropped_count == 1
    assert session.scalar(select(Item).where(Item.external_id == "mh-dup-1")) is None


def test_third_party_commentary_attaches_to_official_item():
    session = make_session()
    batch = make_batch(session)
    official = Item(
        external_id="deepseek-official-v4",
        source_name="deepseek_news",
        source_origin="official",
        source_type="official_changelog",
        source_url="https://api-docs.deepseek.com",
        original_url="https://api-docs.deepseek.com/news/v4",
        title="DeepSeek V4 Pro 发布",
        category="llm",
        company="deepseek",
        domain="llm",
        event_type="product_update",
        processing_status="enriched",
        created_at=batch.triggered_at,
    )
    session.add_all(
        [
            official,
            Source(
                source_name="machine_heart",
                display_name="机器之心",
                source_type="third_party_article",
                source_origin="third_party",
                default_category="llm",
                crawl_strategy="daily_incremental",
            ),
        ]
    )
    session.flush()

    result = upsert_items(
        session,
        batch,
        "machine_heart",
        {
            "items": [
                {
                    "external_id": "mh-comment-1",
                    "source_name": "machine_heart",
                    "source_type": "third_party_article",
                    "source_origin": "third_party",
                    "original_url": "https://example.com/comment",
                    "title": "DeepSeek V4 Pro 使用体验",
                    "summary": "文章认为模型在代码任务上表现更稳。",
                    "category": "llm",
                    "company": "deepseek",
                    "domain": "llm",
                    "relation": {
                        "target_id": f"official_{official.id}",
                        "relation_type": "commentary",
                        "confidence": "high",
                        "reason": "same company and model release",
                    },
                    "sentiment": "positive",
                    "metadata": {},
                }
            ]
        },
    )

    comment = session.scalar(select(ContentComment).where(ContentComment.official_item_id == official.id))
    third_party_item = session.scalar(select(Item).where(Item.external_id == "mh-comment-1"))
    relation = session.scalar(select(ContentItemRelation).where(ContentItemRelation.official_item_id == official.id))
    assert result.saved_count == 1
    assert result.attached_count == 1
    assert third_party_item is not None
    assert third_party_item.related_official_item_id == official.id
    assert relation is not None
    assert relation.third_party_item_id == third_party_item.id
    assert relation.relation_type == "commentary"
    assert relation.relation_confidence == "high"
    assert relation.relation_reason == "same company and model release"
    assert relation.matched_by == "relation_target_id"
    assert comment is not None
    assert comment.source_name == "machine_heart"
    assert comment.relation_type == "commentary"
    assert comment.sentiment == "positive"
    assert third_party_item.company == "deepseek"
    assert third_party_item.domain == "llm"


def test_metrics_only_github_item_updates_metrics_without_news_item():
    session = make_session()
    batch = make_batch(session)
    session.add(
        Source(
            source_name="github_codex",
            display_name="Codex",
            source_type="github_repository",
            source_origin="repository",
            default_category="runtime",
            crawl_strategy="latest_only",
        )
    )
    session.flush()

    payload = {
        "items": [
            {
                "external_id": "github_codex:repo_metrics:2026-08-17",
                "source_name": "github_codex",
                "source_type": "github_repository",
                "event_type": "repo_metric_change",
                "title": "Codex 仓库指标快照",
                "category": "runtime",
                "metadata": {
                    "platform": "GitHub",
                    "metrics_only": True,
                    "metrics_reason": "no_recent_release",
                    "stars": 100,
                    "forks": 20,
                    "watchers": 100,
                    "open_issues": 7,
                    "metrics": {
                        "stars": 101,
                        "forks": 21,
                        "watchers": 101,
                        "open_issues": 8,
                        "metrics_snapshot_at": "2026-08-17T18:30:00+08:00",
                    },
                },
                "llm_status": "skipped",
                "processing_status": "enriched",
            }
        ]
    }

    result = upsert_items(session, batch, "github_codex", payload)

    assert result.saved_count == 0
    assert session.scalar(select(Item).where(Item.external_id == "github_codex:repo_metrics:2026-08-17")) is None
    metric = session.scalar(select(GitHubRepoMetrics).where(GitHubRepoMetrics.source_name == "github_codex"))
    assert metric is not None
    assert metric.stars == 101
    assert metric.forks == 21
    assert metric.watchers == 101
    assert metric.open_issues == 8

    payload["items"][0]["metadata"]["metrics"]["stars"] = 102
    upsert_items(session, batch, "github_codex", payload)
    metrics = list(session.scalars(select(GitHubRepoMetrics).where(GitHubRepoMetrics.source_name == "github_codex")).all())

    assert len(metrics) == 1
    assert metrics[0].stars == 102
