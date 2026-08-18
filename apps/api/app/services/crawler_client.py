from __future__ import annotations

import logging
from typing import Any

import httpx

from ..config import get_settings


settings = get_settings()
logger = logging.getLogger(__name__)


def is_crawler_available() -> bool:
    try:
        logger.info("crawler health check start url=%s/health", settings.crawler_base_url)
        with httpx.Client(timeout=1.0) as client:
            response = client.get(f"{settings.crawler_base_url}/health")
            response.raise_for_status()
        logger.info("crawler health check ok url=%s/health", settings.crawler_base_url)
        return True
    except httpx.HTTPStatusError:
        logger.info("crawler health check returned http status but service is reachable url=%s/health", settings.crawler_base_url)
        return True
    except httpx.HTTPError:
        logger.exception("crawler health check failed url=%s/health", settings.crawler_base_url)
        return False


def crawl_source(
    source_name: str,
    *,
    since: str | None = None,
    max_pages: int | None = None,
    max_items: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"source_name": source_name}
    if since is not None:
        payload["since"] = since
    if max_pages is not None:
        payload["max_pages"] = max_pages
    if max_items is not None:
        payload["max_items"] = max_items
    try:
        logger.info("crawler request start endpoint=/internal/crawl source_name=%s payload=%s", source_name, payload)
        with httpx.Client(timeout=settings.crawler_timeout_ms / 1000.0) as client:
            response = client.post(f"{settings.crawler_base_url}/internal/crawl", json=payload)
            response.raise_for_status()
            data = response.json()
            logger.info(
                "crawler request finished endpoint=/internal/crawl source_name=%s status=%s returned_count=%s",
                source_name,
                data.get("status"),
                len(data.get("items") or []),
            )
            if "items" not in data:
                return {
                    "status": "crawl_failed",
                    "source_name": source_name,
                    "source_url": None,
                    "items": [],
                    "stats": {"raw_count": 0, "returned_count": 0, "duplicate_count": 0, "llm_success_count": 0, "llm_failed_count": 0},
                    "error": {"code": "INVALID_CRAWLER_RESPONSE", "message": "Crawler response missing items."},
                }
            data["_crawler_response"] = True
            return data
    except Exception as exc:
        logger.exception("crawler request failed endpoint=/internal/crawl source_name=%s", source_name)
        return {
            "status": "crawl_failed",
            "source_name": source_name,
            "source_url": None,
            "items": [],
            "stats": {"raw_count": 0, "returned_count": 0, "duplicate_count": 0, "llm_success_count": 0, "llm_failed_count": 0},
            "error": {"code": "CRAWLER_REQUEST_FAILED", "message": str(exc)[:300]},
        }


def crawl_sources_batch(source_names: list[str]) -> dict[str, Any]:
    payload = {"source_names": source_names}
    try:
        with httpx.Client(timeout=settings.crawler_timeout_ms / 1000.0) as client:
            response = client.post(f"{settings.crawler_base_url}/internal/crawl/batch", json=payload)
            response.raise_for_status()
            data = response.json()
            if "responses" not in data or not isinstance(data["responses"], list):
                return {
                    "status": "failed",
                    "source_names": source_names,
                    "responses": [],
                    "stats": {"raw_count": 0, "returned_count": 0, "duplicate_count": 0, "llm_success_count": 0, "llm_failed_count": 0},
                    "error": {"code": "INVALID_CRAWLER_BATCH_RESPONSE", "message": "Crawler batch response missing responses."},
                }
            data["_crawler_batch_response"] = True
            return data
    except Exception as exc:
        return {
            "status": "failed",
            "source_names": source_names,
            "responses": [],
            "stats": {"raw_count": 0, "returned_count": 0, "duplicate_count": 0, "llm_success_count": 0, "llm_failed_count": 0},
            "error": {"code": "CRAWLER_BATCH_REQUEST_FAILED", "message": str(exc)[:300]},
        }


def sync_github_repository_source(payload: dict[str, Any]) -> dict[str, Any]:
    return _send_source_config("POST", "/internal/sources/github-repository", payload)


def delete_github_repository_source(source_name: str) -> dict[str, Any]:
    return _send_source_config("DELETE", f"/internal/sources/github-repository/{source_name}", None)


def sync_third_party_source(payload: dict[str, Any]) -> dict[str, Any]:
    return _send_source_config("POST", "/internal/sources/third-party", payload)


def delete_third_party_source(source_name: str) -> dict[str, Any]:
    return _send_source_config("DELETE", f"/internal/sources/third-party/{source_name}", None)


def _send_source_config(method: str, path: str, payload: dict[str, Any] | None) -> dict[str, Any]:
    try:
        with httpx.Client(timeout=settings.crawler_timeout_ms / 1000.0) as client:
            response = client.request(method, f"{settings.crawler_base_url}{path}", json=payload)
            response.raise_for_status()
            return response.json() if response.content else {"status": "success", "error": None}
    except Exception as exc:
        return {"status": "failed", "error": {"code": "CRAWLER_SOURCE_SYNC_FAILED", "message": str(exc)[:300]}}
