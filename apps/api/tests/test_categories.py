from app.categories import category_for_item, category_for_section, normalize_category


def test_category_codes_are_used_by_sections():
    assert category_for_section("core-agent") == "runtime"
    assert category_for_section("github-stars") == "trending"
    assert category_for_section("model-platform") == "llm"
    assert category_for_section("agent-products") == "agent"
    assert category_for_section("finance-ai") == "finance"
    assert category_for_section("others") == "other"


def test_legacy_chinese_categories_normalize_to_codes():
    assert normalize_category("核心 Agent runtime 更新") == "runtime"
    assert normalize_category("GitHub 上升项目") == "trending"
    assert normalize_category("大模型产品与平台") == "llm"
    assert normalize_category("Agent 产品与应用") == "agent"
    assert normalize_category("金融 AI 产品与技术") == "finance"
    assert normalize_category("其他") == "other"


def test_github_trending_source_forces_trending_category():
    assert category_for_item("github_trending", "github_trending", "runtime") == "trending"
    assert category_for_item("github_trending", "github_trending", "核心 Agent runtime 更新") == "trending"
