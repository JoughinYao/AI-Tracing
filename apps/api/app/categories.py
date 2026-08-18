from __future__ import annotations


CATEGORY_RUNTIME = "runtime"
CATEGORY_TRENDING = "trending"
CATEGORY_LLM = "llm"
CATEGORY_AGENT = "agent"
CATEGORY_FINANCE = "finance"
CATEGORY_OTHER = "other"

CATEGORY_BY_SECTION = {
    "core-agent": CATEGORY_RUNTIME,
    "github-stars": CATEGORY_TRENDING,
    "model-platform": CATEGORY_LLM,
    "agent-products": CATEGORY_AGENT,
    "finance-ai": CATEGORY_FINANCE,
    "others": CATEGORY_OTHER,
}

CATEGORY_ALIASES = {
    CATEGORY_RUNTIME: CATEGORY_RUNTIME,
    CATEGORY_TRENDING: CATEGORY_TRENDING,
    CATEGORY_LLM: CATEGORY_LLM,
    CATEGORY_AGENT: CATEGORY_AGENT,
    CATEGORY_FINANCE: CATEGORY_FINANCE,
    CATEGORY_OTHER: CATEGORY_OTHER,
    "核心Agent Runtime更新": CATEGORY_RUNTIME,
    "核心Agent runtime更新": CATEGORY_RUNTIME,
    "核心 Agent Runtime 更新": CATEGORY_RUNTIME,
    "核心 Agent runtime 更新": CATEGORY_RUNTIME,
    "Github 上升项目": CATEGORY_TRENDING,
    "GitHub 上升项目": CATEGORY_TRENDING,
    "大模型产品与平台": CATEGORY_LLM,
    "Agent 产品与应用": CATEGORY_AGENT,
    "金融AI产品与技术": CATEGORY_FINANCE,
    "金融 AI 产品与技术": CATEGORY_FINANCE,
    "其他": CATEGORY_OTHER,
}


def normalize_category(value: str | None) -> str | None:
    if value is None:
        return None
    compact = value.strip()
    if not compact:
        return None
    return CATEGORY_ALIASES.get(compact, compact)


def category_for_section(section: str) -> str | None:
    return CATEGORY_BY_SECTION.get(section)


def category_for_item(source_name: str | None, source_type: str | None, raw_category: str | None) -> str | None:
    if source_name == "github_trending" or source_type == "github_trending":
        return CATEGORY_TRENDING
    return normalize_category(raw_category)
