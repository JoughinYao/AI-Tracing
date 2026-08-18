from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import CrawlBatch, Source, SystemLog
from ..schemas import BatchRead, CrawlRequest, CrawlRunResponse
from ..services.batch_runner import rerank_latest_daily_report, run_daily_batch
from ..services.crawler_client import is_crawler_available

router = APIRouter(prefix="/api", tags=["batches"])


def get_session():
    with session_scope() as session:
        yield session


@router.get("/crawl-batches", response_model=list[BatchRead])
def list_batches(session: Session = Depends(get_session)):
    rows = session.scalars(select(CrawlBatch).order_by(CrawlBatch.batch_date.desc())).all()
    return [BatchRead.model_validate(row) for row in rows]


@router.get("/crawl-batches/{batch_id}", response_model=BatchRead)
def get_batch(batch_id: int, session: Session = Depends(get_session)):
    row = session.get(CrawlBatch, batch_id)
    return BatchRead.model_validate(row)


def _run_batch_background(batch_id: int, source_names: list[str] | None = None) -> None:
    with session_scope() as session:
        run_daily_batch(session, batch_id=batch_id, source_names=source_names)


def _requested_source_names(request: CrawlRequest | None) -> list[str] | None:
    if not request:
        return None
    if request.source_names:
        names = [name.strip() for name in request.source_names if name and name.strip()]
    elif request.source_name and request.source_name.strip() != "all":
        names = [request.source_name.strip()]
    else:
        return None
    return list(dict.fromkeys(names))


@router.post("/crawl-batches/run", response_model=CrawlRunResponse)
def trigger_batch(
    background_tasks: BackgroundTasks,
    request: CrawlRequest | None = None,
    session: Session = Depends(get_session),
):
    now = datetime.now(timezone.utc)
    requested_source_names = _requested_source_names(request)
    running = session.scalar(select(CrawlBatch).where(CrawlBatch.status == "running").order_by(CrawlBatch.id.desc()))
    if running:
        triggered_at = running.triggered_at
        if triggered_at.tzinfo is None:
            triggered_at = triggered_at.replace(tzinfo=timezone.utc)
        if now - triggered_at < timedelta(minutes=60):
            return CrawlRunResponse(
                batch_id=running.id,
                status=running.status,
                message="采集任务正在运行。",
                top6_count=running.top6_count,
            )
        running.status = "failed"
        running.finished_at = now
        running.notes = "上一轮采集任务超时，已自动结束。"
        session.flush()

    source_query = select(Source).where(Source.enabled.is_(True))
    if requested_source_names:
        source_query = source_query.where(Source.source_name.in_(requested_source_names))
    enabled_sources = list(session.scalars(source_query).all())
    enabled_source_names = [source.source_name for source in enabled_sources]
    if requested_source_names:
        missing = sorted(set(requested_source_names) - set(enabled_source_names))
        if missing:
            raise HTTPException(status_code=400, detail=f"信源不存在或未启用：{', '.join(missing)}")
    if not enabled_source_names:
        raise HTTPException(status_code=400, detail="当前没有可请求的已启用信源。")

    if not is_crawler_available():
        session.add(
            SystemLog(
                log_date=now,
                level="error",
                source_name=None,
                action="crawler_unavailable",
                message="数据请求失败，爬虫端服务中断",
                context={"crawler_base_url": "configured"},
            )
        )
        session.commit()
        raise HTTPException(status_code=503, detail="数据请求失败，爬虫端服务中断")

    batch = CrawlBatch(
        batch_date=now,
        status="running",
        triggered_at=now,
        total_sources=0,
        success_sources=0,
        failed_sources=0,
        top6_count=0,
        notes=f"selected_sources={','.join(enabled_source_names)}",
    )
    session.add(batch)
    session.flush()
    batch_id = batch.id
    session.commit()
    background_tasks.add_task(_run_batch_background, batch_id, enabled_source_names)
    return CrawlRunResponse(batch_id=batch_id, status="running", message="采集任务已开始。", top6_count=0)


@router.post("/crawl-batches/rerank", response_model=CrawlRunResponse)
def rerank_batch(session: Session = Depends(get_session)):
    running = session.scalar(select(CrawlBatch).where(CrawlBatch.status == "running").order_by(CrawlBatch.id.desc()))
    if running:
        raise HTTPException(status_code=409, detail="采集任务仍在运行，请结束后再排序。")
    try:
        batch, top6 = rerank_latest_daily_report(session)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CrawlRunResponse(batch_id=batch.id, status=batch.status, message="TOP6 已重新排序。", top6_count=len(top6))
