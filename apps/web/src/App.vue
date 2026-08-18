<template>
  <div class="app-shell">
    <header class="topbar">
      <div class="brand">
        <img class="brand-mark" src="/favicon.svg" alt="AI Tracing" />
        <div>
          <div class="brand-name">AI Tracing</div>
          <div class="brand-sub">internal daily briefing</div>
        </div>
      </div>
      <nav class="nav">
        <RouterLink v-for="item in navItems" :key="item.to" :to="item.to" class="nav-link">
          {{ item.label }}
        </RouterLink>
      </nav>
    </header>
    <main class="page-shell">
      <RouterView v-slot="{ Component, route }">
        <Transition name="page-flow" mode="out-in">
          <component :is="Component" :key="route.fullPath" />
        </Transition>
      </RouterView>
    </main>
    <button class="settings-trigger" type="button" aria-label="系统设置" title="系统设置" @click="openSettings">
      ⚙
    </button>
    <Transition name="settings-pop">
      <div v-if="settingsOpen" class="settings-overlay" role="presentation" @click.self="closeSettings">
        <section class="settings-window" role="dialog" aria-modal="true" aria-labelledby="settings-title">
        <header class="settings-head">
          <div>
            <h2 id="settings-title">系统设置</h2>
            <p>{{ settingsSubtitle }}</p>
          </div>
          <div class="settings-actions">
            <button class="settings-close" type="button" aria-label="关闭" title="关闭" @click="closeSettings">×</button>
          </div>
        </header>
        <p v-if="settingsError" class="error-text">{{ settingsError }}</p>
        <div class="settings-body">
          <section class="settings-card settings-card-wide">
            <div class="settings-card-head">
              <div>
                <h3>系统消息</h3>
                <p>北京时间 · 近3天 · {{ selectedSourceSummary }}</p>
              </div>
              <div class="settings-button-group">
                <button class="action-btn" type="button" :disabled="isRefreshing || isReranking || !selectedSourceNames.length" @click="refreshFromCrawler">
                  {{ isRefreshing ? "采集中" : "刷新数据" }}
                </button>
                <button class="action-btn" type="button" :disabled="isRefreshing || isReranking" @click="rerankTop6">
                  {{ isReranking ? "排序中" : "排序测试" }}
                </button>
              </div>
            </div>
            <div class="source-check-toolbar">
              <label class="source-check-all">
                <input type="checkbox" :checked="allEnabledSourcesSelected" :disabled="isRefreshing || !enabledSources.length" @change="toggleAllSources" />
                <span>全部已启用信源</span>
              </label>
              <span>{{ selectedSourceNames.length }} / {{ enabledSources.length }} 已选</span>
            </div>
            <div v-if="enabledSources.length" class="source-check-grid" aria-label="请求信源">
              <label v-for="source in enabledSources" :key="source.source_name" class="source-check-item">
                <input v-model="selectedSourceNames" type="checkbox" :value="source.source_name" :disabled="isRefreshing" />
                <span>
                  <strong>{{ source.display_name }}</strong>
                  <small>{{ source.source_name }}</small>
                </span>
              </label>
            </div>
            <div v-else class="settings-empty compact">暂无已启用信源</div>
            <div v-if="systemLogs.length" class="settings-log-list" aria-live="polite">
              <div v-for="log in systemLogs" :key="log.id" class="settings-log-row" :data-level="log.level">
                <span>{{ formatSystemMessage(log) }}</span>
              </div>
            </div>
            <div v-else class="settings-empty">近3天暂无系统消息</div>
          </section>

          <section class="settings-card source-panel">
            <div class="settings-card-head">
              <div>
                <h3>GitHub源</h3>
                <p>仓库信源配置</p>
              </div>
            </div>
            <form class="source-form" @submit.prevent="saveGithubSource">
              <label class="field">
                <span>source_name</span>
                <input v-model.trim="githubForm.source_name" placeholder="github_my_agent" required />
              </label>
              <label class="field">
                <span>仓库地址</span>
                <input v-model.trim="githubForm.repo_url" placeholder="https://github.com/owner/repo" required />
              </label>
              <label class="check-field">
                <input v-model="githubForm.is_official" type="checkbox" />
                <span>官方源</span>
              </label>
              <button class="action-btn" type="submit" :disabled="isSavingSource">
                {{ isSavingSource ? "同步中" : "保存 GitHub 源" }}
              </button>
            </form>
            <div class="settings-source-list">
              <div v-for="source in githubSources" :key="source.source_name" class="settings-source-row">
                <strong>{{ source.display_name }}</strong>
                <span>{{ source.source_name }} · {{ source.enabled ? "已启用" : source.latest_status || "未启用" }}</span>
              </div>
            </div>
          </section>

          <section class="settings-card source-panel">
            <div class="settings-card-head">
              <div>
                <h3>三方源</h3>
                <p>文章信源配置</p>
              </div>
            </div>
            <form class="source-form third-party" @submit.prevent="saveThirdPartySource">
              <label class="field">
                <span>source_name</span>
                <input v-model.trim="thirdPartyForm.source_name" placeholder="machine_heart" required />
              </label>
              <label class="field">
                <span>平台名</span>
                <input v-model.trim="thirdPartyForm.platform" placeholder="机器之心" required />
              </label>
              <label class="field wide">
                <span>信源地址</span>
                <input v-model.trim="thirdPartyForm.source_url" placeholder="https://www.jiqizhixin.com" required />
              </label>
              <label class="field wide">
                <span>列表容器 XPath</span>
                <input v-model.trim="thirdPartyForm.list_container_xpath" placeholder="/html/body" required />
              </label>
              <label class="field wide">
                <span>文章 URL 正则</span>
                <input v-model.trim="thirdPartyForm.article_url_regex" placeholder="https?://example.com/articles/.*" required />
              </label>
              <label class="field">
                <span>候选数</span>
                <input v-model.number="thirdPartyForm.default_max_candidates" type="number" min="1" />
              </label>
              <label class="field">
                <span>入库数</span>
                <input v-model.number="thirdPartyForm.default_max_items" type="number" min="1" />
              </label>
              <label class="field">
                <span>页数</span>
                <input v-model.number="thirdPartyForm.default_max_pages" type="number" min="1" />
              </label>
              <label class="check-field">
                <input v-model="thirdPartyForm.render_list_page" type="checkbox" />
                <span>渲染列表页</span>
              </label>
              <label class="check-field">
                <input v-model="thirdPartyForm.render_article_page" type="checkbox" />
                <span>渲染文章页</span>
              </label>
              <button class="action-btn" type="submit" :disabled="isSavingSource">
                {{ isSavingSource ? "同步中" : "保存三方源" }}
              </button>
            </form>
            <div class="settings-source-list">
              <div v-for="source in thirdPartySources" :key="source.source_name" class="settings-source-row">
                <strong>{{ source.display_name }}</strong>
                <span>{{ source.source_name }} · {{ source.enabled ? "已启用" : source.latest_status || "未启用" }}</span>
                <small v-if="source.last_error">{{ source.last_error }}</small>
              </div>
            </div>
          </section>
        </div>
        </section>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { api } from "./lib/api";
