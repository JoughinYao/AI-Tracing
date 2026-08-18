from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import CrawlBatch, CrawlSourceRun, Source, SystemLog
from app.services.batch_runner import run_daily_batch


def make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def test_run_daily_batch_requests_only_selected_sources(monkeypatch):
    session = make_session()
    now = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
    batch = CrawlBatch(batch_date=now, triggered_at=now, status="running")
    codex = Source(
        source_name="github_codex",
        display_name="Codex",
        source_type="github_repository",
        default_category="runtime",
        enabled=True,
    )
    qbitai = Source(
        source_name="qbitai",
        display_name="量子位",
        source_type="third_party_article",
        source_origin="third_party",
        default_category="llm",
        enabled=True,
    )
    disabled = Source(
        source_name="disabled_source",
        display_name="Disabled",
        source_type="third_party_article",
        default_category="llm",
        enabled=False,
    )
    session.add_all([batch, codex, qbitai, disabled])
    session.flush()

    requested_source_names = []

    def fake_crawl_source(source_name, **_kwargs):
        requested_source_names.append(source_name)
        return {
            "status": "success",
            "source_name": source_name,
            "items": [],
            "stats": {"raw_count": 0, "returned_count": 0},
        }

    monkeypatch.setattr("app.services.batch_runner.crawl_source", fake_crawl_source)

    run_daily_batch(session, batch_id=batch.id, source_names=["qbitai"])

    runs = list(session.scalars(select(CrawlSourceRun)).all())
    assert requested_source_names == ["qbitai"]
    assert batch.total_sources == 1
    assert len(runs) == 1
    assert runs[0].source_id == qbitai.id


def test_run_daily_batch_collects_anchor_sources_before_third_party(monkeypatch):
    session = make_session()
    now = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
    batch = CrawlBatch(batch_date=now, triggered_at=now, status="running")
    session.add_all(
        [
            batch,
            Source(
                source_name="github_codex",
                display_name="Codex",
                source_type="github_repository",
                source_origin="official",
                default_category="runtime",
                enabled=True,
            ),
            Source(
                source_name="github_trending",
                display_name="GitHub Trending",
                source_type="github_trending",
                source_origin="community",
                default_category="trending",
                enabled=True,
            ),
            Source(
                source_name="qbitai",
                display_name="量子位",
                source_type="third_party_article",
                source_origin="third_party",
                default_category="llm",
                enabled=True,
            ),
        ]
    )
    session.flush()

    requested_sources = []

    def fake_crawl_source(source_name, **_kwargs):
        requested_sources.append(source_name)
        return {
            "status": "success",
            "source_name": source_name,
            "items": [],
            "stats": {"raw_count": 0, "returned_count": 0},
        }

    monkeypatch.setattr("app.services.batch_runner.crawl_source", fake_crawl_source)

    run_daily_batch(session, batch_id=batch.id)

    assert requested_sources == ["github_codex", "github_trending", "qbitai"]


def test_run_daily_batch_retries_failed_source_three_times(monkeypatch):
    session = make_session()
    now = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
    batch = CrawlBatch(batch_date=now, triggered_at=now, status="running")
    source = Source(
        source_name="aihot",
        display_name="AIHOT",
        source_type="third_party_article",
        source_origin="third_party",
        default_category="llm",
        enabled=True,
    )
    session.add_all([batch, source])
    session.flush()

    requested_source_names = []

    def fake_crawl_source(source_name, **_kwargs):
        requested_source_names.append(source_name)
        return {
            "status": "crawl_failed",
            "source_name": source_name,
            "items": [],
            "stats": {"raw_count": 0, "returned_count": 0},
            "error": {"code": "FETCH_ERROR", "message": "fetch failed"},
        }

    monkeypatch.setattr("app.services.batch_runner.crawl_source", fake_crawl_source)

    run_daily_batch(session, batch_id=batch.id)

    run = session.scalar(select(CrawlSourceRun))
    assert requested_source_names == ["aihot", "aihot", "aihot"]
    assert batch.failed_sources == 1
    assert run is not None
    assert run.attempt_count == 3
    assert run.error_code == "FETCH_ERROR"


def test_metrics_only_update_writes_system_log(monkeypatch):
    session = make_session()
    now = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
    batch = CrawlBatch(batch_date=now, triggered_at=now, status="running")
    source = Source(
        source_name="github_codex",
        display_name="Codex",
        source_type="github_repository",
        source_origin="repository",
        default_category="runtime",
        enabled=True,
    )
    session.add_all([batch, source])
    session.flush()

    def fake_crawl_source(source_name, **_kwargs):
        return {
            "status": "success",
            "source_name": source_name,
            "items": [
                {
                    "external_id": "github_codex:repo_metrics:2026-08-17",
                    "source_name": "github_codex",
                    "source_type": "github_repository",
                    "event_type": "repo_metric_change",
                    "company": "openai",
                    "domain": "agent",
                    "relation": None,
                    "metadata": {
                        "metrics_only": True,
                        "stars": 100,
                        "forks": 20,
                        "watchers": 100,
                        "open_issues": 7,
                        "metrics": {"metrics_snapshot_at": "2026-08-17T07:04:02Z"},
                    },
                    "llm_status": "skipped",
                    "processing_status": "enriched",
                }
            ],
            "stats": {"raw_count": 1, "returned_count": 1},
        }

    monkeypatch.setattr("app.services.batch_runner.crawl_source", fake_crawl_source)

    run_daily_batch(session, batch_id=batch.id, source_names=["github_codex"])

    log = session.scalar(select(SystemLog).where(SystemLog.action == "source_updated"))
    assert log is not None
    assert log.source_name == "github_codex"
    assert log.context["inserted_count"] == 0
    assert log.context["metrics_count"] == 1
