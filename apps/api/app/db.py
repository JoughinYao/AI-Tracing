from __future__ import annotations

from contextlib import contextmanager
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings


settings = get_settings()
engine = create_engine(
    settings.database_url,
    future=True,
    pool_pre_ping=True,
    connect_args={"timeout": 30} if settings.database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(engine, "connect")
def _configure_sqlite(dbapi_connection, _connection_record):
    if not settings.database_url.startswith("sqlite"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=30000")
    cursor.close()


class Base(DeclarativeBase):
    pass


@contextmanager
def session_scope() -> Session:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    from . import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _apply_schema_upgrades()


def _apply_schema_upgrades() -> None:
    """Apply the small additive SQLite upgrades used before Alembic is introduced."""
    if not settings.database_url.startswith("sqlite"):
        return

    upgrades = {
        "items": {
            "source_origin": "VARCHAR(40) NOT NULL DEFAULT 'official'",
            "ranking_score": "FLOAT",
            "ranking_version": "VARCHAR(32)",
            "event_impact_score": "INTEGER",
            "category_relevance_score": "INTEGER",
            "freshness_score": "INTEGER",
            "source_authority_score": "INTEGER",
            "community_heat_score": "INTEGER",
            "community_heat_applicable": "BOOLEAN NOT NULL DEFAULT 0",
            "score_breakdown": "JSON NOT NULL DEFAULT '{}'",
            "selection_reason": "VARCHAR(255)",
            "key_points": "JSON NOT NULL DEFAULT '[]'",
            "technical_details": "JSON NOT NULL DEFAULT '[]'",
            "value_interpretation": "JSON",
            "impact_scope": "JSON NOT NULL DEFAULT '[]'",
            "risk_or_limitations": "JSON NOT NULL DEFAULT '[]'",
            "recommended_action": "TEXT",
            "evidence_excerpts": "JSON NOT NULL DEFAULT '[]'",
            "information_gaps": "JSON NOT NULL DEFAULT '[]'",
            "content_depth": "VARCHAR(40)",
            "primary_image": "JSON",
            "image_candidates": "JSON NOT NULL DEFAULT '[]'",
            "company": "VARCHAR(80)",
            "domain": "VARCHAR(40)",
            "canonical_key": "VARCHAR(200)",
            "product_key": "VARCHAR(160)",
            "model_key": "VARCHAR(160)",
            "version_key": "VARCHAR(120)",
            "related_official_item_id": "INTEGER",
            "relation_type": "VARCHAR(40)",
            "relation": "JSON",
        },
        "sources": {
            "source_origin": "VARCHAR(40) NOT NULL DEFAULT 'official'",
            "crawl_strategy": "VARCHAR(40) NOT NULL DEFAULT 'latest_only'",
            "last_success_at": "DATETIME",
            "last_checkpoint_at": "DATETIME",
            "last_error": "TEXT",
            "crawler_config": "JSON NOT NULL DEFAULT '{}'",
            "synced_to_crawler_at": "DATETIME",
        },
        "crawl_batches": {
            "raw_count": "INTEGER NOT NULL DEFAULT 0",
            "saved_count": "INTEGER NOT NULL DEFAULT 0",
            "comment_attached_count": "INTEGER NOT NULL DEFAULT 0",
            "duplicate_dropped_count": "INTEGER NOT NULL DEFAULT 0",
        },
        "crawl_source_runs": {
            "raw_count": "INTEGER NOT NULL DEFAULT 0",
            "returned_count": "INTEGER NOT NULL DEFAULT 0",
            "saved_count": "INTEGER NOT NULL DEFAULT 0",
            "attached_count": "INTEGER NOT NULL DEFAULT 0",
            "dropped_count": "INTEGER NOT NULL DEFAULT 0",
        },
        "daily_report_items": {
            "ranking_score_snapshot": "FLOAT",
            "score_breakdown_snapshot": "JSON NOT NULL DEFAULT '{}'",
            "selection_reason_snapshot": "VARCHAR(255)",
        },
    }
    with engine.begin() as connection:
        for table_name, columns in upgrades.items():
            existing = {row[1] for row in connection.exec_driver_sql(f"PRAGMA table_info({table_name})")}
            for column_name, definition in columns.items():
                if column_name not in existing:
                    connection.exec_driver_sql(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")
        _normalize_existing_categories(connection)


def _normalize_existing_categories(connection) -> None:
    aliases = {
        "核心Agent Runtime更新": "runtime",
        "核心Agent runtime更新": "runtime",
        "核心 Agent Runtime 更新": "runtime",
        "核心 Agent runtime 更新": "runtime",
        "Github 上升项目": "trending",
        "GitHub 上升项目": "trending",
        "大模型产品与平台": "llm",
        "Agent 产品与应用": "agent",
        "金融AI产品与技术": "finance",
        "金融 AI 产品与技术": "finance",
        "其他": "other",
    }
    for old_value, new_value in aliases.items():
        connection.exec_driver_sql("UPDATE items SET category = ? WHERE category = ?", (new_value, old_value))
    connection.exec_driver_sql(
        "UPDATE items SET category = ? WHERE source_name = ? OR source_type = ?",
        ("trending", "github_trending", "github_trending"),
    )
    source_aliases = {
        "核心 Agent runtime 更新": "runtime",
        "GitHub 上升项目": "trending",
        "大模型产品与平台": "llm",
        "Agent 产品与应用": "agent",
        "金融 AI 产品与技术": "finance",
        "其他": "other",
    }
    for old_value, new_value in source_aliases.items():
        connection.exec_driver_sql("UPDATE sources SET default_category = ? WHERE default_category = ?", (new_value, old_value))
    connection.exec_driver_sql("UPDATE sources SET source_origin = 'community', crawl_strategy = 'trending' WHERE source_name = 'github_trending'")
    connection.exec_driver_sql("UPDATE sources SET source_origin = 'official', crawl_strategy = 'latest_only' WHERE source_name != 'github_trending' AND source_origin IS NULL")
    connection.exec_driver_sql("UPDATE items SET source_origin = 'community' WHERE source_name = 'github_trending' OR source_type = 'github_trending'")
    connection.exec_driver_sql("UPDATE items SET source_origin = 'third_party' WHERE source_type = 'third_party_article'")
    connection.exec_driver_sql("UPDATE items SET source_origin = 'official' WHERE source_origin IS NULL OR source_origin = ''")