import type { Source, SystemLog } from "./types";

const navItems = [
  { label: "首页", to: "/" },
  { label: "核心Agent", to: "/core-agent" },
  { label: "Github新星", to: "/github-stars" },
  { label: "大模型", to: "/model-platform" },
  { label: "Agent", to: "/agent-products" },
  { label: "金融AI", to: "/finance-ai" },
  { label: "其他", to: "/others" },
];

const settingsOpen = ref(false);
const settingsError = ref("");
const isRefreshing = ref(false);
const isReranking = ref(false);
const isSavingSource = ref(false);
const systemLogs = ref<SystemLog[]>([]);
const sources = ref<Source[]>([]);
const selectedSourceNames = ref<string[]>([]);
const sourceSelectionInitialized = ref(false);

const githubForm = ref({
  source_name: "",
  repo_url: "",
  is_official: false,
});

const thirdPartyForm = ref({
  source_name: "",
  source_url: "",
  platform: "",
  list_container_xpath: "/html/body",
  article_url_regex: "",
  default_max_candidates: 20,
  default_max_items: 10,
  default_max_pages: 1,
  render_list_page: false,
  render_article_page: false,
  source_tags: [] as string[],
  blocked_url_keywords: ["tag/", "author=", "#", "javascript:"],
});

const settingsSubtitle = computed(() => "系统消息、GitHub源、三方源");

const githubSources = computed(() => sources.value.filter((source) => source.source_type === "github_repository"));
const thirdPartySources = computed(() => sources.value.filter((source) => source.source_type === "third_party_article"));
const enabledSources = computed(() => sources.value.filter((source) => source.enabled));
const allEnabledSourcesSelected = computed(
  () => enabledSources.value.length > 0 && selectedSourceNames.value.length === enabledSources.value.length,
);
const selectedSourceSummary = computed(() => {
  if (!enabledSources.value.length) return "暂无可请求信源";
  if (allEnabledSourcesSelected.value) return "请求全部已启用信源";
  return `请求 ${selectedSourceNames.value.length} 个信源`;
});

async function openSettings() {
  settingsOpen.value = true;
  await Promise.all([reloadSystemLogs(), reloadSources()]);
}

