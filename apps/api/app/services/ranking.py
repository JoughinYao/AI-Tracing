from __future__ import annotations

import json
import logging
import math
from time import sleep
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..categories import (
    CATEGORY_AGENT,
    CATEGORY_FINANCE,
    CATEGORY_LLM,
    CATEGORY_OTHER,
    CATEGORY_RUNTIME,
    CATEGORY_TRENDING,
    normalize_category,
)
from ..config import get_settings
from ..models import CrawlBatch, GitHubRepoMetrics, Item, Source, SystemLog


logger = logging.getLogger(__name__)

RANKING_VERSION = "v3"
SHANGHAI = ZoneInfo("Asia/Shanghai")
DISPLAYABLE_STATUSES = {"normalized", "enriched", "completed"}
TOP6_SIZE = 6
TOP6_GUARANTEED_CATEGORIES = [
    CATEGORY_RUNTIME,
    CATEGORY_TRENDING,
    CATEGORY_LLM,
    CATEGORY_AGENT,
    CATEGORY_FINANCE,
]

EVENT_IMPACT_SCORES = {
    "security_issue": 40,
    "breaking_change": 35,
    "major_feature": 30,
    "release": 28,
    "model_update": 25,
    "product_update": 20,
    "repo_metric_change": 12,
    "community_activity": 10,
    "research": 8,
    "tutorial": 8,
    "opinion": 5,
    "other": 5,
}
CATEGORY_RELEVANCE_SCORES = {
    CATEGORY_RUNTIME: 20,
    CATEGORY_FINANCE: 17,
    CATEGORY_TRENDING: 15,
    CATEGORY_LLM: 13,
    CATEGORY_AGENT: 12,
    CATEGORY_OTHER: 6,
}
SOURCE_AUTHORITY_SCORES = {
    "deepseek_news": 13,
    "minimax_news": 12,
    "bytedance_seed_blog": 12,
    "glm_new_releases": 12,
    "kimi_blog": 12,
    "qwen_research": 12,
    "workbuddy_changelog": 12,
    "github_codex": 14,
    "github_pi_agent": 14,
    "github_hermes": 14,
    "github_opencode": 14,
    "github_trending": 8,
    "huggingface_blog": 8,
    "aihot": 8,
    "qbitai": 9,
}
AUDIENCE_DESCRIPTION = "金融垂域 AI 科技公司的后端开发人员"
CATEGORY_LABELS = {
    CATEGORY_RUNTIME: "核心 Agent runtime 更新",
    CATEGORY_TRENDING: "GitHub 上升项目",
    CATEGORY_LLM: "大模型产品与平台",
    CATEGORY_AGENT: "Agent 产品与应用",
    CATEGORY_FINANCE: "金融 AI 产品与技术",
    CATEGORY_OTHER: "其他",
}


def rank_batch_items(session: Session, batch: CrawlBatch) -> list[Item]:
    """Score a batch deterministically and return its selected TOP6 items."""
    # The application session disables autoflush, so persist freshly ingested
    # items and metric snapshots before issuing ranking queries.
    session.flush()
    items = list(session.scalars(select(Item).where(Item.crawl_batch_id == batch.id)).all())
    return rank_items(session, batch, items)


def rank_items(session: Session, batch: CrawlBatch, items: list[Item]) -> list[Item]:
    """Score supplied items and return selected TOP6 items."""
    metric_deltas = _metric_deltas(session, batch, items)

    for item in items:
        _score_item(session, batch, item, metric_deltas.get(item.id, {}))

    candidates = [item for item in items if _is_displayable(item)]
    ranked = sorted(candidates, key=_ranking_sort_key)
    llm_result = _select_top6_with_llm(session, batch, ranked)
    if llm_result is None:
        selected = _select_top6_by_category_slots(ranked)
        llm_reasons: dict[int, str] = {}
        llm_used = False
    else:
        selected, llm_reasons = llm_result
        llm_used = True
    for item in selected:
        item.selection_reason = _selection_reason(item, llm_reasons.get(item.id), llm_used=llm_used)
        if llm_used:
            item.score_breakdown = {
                **(item.score_breakdown or {}),
                "llm_selection": {
                    "enabled": True,
                    "audience": AUDIENCE_DESCRIPTION,
                    "reason": llm_reasons.get(item.id),
                },
            }
    return selected if llm_used else sorted(selected, key=_ranking_sort_key)


