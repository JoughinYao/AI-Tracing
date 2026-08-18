from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import CrawlBatch, DailyReport, DailyReportItem, Item
from app.services.batch_runner import publish_daily_report, rerank_latest_daily_report
from app.services.ranking import rank_batch_items


def make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def make_batch(session):
    now = datetime(2026, 8, 13, 10, 30, tzinfo=timezone.utc)
    batch = CrawlBatch(batch_date=now, triggered_at=now, finished_at=now, status="running")
    session.add(batch)
    session.flush()
    return batch


def make_item(session, batch, external_id, source_name, event_type="community_activity", category="GitHub 上升项目", metadata=None):
    item = Item(
        external_id=external_id,
        source_name=source_name,
        source_type="github_trending" if source_name == "github_trending" else "github_repository",
        source_url="https://github.com",
        original_url="https://github.com/example/project",
        title=external_id,
        category=category,
        event_type=event_type,
        published_at=batch.finished_at - timedelta(hours=2),
        extra_metadata=metadata or {"platform": "GitHub"},
        processing_status="enriched",
        crawl_batch_id=batch.id,
        created_at=batch.finished_at,
    )
    session.add(item)
    session.flush()
    return item


def test_trending_score_uses_rank_and_saves_breakdown():
    session = make_session()
    batch = make_batch(session)
    item = make_item(session, batch, "trending-1", "github_trending", metadata={"platform": "GitHub", "trending_rank": 2, "stars": 500})

    selected = rank_batch_items(session, batch)

    assert selected == [item]
    assert item.event_impact_score == 10
    assert item.category_relevance_score == 15
    assert item.freshness_score == 15
    assert item.source_authority_score == 8
    assert item.community_heat_score == 10
    assert item.ranking_score == 58
    assert item.score_breakdown["rules"]["community_heat_rule"] == "trending_rank_1_3"


def test_top6_fills_from_whole_day_pool_after_category_slots():
    session = make_session()
    batch = make_batch(session)
    for index in range(4):
        make_item(session, batch, f"codex-{index}", "github_codex", event_type="security_issue", category="核心 Agent runtime 更新")
    for index in range(3):
        make_item(session, batch, f"trend-{index}", "github_trending", metadata={"platform": "GitHub", "trending_rank": index + 1})
    make_item(session, batch, "pi-1", "github_pi_agent", event_type="release", category="核心 Agent runtime 更新")

    selected = rank_batch_items(session, batch)

    assert len(selected) == 6
    assert any(item.category == "runtime" for item in selected)
    assert any(item.category == "trending" for item in selected)
    assert sum(item.source_name == "github_codex" for item in selected) > 2


def test_top6_missing_categories_are_backfilled_from_ranked_items():
    session = make_session()
    batch = make_batch(session)
    for index, source_name in enumerate(["github_codex", "github_pi_agent", "github_hermes", "github_opencode"]):
        make_item(session, batch, f"runtime-{index}", source_name, event_type="release", category="runtime")
    for index in range(2):
        make_item(session, batch, f"trend-{index}", "github_trending", event_type="release", category="trending", metadata={"platform": "GitHub", "trending_rank": index + 1})
    llm_item = make_item(session, batch, "deepseek-v4-pro", "deepseek_news", event_type="product_update", category="llm", metadata={})

    selected = rank_batch_items(session, batch)

    assert len(selected) == 6
    assert llm_item in selected
    assert any(item.category == "runtime" for item in selected)
    assert any(item.category == "trending" for item in selected)
    assert sum(item.category in {"runtime", "trending", "llm"} for item in selected) == 6


def test_top6_guarantees_best_item_for_each_priority_category():
    session = make_session()
    batch = make_batch(session)
    runtime_winner = make_item(session, batch, "runtime-best", "github_codex", event_type="security_issue", category="runtime")
    runtime_runner_up = make_item(session, batch, "runtime-other", "github_codex", event_type="other", category="runtime")
    trending_winner = make_item(session, batch, "trending-best", "github_trending", event_type="release", category="trending", metadata={"platform": "GitHub", "trending_rank": 1})
    make_item(session, batch, "trending-other", "github_trending", event_type="release", category="trending", metadata={"platform": "GitHub", "trending_rank": 18})
    llm_winner = make_item(session, batch, "llm-best", "deepseek_news", event_type="major_feature", category="llm")
    make_item(session, batch, "llm-other", "deepseek_news", event_type="other", category="llm")
    agent_winner = make_item(session, batch, "agent-best", "github_pi_agent", event_type="release", category="agent")
    finance_winner = make_item(session, batch, "finance-best", "qbitai", event_type="product_update", category="finance")

    selected = rank_batch_items(session, batch)

    assert len(selected) == 6
    assert runtime_winner in selected
    assert runtime_runner_up not in selected
    assert trending_winner in selected
    assert llm_winner in selected
    assert agent_winner in selected
    assert finance_winner in selected


