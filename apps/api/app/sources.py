from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .categories import CATEGORY_AGENT, CATEGORY_LLM, CATEGORY_RUNTIME, CATEGORY_TRENDING
from .models import Source


DEFAULT_SOURCES = [
    {
        "source_name": "deepseek_news",
        "display_name": "DeepSeek News",
        "default_category": CATEGORY_LLM,
        "source_type": "official_changelog",
        "source_origin": "official",
        "crawl_strategy": "latest_only",
        "source_url": "https://api-docs.deepseek.com/zh-cn/",
        "crawler_config": {"source_url": "https://api-docs.deepseek.com/zh-cn/"},
    },
    {
        "source_name": "minimax_news",
        "display_name": "MiniMax News",
        "default_category": CATEGORY_LLM,
        "source_type": "official_changelog",
        "source_origin": "official",
        "crawl_strategy": "latest_only",
        "source_url": "https://www.minimaxi.com/news",
        "crawler_config": {"source_url": "https://www.minimaxi.com/news", "default_max_items": 10},
    },
    {
        "source_name": "bytedance_seed_blog",
        "display_name": "ByteDance Seed Blog",
        "default_category": CATEGORY_LLM,
        "source_type": "official_changelog",
        "source_origin": "official",
        "crawl_strategy": "latest_only",
        "source_url": "https://seed.bytedance.com/zh/blog",
        "crawler_config": {"source_url": "https://seed.bytedance.com/zh/blog", "default_max_items": 10},
    },
    {
        "source_name": "glm_new_releases",
        "display_name": "GLM New Releases",
        "default_category": CATEGORY_LLM,
        "source_type": "official_changelog",
        "source_origin": "official",
        "crawl_strategy": "latest_only",
        "source_url": "https://docs.bigmodel.cn/cn/update/new-releases.md",
        "crawler_config": {"source_url": "https://docs.bigmodel.cn/cn/update/new-releases.md", "default_max_items": 10},
    },
    {
        "source_name": "kimi_blog",
        "display_name": "Kimi Blog",
        "default_category": CATEGORY_LLM,
        "source_type": "official_changelog",
        "source_origin": "official",
        "crawl_strategy": "latest_only",
        "source_url": "https://www.kimi.com/blog/",
        "crawler_config": {"source_url": "https://www.kimi.com/blog/", "default_max_items": 10},
    },
    {
        "source_name": "qwen_research",
        "display_name": "Qwen Research",
        "default_category": CATEGORY_LLM,
        "source_type": "official_changelog",
        "source_origin": "official",
        "crawl_strategy": "latest_only",
        "source_url": "https://qwen.ai/research#research_latest_advancements",
        "crawler_config": {"source_url": "https://qwen.ai/research#research_latest_advancements", "default_max_items": 10},
    },
    {
        "source_name": "workbuddy_changelog",
        "display_name": "WorkBuddy Changelog",
        "default_category": CATEGORY_AGENT,
        "source_type": "official_changelog",
        "source_origin": "official",
        "crawl_strategy": "latest_only",
        "source_url": "https://www.workbuddy.cn/docs/workbuddy/Changelog",
        "crawler_config": {"source_url": "https://www.workbuddy.cn/docs/workbuddy/Changelog", "default_max_items": 10},
    },
    {
        "source_name": "github_codex",
        "display_name": "Codex",
        "default_category": CATEGORY_RUNTIME,
        "source_type": "github_repository",
        "source_origin": "repository",
        "crawl_strategy": "latest_only",
        "source_url": "https://github.com/openai/codex",
        "crawler_config": {"repo_url": "https://github.com/openai/codex"},
    },
    {
        "source_name": "github_pi_agent",
        "display_name": "Pi Agent",
        "default_category": CATEGORY_RUNTIME,
        "source_type": "github_repository",
        "source_origin": "repository",
        "crawl_strategy": "latest_only",
        "source_url": None,
        "crawler_config": {},
    },
    {
        "source_name": "github_hermes",
        "display_name": "Hermes Agent",
        "default_category": CATEGORY_RUNTIME,
        "source_type": "github_repository",
        "source_origin": "repository",
        "crawl_strategy": "latest_only",
        "source_url": None,
        "crawler_config": {},
    },
    {
        "source_name": "github_opencode",
        "display_name": "OpenCode",
        "default_category": CATEGORY_RUNTIME,
        "source_type": "github_repository",
        "source_origin": "repository",
        "crawl_strategy": "latest_only",
        "source_url": None,
        "crawler_config": {},
    },
    {
        "source_name": "github_trending",
        "display_name": "GitHub Trending",
        "default_category": CATEGORY_TRENDING,
        "source_type": "github_trending",
        "source_origin": "community",
        "crawl_strategy": "trending",
        "source_url": "https://github.com/trending",
        "crawler_config": {"source_url": "https://github.com/trending"},
    },
    {
        "source_name": "qbitai",
        "display_name": "量子位",
        "default_category": CATEGORY_LLM,
        "source_type": "third_party_article",
        "source_origin": "third_party",
        "crawl_strategy": "daily_incremental",
        "source_url": "https://www.qbitai.com",
        "crawler_config": {
            "source_url": "https://www.qbitai.com",
            "platform": "量子位",
            "list_container_xpath": "/html/body/div[2]/div[1]",
            "article_url_regex": r"https?://www\.qbitai\.com/\d{4}/\d{2}/\d+\.html$",
            "default_max_candidates": 18,
            "default_max_items": 10,
            "default_max_pages": 1,
            "render_list_page": False,
            "render_article_page": False,
        },
    },
    {
        "source_name": "huggingface_blog",
        "display_name": "Hugging Face Blog",
        "default_category": CATEGORY_LLM,
        "source_type": "third_party_article",
        "source_origin": "third_party",
        "crawl_strategy": "daily_incremental",
        "source_url": "https://huggingface.co/blog/feed.xml",
        "crawler_config": {"source_url": "https://huggingface.co/blog/feed.xml", "default_max_items": 10},
    },
    {
        "source_name": "aihot",
        "display_name": "AIHOT",
        "default_category": CATEGORY_LLM,
        "source_type": "third_party_article",
        "source_origin": "third_party",
        "crawl_strategy": "daily_incremental",
        "source_url": "https://aihot.virxact.com",
        "crawler_config": {
            "source_url": "https://aihot.virxact.com",
            "default_max_items": 10,
        },
    },
]


def ensure_sources(session: Session) -> None:
    for source_data in DEFAULT_SOURCES:
        source = session.scalar(select(Source).where(Source.source_name == source_data["source_name"]))
        if source:
            for key, value in source_data.items():
                if key in {"default_category", "source_type", "source_origin", "crawl_strategy", "source_url", "crawler_config", "display_name"} and getattr(source, key) != value:
                    setattr(source, key, value)
                elif key != "source_name" and getattr(source, key) in (None, "", {}):
                    setattr(source, key, value)
            source.enabled = True
        else:
            session.add(Source(enabled=True, **source_data))