def _select_top6_with_llm(session: Session, batch: CrawlBatch, ranked: list[Item]) -> tuple[list[Item], dict[int, str]] | None:
    settings = get_settings()
    api_key = settings.anthropic_api_key or settings.openai_api_key
    if not settings.ranking_llm_enabled or not api_key:
        return None
    pool = _llm_candidate_pool(ranked)
    if not pool:
        return None
    items_by_id = {item.id: item for item in pool if item.id is not None}
    try:
        response = _call_ranking_llm(settings, pool)
        selected = _build_llm_selection(response, ranked, items_by_id)
    except Exception as exc:
        logger.exception("LLM ranking failed for batch_id=%s", batch.id)
        session.add(
            SystemLog(
                log_date=datetime.now(timezone.utc),
                level="warn",
                source_name=None,
                action="ranking_llm_failed",
                message="TOP6 LLM 选择失败，已使用规则排序兜底。",
                context={"batch_id": batch.id, "error": str(exc)[:300], "ranking_version": RANKING_VERSION},
            )
        )
        return None
    if not selected:
        return None

    reasons = _llm_reason_map(response, selected)
    session.add(
        SystemLog(
            log_date=datetime.now(timezone.utc),
            level="info",
            source_name=None,
            action="ranking_llm_selected",
            message="TOP6 已使用 LLM 按读者相关性选择。",
            context={
                "batch_id": batch.id,
                "selected_item_ids": [item.id for item in selected],
                "candidate_count": len(pool),
                "ranking_version": RANKING_VERSION,
            },
        )
    )
    return selected, reasons


def _llm_candidate_pool(ranked: list[Item]) -> list[Item]:
    return [item for item in ranked if item.id is not None]


def _call_ranking_llm(settings, candidates: list[Item]) -> dict:
    system_prompt = (
        "You are a technical intelligence editor for backend developers at a finance-domain AI technology company. "
        "Select today's most useful TOP6 items. Prefer Agent runtime changes, model/API capability updates, backend integration, tool calling, "
        "financial AI engineering, risk-control, investment research, quant infrastructure, observability, deployment, security, and breaking changes. "
        "Down-rank generic content generation tools, pure marketing, consumer tools, and projects weakly related to backend engineering or financial AI. "
        "If a category has no worthwhile item for this audience, return null for that category. Select only from the provided ids and return strict JSON."
    )
    user_payload = {
        "audience": AUDIENCE_DESCRIPTION,
        "selection_rules": [
            "For runtime/trending/llm/agent/finance, pick at most one most useful item per category. Return null if all candidates in that category are weakly relevant.",
            "If fewer than 6 are selected, fill from all candidates by usefulness for this audience.",
            "Put clearly unsuitable candidates in rejected_ids.",
            "Return at most 6 final items in display order.",
        ],
        "output_schema": {
            "category_picks": {"runtime": "id or null", "trending": "id or null", "llm": "id or null", "agent": "id or null", "finance": "id or null"},
            "fill_ids": ["id"],
            "rejected_ids": ["id"],
            "reasons": {"id": "short reason"},
        },
        "candidates": [_llm_candidate_payload(item) for item in candidates],
    }
    payload = {
        "model": settings.anthropic_model,
        "max_tokens": 2200,
        "temperature": 0.1,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            }
        ],
    }
    api_key = settings.anthropic_api_key or settings.openai_api_key
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    url = _anthropic_messages_url(settings.anthropic_api_url)
    max_retries = max(0, settings.ranking_llm_max_retries)
    attempts = max_retries + 1
    last_response_text = ""
    with httpx.Client(timeout=settings.ranking_llm_timeout_ms / 1000.0) as client:
        for attempt in range(1, attempts + 1):
            response = client.post(url, headers=headers, json=payload)
            last_response_text = response.text[:800]
            if response.status_code == 503 and attempt < attempts:
                wait_seconds = min(2 ** (attempt - 1), 8)
                logger.warning(
                    "ranking llm received 503, retrying attempt=%s/%s wait_seconds=%s url=%s body=%s",
                    attempt,
                    attempts,
                    wait_seconds,
                    url,
                    last_response_text,
                )
                sleep(wait_seconds)
                continue
            response.raise_for_status()
            data = response.json()
            break
        else:
            raise RuntimeError(f"LLM request failed after retries: {last_response_text}")
    return _parse_llm_json(_anthropic_response_text(data))


