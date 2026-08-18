from __future__ import annotations

from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import session_scope
from ..models import GitHubRepoMetrics, Source
from ..schemas import AgentMetricsSeries, CoreAgentMetricsResponse, MetricsPoint

router = APIRouter(prefix="/api", tags=["metrics"])


def get_session():
    with session_scope() as session:
        yield session


CORE_AGENT_SOURCES = ["github_codex", "github_pi_agent", "github_hermes", "github_opencode"]


@router.get("/core-agent/metrics", response_model=CoreAgentMetricsResponse)
def core_agent_metrics(
    range: str = Query(default="all", pattern="^(all|week|month)$"),
    session: Session = Depends(get_session),
):
    cutoff = None
    now = datetime.now(timezone.utc)
    if range == "week":
        cutoff = now - timedelta(days=7)
    elif range == "month":
        cutoff = now - timedelta(days=30)

    source_rows = session.scalars(select(Source).where(Source.source_name.in_(CORE_AGENT_SOURCES))).all()
    display_names = {source.source_name: source.display_name for source in source_rows}
    agents: list[AgentMetricsSeries] = []
    for source_name in CORE_AGENT_SOURCES:
        query = select(GitHubRepoMetrics).where(GitHubRepoMetrics.source_name == source_name)
        if cutoff:
            query = query.where(GitHubRepoMetrics.metrics_snapshot_at >= cutoff)
        rows = session.scalars(query.order_by(GitHubRepoMetrics.metrics_snapshot_at.asc())).all()
        series = [
            MetricsPoint(
                snapshot_at=row.metrics_snapshot_at,
                stars=row.stars,
                forks=row.forks,
                watchers=row.watchers,
                subscribers=row.subscribers,
                open_issues=row.open_issues,
                pushed_at=row.pushed_at,
                updated_at=row.updated_at,
            )
            for row in rows
        ]
        agents.append(AgentMetricsSeries(source_name=source_name, display_name=display_names.get(source_name, source_name), series=series))
    return CoreAgentMetricsResponse(range=range, agents=agents)