function closeSettings() {
  settingsOpen.value = false;
}

async function reloadSystemLogs() {
  try {
    systemLogs.value = await api.systemLogs({ days: 3, page_size: 100 });
    settingsError.value = "";
  } catch {
    settingsError.value = "无法加载系统消息，请检查系统后端。";
  }
}

async function reloadSources() {
  try {
    sources.value = await api.sources();
    const enabledNames = enabledSources.value.map((source) => source.source_name);
    if (!sourceSelectionInitialized.value) {
      selectedSourceNames.value = enabledNames;
      sourceSelectionInitialized.value = true;
    } else {
      selectedSourceNames.value = selectedSourceNames.value.filter((sourceName) => enabledNames.includes(sourceName));
    }
  } catch {
    settingsError.value = "无法加载信源配置，请检查系统后端。";
  }
}

function toggleAllSources(event: Event) {
  const checked = event.target instanceof HTMLInputElement && event.target.checked;
  selectedSourceNames.value = checked ? enabledSources.value.map((source) => source.source_name) : [];
}

async function saveGithubSource() {
  isSavingSource.value = true;
  settingsError.value = "";
  try {
    const source = await api.createGithubSource(githubForm.value);
    if (!source.enabled) settingsError.value = source.last_error || "GitHub 源同步失败，配置已保留但未启用。";
    githubForm.value = { source_name: "", repo_url: "", is_official: false };
    await Promise.all([reloadSources(), reloadSystemLogs()]);
  } catch (error) {
    settingsError.value = error instanceof Error ? error.message : "GitHub 源保存失败。";
  } finally {
    isSavingSource.value = false;
  }
}

async function saveThirdPartySource() {
  isSavingSource.value = true;
  settingsError.value = "";
  try {
    const source = await api.createThirdPartySource(thirdPartyForm.value);
    if (!source.enabled) settingsError.value = source.last_error || "三方源同步失败，配置已保留但未启用。";
    thirdPartyForm.value = {
      source_name: "",
      source_url: "",
      platform: "",
      list_container_xpath: "/html/body",
      article_url_regex: "",
      default_max_candidates: 20,
      default_max_items: 10,
      default_max_pages: 1,
      render_list_page: false,
      render_article_page: false,
      source_tags: [],
      blocked_url_keywords: ["tag/", "author=", "#", "javascript:"],
    };
    await Promise.all([reloadSources(), reloadSystemLogs()]);
  } catch (error) {
    settingsError.value = error instanceof Error ? error.message : "三方源保存失败。";
  } finally {
    isSavingSource.value = false;
  }
}

async function refreshFromCrawler() {
  if (isRefreshing.value) return;
  isRefreshing.value = true;
  settingsError.value = "";
  try {
    if (!selectedSourceNames.value.length) {
      settingsError.value = "请至少选择一个信源。";
      return;
    }
    await api.runBatch(selectedSourceNames.value);
    await waitForBatch();
    window.dispatchEvent(new CustomEvent("ai-tracing-data-updated"));
  } catch (error) {
    settingsError.value = error instanceof Error ? error.message : "采集失败，请检查系统后端或爬虫后端。";
  } finally {
    isRefreshing.value = false;
    await reloadSystemLogs();
  }
}

async function rerankTop6() {
  if (isReranking.value) return;
  isReranking.value = true;
  settingsError.value = "";
  try {
    await api.rerankTop6();
    window.dispatchEvent(new CustomEvent("ai-tracing-data-updated"));
  } catch (error) {
    settingsError.value = error instanceof Error ? error.message : "排序失败，请检查系统后端或 LLM 配置。";
  } finally {
    isReranking.value = false;
    await reloadSystemLogs();
  }
}

async function waitForBatch() {
  for (let index = 0; index < 800; index += 1) {
    const home = await api.homeToday();
    const status = home.batch?.status;
    if (status === "completed" || status === "degraded" || status === "failed") {
      return;
    }
    await new Promise((resolve) => window.setTimeout(resolve, 3000));
  }
  settingsError.value = "采集仍在运行，请稍后查看结果。";
}

function formatSystemMessage(log: SystemLog) {
  return `${formatBeijingTime(log.log_date)} ${log.message}`;
}

function formatBeijingTime(value: string) {
  const normalizedValue = /(?:Z|[+-]\d{2}:?\d{2})$/.test(value) ? value : `${value}Z`;
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date(normalizedValue));
  const part = (type: string) => parts.find((item) => item.type === type)?.value ?? "";
  return `${part("year")}年${part("month")}月${part("day")}日 ${part("hour")}:${part("minute")}`;
}
</script>