def _anthropic_messages_url(api_url: str) -> str:
    base = api_url.rstrip("/")
    if base.endswith("/v1/messages"):
        return base
    if base.endswith("/v1"):
        return f"{base}/messages"
    return f"{base}/v1/messages"


def _anthropic_response_text(data: dict) -> str:
    blocks = data.get("content")
    if isinstance(blocks, list):
        parts = [str(block.get("text") or "") for block in blocks if isinstance(block, dict) and block.get("type") == "text"]
        return "\n".join(part for part in parts if part).strip()
    return str(data.get("text") or "").strip()
def _llm_candidate_payload(item: Item) -> dict:
    metadata = item.extra_metadata or {}
    return {
        "id": item.id,
        "title": item.title,
        "summary": _truncate(item.summary, 700),
        "category": normalize_category(item.category),
        "category_label": CATEGORY_LABELS.get(normalize_category(item.category) or "", item.category),
        "source_name": item.source_name,
        "source_origin": item.source_origin,
        "event_type": item.event_type,
        "key_points": item.key_points[:5] if isinstance(item.key_points, list) else [],
        "value_interpretation": _truncate(item.value_interpretation, 260),
        "impact_scope": item.impact_scope[:4] if isinstance(item.impact_scope, list) else [],
        "risk_or_limitations": item.risk_or_limitations[:4] if isinstance(item.risk_or_limitations, list) else [],
        "tags": metadata.get("tags") or metadata.get("source_tags") or [],
        "stars": metadata.get("stars"),
        "stars_today": metadata.get("stars_today") or metadata.get("today_stars") or metadata.get("stars_delta"),
        "trending_rank": metadata.get("trending_rank"),
        "ranking_score": item.ranking_score,
    }


def _parse_llm_json(content: str) -> dict:
    if not content:
        raise ValueError("empty LLM response")
    if content.startswith("```"):
        content = content.strip("`")
        if content.lower().startswith("json"):
            content = content[4:].strip()
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError("LLM response is not a JSON object")
    return data


def _build_llm_selection(response: dict, ranked: list[Item], items_by_id: dict[int, Item]) -> list[Item]:
    selected: list[Item] = []
    selected_ids: set[int] = set()
    rejected_ids = _id_set(response.get("rejected_ids"))

    def add_id(value: object) -> None:
        if len(selected) >= TOP6_SIZE:
            return
        item_id = _coerce_item_id(value)
        if item_id is None or item_id in selected_ids or item_id in rejected_ids:
            return
        item = items_by_id.get(item_id)
        if item is None:
            return
        selected.append(item)
        selected_ids.add(item_id)

    category_picks = response.get("category_picks") if isinstance(response.get("category_picks"), dict) else {}
    for category in TOP6_GUARANTEED_CATEGORIES:
        add_id(category_picks.get(category))
    for value in response.get("fill_ids") or []:
        add_id(value)
    for item in ranked:
        if item.id in rejected_ids:
            continue
        add_id(item.id)
        if len(selected) >= TOP6_SIZE:
            break
    return selected


def _llm_reason_map(response: dict, selected: list[Item]) -> dict[int, str]:
    raw_reasons = response.get("reasons") if isinstance(response.get("reasons"), dict) else {}
    reasons: dict[int, str] = {}
    for item in selected:
        if item.id is None:
            continue
        reason = raw_reasons.get(str(item.id)) or raw_reasons.get(item.id)
        if reason:
            reasons[item.id] = str(reason)[:220]
    return reasons


def _id_set(values: object) -> set[int]:
    if not isinstance(values, list):
        return set()
    result: set[int] = set()
    for value in values:
        item_id = _coerce_item_id(value)
        if item_id is not None:
            result.add(item_id)
    return result


