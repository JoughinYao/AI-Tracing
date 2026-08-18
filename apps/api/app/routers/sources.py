from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..categories import CATEGORY_LLM, CATEGORY_RUNTIME
from ..db import session_scope
from ..models import Source, SystemLog
from ..schemas import GitHubSourceCreate, SourceRead, ThirdPartySourceCreate
from ..services.crawler_client import (
    delete_github_repository_source,
    delete_third_party_source,
    sync_github_repository_source,
    sync_third_party_source,
)

router = APIRouter(prefix="/api", tags=["sources"])


def get_session():
    with session_scope() as session:
        yield session


@router.get("/sources", response_model=list[SourceRead])
def list_sources(session: Session = Depends(get_session)):
    rows = session.scalars(select(Source).order_by(Source.id.asc())).all()
    return [SourceRead.model_validate(row) for row in rows]


@router.post("/sources/github-repository", response_model=SourceRead)
def upsert_github_source(payload: GitHubSourceCreate, session: Session = Depends(get_session)):
    sync_payload = {"source_name": payload.source_name, "repo_url": payload.repo_url, "is_official": payload.is_official}
    sync_result = sync_github_repository_source(sync_payload)
    synced = sync_result.get("status") == "success"
    source = _get_or_create_source(session, payload.source_name)
    source.display_name = payload.source_name
    source.default_category = CATEGORY_RUNTIME
    source.source_type = "github_repository"
    source.source_origin = "repository"
    source.crawl_strategy = "latest_only"
    source.source_url = payload.repo_url
    source.crawler_config = sync_payload
    _apply_sync_state(session, source, synced, sync_result)
    return SourceRead.model_validate(source)


@router.delete("/sources/github-repository/{source_name}", response_model=SourceRead)
def remove_github_source(source_name: str, session: Session = Depends(get_session)):
    source = _get_or_create_source(session, source_name)
    result = delete_github_repository_source(source_name)
    source.enabled = False
    source.latest_status = "deleted" if result.get("status") == "success" else "delete_failed"
    source.last_error = _error_message(result)
    return SourceRead.model_validate(source)


@router.post("/sources/third-party", response_model=SourceRead)
def upsert_third_party_source(payload: ThirdPartySourceCreate, session: Session = Depends(get_session)):
    sync_payload = payload.model_dump()
    sync_result = sync_third_party_source(sync_payload)
    synced = sync_result.get("status") == "success"
    source = _get_or_create_source(session, payload.source_name)
    source.display_name = payload.platform
    source.default_category = CATEGORY_LLM
    source.source_type = "third_party_article"
    source.source_origin = "third_party"
    source.crawl_strategy = "daily_incremental"
    source.source_url = payload.source_url
    source.crawler_config = sync_payload
    _apply_sync_state(session, source, synced, sync_result)
    return SourceRead.model_validate(source)


@router.delete("/sources/third-party/{source_name}", response_model=SourceRead)
def remove_third_party_source(source_name: str, session: Session = Depends(get_session)):
    source = _get_or_create_source(session, source_name)
    result = delete_third_party_source(source_name)
    source.enabled = False
    source.latest_status = "deleted" if result.get("status") == "success" else "delete_failed"
    source.last_error = _error_message(result)
    return SourceRead.model_validate(source)


def _get_or_create_source(session: Session, source_name: str) -> Source:
    source = session.scalar(select(Source).where(Source.source_name == source_name))
    if source:
        return source
    source = Source(source_name=source_name, display_name=source_name, enabled=False)
    session.add(source)
    session.flush()
    return source


def _apply_sync_state(session: Session, source: Source, synced: bool, sync_result: dict) -> None:
    now = datetime.now(timezone.utc)
    source.synced_to_crawler_at = now if synced else source.synced_to_crawler_at
    source.latest_checked_at = now
    source.enabled = synced
    source.latest_status = "synced" if synced else "sync_failed"
    source.last_error = None if synced else _error_message(sync_result)
    session.add(
        SystemLog(
            log_date=now,
            level="info" if synced else "error",
            source_name=source.source_name,
            action="source_sync_succeeded" if synced else "source_sync_failed",
            message=f"信源{source.source_name}同步{'成功' if synced else '失败'}",
            context={"sync_result": sync_result},
        )
    )


def _error_message(result: dict) -> str | None:
    error = result.get("error")
    if isinstance(error, dict):
        return error.get("message") or error.get("code")
    return None
