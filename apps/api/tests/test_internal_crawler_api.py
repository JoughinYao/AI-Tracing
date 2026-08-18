from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Item, Source
from app.routers.internal_crawler import official_candidates, official_items_detail
from app.schemas import OfficialCandidateQuery, OfficialCandidatesRequest, OfficialItemsDetailRequest


def make_session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, future=True)()


def test_official_candidates_returns_company_domain_anchor_items():
    session = make_session()
    now = datetime.now(timezone.utc)
    source = Source(
        source_name="deepseek_news",
        display_name="DeepSeek News",
        source_type="official_changelog",
        source_origin="official",
        default_category="llm",
        enabled=True,
    )
    item = Item(
        external_id="deepseek-v4-pro",
        source_name="deepseek_news",
        source_origin="official",
        source_type="official_changelog",
        original_url="https://api-docs.deepseek.com/news/v4",
        title="DeepSeek V4 Pro release",
        summary="Official release notes.",
        category="llm",
        company="deepseek",
        domain="llm",
        event_type="model_update",
        published_at=now - timedelta(days=1),
        processing_status="enriched",
        created_at=now,
    )
    session.add_all([source, item])
    session.flush()

    response = official_candidates(
        OfficialCandidatesRequest(queries=[OfficialCandidateQuery(company="deepseek", domain="llm", since_days=7)]),
        session,
    )

    assert len(response.items) == 1
    assert response.items[0].id == f"official_{item.id}"
    assert response.items[0].company == "deepseek"
    assert response.items[0].domain == "llm"
    assert response.items[0].source_name == "deepseek_news"


def test_official_detail_accepts_prefixed_internal_id():
    session = make_session()
    now = datetime.now(timezone.utc)
    source = Source(
        source_name="github_codex",
        display_name="Codex",
        source_type="github_repository",
        source_origin="repository",
        default_category="runtime",
        enabled=True,
    )
    item = Item(
        external_id="github-codex-release",
        source_name="github_codex",
        source_origin="repository",
        source_type="github_repository",
        original_url="https://github.com/openai/codex/releases/tag/v1",
        title="Codex release",
        summary="Repository release notes.",
        category="runtime",
        company="openai",
        domain="agent",
        event_type="release",
        published_at=now,
        processing_status="enriched",
        created_at=now,
    )
    session.add_all([source, item])
    session.flush()

    response = official_items_detail(OfficialItemsDetailRequest(ids=[f"repository_{item.id}"]), session)

    assert len(response.items) == 1
    assert response.items[0].id == f"repository_{item.id}"
    assert response.items[0].company == "openai"
    assert response.items[0].domain == "agent"
    assert response.items[0].summary == "Repository release notes."