def test_llm_selection_can_reject_high_heat_but_low_relevance_item(monkeypatch):
    session = make_session()
    batch = make_batch(session)
    generic_tool = make_item(
        session,
        batch,
        "money-printer-turbo",
        "github_trending",
        event_type="community_activity",
        category="trending",
        metadata={"platform": "GitHub", "trending_rank": 1, "stars": 106717, "stars_today": 1189},
    )
    finance_item = make_item(session, batch, "finance-agent-api", "qbitai", event_type="major_feature", category="finance")
    runtime_item = make_item(session, batch, "codex-runtime-security", "github_codex", event_type="security_issue", category="runtime")

    monkeypatch.setattr(
        "app.services.ranking.get_settings",
        lambda: SimpleNamespace(
            ranking_llm_enabled=True,
            anthropic_api_key="test-key",
            openai_api_key=None,
            anthropic_model="claude-test",
            anthropic_api_url="https://new-api.finstep.cn",
            ranking_llm_timeout_ms=1000,
        ),
    )
    monkeypatch.setattr(
        "app.services.ranking._call_ranking_llm",
        lambda _settings, _pool: {
            "category_picks": {"runtime": runtime_item.id, "trending": None, "llm": None, "agent": None, "finance": finance_item.id},
            "fill_ids": [],
            "rejected_ids": [generic_tool.id],
            "reasons": {
                str(runtime_item.id): "Runtime security is directly relevant to backend engineering.",
                str(finance_item.id): "Financial AI API change is relevant to the target audience.",
            },
        },
    )

    selected = rank_batch_items(session, batch)

    assert generic_tool not in selected
    assert selected == [runtime_item, finance_item]
    assert runtime_item.selection_reason.startswith("LLM selected")


def test_ranking_flushes_new_items_before_querying_candidates():
    session = make_session()
    batch = make_batch(session)
    item = Item(
        external_id="unflushed-item",
        source_name="github_codex",
        source_type="github_repository",
        source_url="https://github.com/openai/codex",
        original_url="https://github.com/openai/codex",
        title="Unflushed item",
        category="核心 Agent runtime 更新",
        event_type="release",
        published_at=batch.finished_at,
        extra_metadata={"platform": "GitHub"},
        processing_status="enriched",
        crawl_batch_id=batch.id,
        created_at=batch.finished_at,
    )
    session.add(item)

    selected = rank_batch_items(session, batch)

    assert selected == [item]
    assert item.ranking_score == 77


def test_report_stores_score_snapshots():
    session = make_session()
    batch = make_batch(session)
    item = make_item(session, batch, "trending-1", "github_trending", metadata={"platform": "GitHub", "trending_rank": 6})

    publish_daily_report(session, batch)
    session.commit()

    report = session.scalar(select(DailyReport))
    report_item = session.scalar(select(DailyReportItem))
    assert report.top6_count == 1
    assert report_item.item_id == item.id
    assert report_item.ranking_score_snapshot == item.ranking_score
    assert report_item.score_breakdown_snapshot["final_score"] == item.ranking_score
    assert report_item.selection_reason_snapshot == item.selection_reason


def test_manual_rerank_rewrites_latest_daily_report():
    session = make_session()
    now = datetime.now(timezone.utc)
    batch = CrawlBatch(batch_date=now, triggered_at=now, finished_at=now, status="completed")
    session.add(batch)
    session.flush()
    first_item = make_item(session, batch, "first-item", "github_trending", metadata={"platform": "GitHub", "trending_rank": 6})
    publish_daily_report(session, batch)

    second_item = make_item(session, batch, "second-item", "github_codex", event_type="security_issue", category="runtime")
    _, top6 = rerank_latest_daily_report(session)

    report = session.scalar(select(DailyReport))
    report_items = list(session.scalars(select(DailyReportItem).where(DailyReportItem.report_id == report.id).order_by(DailyReportItem.sort_order.asc())).all())

    assert second_item in top6
    assert [row.item_id for row in report_items] == [item.id for item in top6]
    assert report.top6_count == len(top6)
    assert first_item.id in [row.item_id for row in report_items]


def test_published_report_is_not_rewritten_by_a_later_batch():
    session = make_session()
    first_batch = make_batch(session)
    first_item = make_item(session, first_batch, "first-report-item", "github_trending", metadata={"platform": "GitHub", "trending_rank": 8})
    publish_daily_report(session, first_batch)

    later_batch = CrawlBatch(
        batch_date=first_batch.finished_at + timedelta(hours=1),
        triggered_at=first_batch.finished_at + timedelta(hours=1),
        finished_at=first_batch.finished_at + timedelta(hours=1),
        status="running",
    )
    session.add(later_batch)
    session.flush()
    later_item = make_item(session, later_batch, "later-item", "github_codex", event_type="security_issue", category="核心 Agent runtime 更新")

    selected = publish_daily_report(session, later_batch)
    report = session.scalar(select(DailyReport))
    report_items = list(session.scalars(select(DailyReportItem).where(DailyReportItem.report_id == report.id)).all())

    assert selected == [first_item]
    assert [report_item.item_id for report_item in report_items] == [first_item.id]
    assert later_item.ranking_score is not None