def _coerce_item_id(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _truncate(value: object, limit: int) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "..."


def _select_top6_by_category_slots(ranked: list[Item]) -> list[Item]:
    selected: list[Item] = []
    selected_ids: set[int] = set()

    def add_item(item: Item) -> None:
        if len(selected) >= TOP6_SIZE or item.id in selected_ids:
            return
        selected.append(item)
        selected_ids.add(item.id)

    for category in TOP6_GUARANTEED_CATEGORIES:
        for item in ranked:
            if normalize_category(item.category) == category:
                add_item(item)
                break

    if len(selected) < TOP6_SIZE:
        for item in ranked:
            add_item(item)
            if len(selected) >= TOP6_SIZE:
                break
    return selected


def _score_item(session: Session, batch: CrawlBatch, item: Item, deltas: dict[str, int | None]) -> None:
    event_type = item.event_type or ""
    event_impact = EVENT_IMPACT_SCORES.get(event_type, 5)
    if event_type not in EVENT_IMPACT_SCORES:
        _warn(session, item, "ranking_unknown_event_type", "Unknown event type scored with fallback.", {"event_type": item.event_type})

    category = normalize_category(item.category) or ""
    if item.category != category:
        item.category = category
    category_relevance = CATEGORY_RELEVANCE_SCORES.get(category, 6)
    if category not in CATEGORY_RELEVANCE_SCORES:
        _warn(session, item, "ranking_unknown_category", "Unknown category scored with fallback.", {"category": item.category})

    source_authority = SOURCE_AUTHORITY_SCORES.get(item.source_name)
    if item.source_name not in SOURCE_AUTHORITY_SCORES:
        source_authority = _source_authority_fallback(session, item)
        if source_authority is None:
            source_authority = 5
            _warn(session, item, "ranking_unknown_source", "未知信源使用默认排序权重。", {"source_name": item.source_name})

    freshness = _freshness_score(session, batch, item)
    community_score, community_applicable, community_rule = _community_heat(item, deltas)
    final_score = event_impact + category_relevance + freshness + source_authority + (community_score or 0)

    item.ranking_score = float(final_score)
    item.ranking_version = RANKING_VERSION
    item.event_impact_score = event_impact
    item.category_relevance_score = category_relevance
    item.freshness_score = freshness
    item.source_authority_score = source_authority
    item.community_heat_score = community_score
    item.community_heat_applicable = community_applicable
    item.selection_reason = None
    item.score_breakdown = {
        "event_impact": event_impact,
        "category_relevance": category_relevance,
        "freshness": freshness,
        "source_authority": source_authority,
        "community_heat": community_score,
        "community_heat_applicable": community_applicable,
        "final_score": final_score,
        "rules": {
            "event_type": item.event_type,
            "category": item.category,
            "source_name": item.source_name,
            "community_heat_rule": community_rule,
        },
        "inputs": {
            "trending_rank": _integer_metadata(item, "trending_rank"),
            "stars_delta": deltas.get("stars"),
            "forks_delta": deltas.get("forks"),
        },
    }


def _metric_deltas(session: Session, batch: CrawlBatch, items: list[Item]) -> dict[int, dict[str, int | None]]:
    by_item: dict[int, dict[str, int | None]] = {}
    github_items = [item for item in items if _is_github_item(item)]
    prior_by_source: dict[str, GitHubRepoMetrics | None] = {}
    for item in github_items:
        if item.source_name not in prior_by_source:
            prior_by_source[item.source_name] = session.scalar(
                select(GitHubRepoMetrics)
                .where(
                    GitHubRepoMetrics.source_name == item.source_name,
                    GitHubRepoMetrics.crawl_batch_id != batch.id,
                )
                .order_by(GitHubRepoMetrics.metrics_snapshot_at.desc(), GitHubRepoMetrics.id.desc())
                .limit(1)
            )

    for item in github_items:
        previous = prior_by_source[item.source_name]
        stars = _integer_metadata(item, "stars")
        forks = _integer_metadata(item, "forks")
        by_item[item.id] = {
            "stars": stars - previous.stars if previous and stars is not None and previous.stars is not None and stars > previous.stars else None,
            "forks": forks - previous.forks if previous and forks is not None and previous.forks is not None and forks > previous.forks else None,
        }

    _add_percentile_scores(by_item, "stars")
    _add_percentile_scores(by_item, "forks")
    return by_item


def _add_percentile_scores(deltas: dict[int, dict[str, int | None]], metric: str) -> None:
    valid = [(item_id, values[metric]) for item_id, values in deltas.items() if values.get(metric) is not None]
    if len(valid) < 3:
        return
    valid.sort(key=lambda entry: entry[1], reverse=True)
    top_twenty = math.ceil(len(valid) * 0.2)
    top_half = math.ceil(len(valid) * 0.5)
    for rank, (item_id, _) in enumerate(valid, start=1):
        if metric == "stars":
            score = 8 if rank <= top_twenty else 5 if rank <= top_half else None
        else:
            score = 4 if rank <= top_twenty else None
        deltas[item_id][f"{metric}_percentile_score"] = score


def _community_heat(item: Item, deltas: dict[str, int | None]) -> tuple[int | None, bool, str | None]:
    if not _is_github_item(item):
        return None, False, None

    rank = _integer_metadata(item, "trending_rank")
    stars = _integer_metadata(item, "stars")
    forks = _integer_metadata(item, "forks")
    if rank is not None:
        if rank <= 3:
            return 10, True, "trending_rank_1_3"
        if rank <= 10:
            return 8, True, "trending_rank_4_10"
        return 5, True, "trending_rank_over_10"

    star_percentile = deltas.get("stars_percentile_score")
    if star_percentile is not None:
        return star_percentile, True, "stars_delta_percentile"
    fork_percentile = deltas.get("forks_percentile_score")
    if deltas.get("stars") is None and fork_percentile is not None:
        return fork_percentile, True, "forks_delta_top_twenty"
    if stars is not None or forks is not None:
        return 2, True, "github_heat_data_fallback"
    return None, False, None


def _freshness_score(session: Session, batch: CrawlBatch, item: Item) -> int:
    if item.published_at is None:
        return 5
    published_at = _as_shanghai(item.published_at, naive_timezone=SHANGHAI)
    finished_at = _as_shanghai(batch.finished_at or datetime.now(timezone.utc), naive_timezone=timezone.utc)
    if published_at > finished_at:
        _warn(
            session,
            item,
            "ranking_future_published_at",
            "Published time is later than batch completion time; using the newest freshness band.",
            {"published_at": published_at.isoformat(), "batch_finished_at": finished_at.isoformat()},
        )
        return 15
    elapsed_hours = (finished_at - published_at).total_seconds() / 3600
    if elapsed_hours <= 6:
        return 15
    if elapsed_hours <= 12:
        return 12
    if elapsed_hours <= 24:
        return 9
    return 6


def _ranking_sort_key(item: Item) -> tuple[float, int, int, float, float, int]:
    published_at = _as_shanghai(item.published_at, naive_timezone=SHANGHAI) if item.published_at else None
    created_at = _as_shanghai(item.created_at, naive_timezone=timezone.utc)
    return (
        -(item.ranking_score or 0),
        -(item.event_impact_score or 0),
        1 if published_at is None else 0,
        -(published_at.timestamp() if published_at else 0),
        -created_at.timestamp(),
        item.id,
    )


def _is_displayable(item: Item) -> bool:
    metadata = item.extra_metadata or {}
    return (
        metadata.get("metrics_only") is not True
        and item.related_official_item_id is None
        and item.processing_status in DISPLAYABLE_STATUSES
        and bool(item.original_url or item.source_url)
    )


def _is_github_item(item: Item) -> bool:
    metadata = item.extra_metadata or {}
    return metadata.get("platform") == "GitHub" or item.source_type.startswith("github") or item.source_name.startswith("github_")


def _source_authority_fallback(session: Session, item: Item) -> int | None:
    source = session.scalar(select(Source).where(Source.source_name == item.source_name).limit(1))
    source_origin = item.source_origin or (source.source_origin if source else "")
    source_type = item.source_type or (source.source_type if source else "")
    if source_origin == "official":
        return 12
    if source_type == "github_repository":
        return 10
    if source_type == "github_trending" or source_origin == "community":
        return 8
    if source_type == "third_party_article" or source_origin == "third_party":
        return 7
    return None


def _integer_metadata(item: Item, key: str) -> int | None:
    value = (item.extra_metadata or {}).get(key)
    if isinstance(value, bool):
        return None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _as_shanghai(value: datetime, *, naive_timezone) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=naive_timezone)
    return value.astimezone(SHANGHAI)


def _selection_reason(item: Item, llm_reason: str | None = None, *, llm_used: bool = False) -> str:
    score = int(item.ranking_score or 0)
    base = (
        f"Rule {RANKING_VERSION}: score {score}, event {item.event_impact_score}, "
        f"category {item.category_relevance_score}, freshness {item.freshness_score}, source {item.source_authority_score}"
    )
    if llm_used:
        return f"LLM selected for finance AI backend audience. {llm_reason or base}"
    return base
def _warn(session: Session, item: Item, action: str, message: str, context: dict) -> None:
    session.add(
        SystemLog(
            log_date=datetime.now(timezone.utc),
            level="warn",
            source_name=item.source_name,
            action=action,
            message=message,
            context={"item_id": item.id, **context},
        )
    )
