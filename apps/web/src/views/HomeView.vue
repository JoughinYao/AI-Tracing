<template>
  <section class="home-page">
    <div class="home-header">
      <div>
        <h1>今日TOP6</h1>
      </div>
    </div>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <section v-if="home" class="relation-update-strip" aria-label="旧内容今日更新">
      <div class="relation-update-head">社区更新</div>
      <template v-if="home.relation_updates.length">
        <a
          v-for="update in home.relation_updates"
          :key="update.official_internal_id"
          class="relation-update-row"
          href="#"
          @click.prevent
        >
          <strong>{{ update.official_title }}</strong>
          <span>
            新增 {{ update.relation_update_count_today }} 条三方内容
            <template v-if="update.latest_relation_source_display_name">
              ，最新来自 {{ update.latest_relation_source_display_name }}
            </template>
          </span>
        </a>
      </template>
      <div v-else class="relation-update-empty">今天暂无旧内容新增社区反馈</div>
    </section>

    <div v-if="home?.top6.length" class="home-news-list" aria-live="polite">
      <article v-for="(item, index) in home.top6" :key="item.external_id" class="home-news-item">
        <div class="home-news-heading">
          <div class="home-news-index">{{ String(index + 1).padStart(2, "0") }}</div>
          <a :href="item.original_url || item.source_url || '#'" target="_blank" rel="noreferrer" class="home-news-title">
            {{ item.title }}
          </a>
        </div>
        <div class="home-news-body">
          <p class="home-news-summary">{{ item.summary || "摘要待生成" }}</p>
          <div v-if="isTrendingItem(item) && (metricValue(item, 'stars') !== null || metricValue(item, 'stars_today') !== null)" class="home-repo-metrics" aria-label="GitHub 仓库指标">
            <span v-if="metricValue(item, 'stars') !== null">Stars {{ formatCount(metricValue(item, "stars")!) }}</span>
            <span v-if="metricValue(item, 'stars_today') !== null" class="home-repo-stars-today">今日 +{{ formatCount(metricValue(item, "stars_today")!) }}</span>
          </div>
          <div v-if="primaryImageUrl(item)" class="home-news-media">
            <img :src="primaryImageUrl(item)" :alt="primaryImageAlt(item)" loading="lazy" @error="markImageBroken(primaryImageUrl(item))" />
            <span v-if="primaryImageCaption(item)">{{ primaryImageCaption(item) }}</span>
          </div>
          <div v-if="hasBriefingDetails(item)" class="briefing-columns">
            <div class="briefing-column primary">
              <div v-if="item.key_points.length" class="home-insight-block">
                <div class="insight-label">关键事实</div>
                <ul class="insight-list">
                  <li v-for="point in item.key_points.slice(0, 4)" :key="point">{{ point }}</li>
                </ul>
              </div>
              <div v-if="valueReason(item)" class="home-insight-grid">
                <section v-if="valueReason(item)" class="insight-cell">
                  <div class="insight-label">价值解读</div>
                  <p>{{ valueReason(item) }}</p>
                </section>
              </div>
            </div>
            <div class="briefing-column secondary">
              <div v-if="item.impact_scope.length || item.risk_or_limitations.length" class="home-insight-grid compact">
                <section v-if="item.impact_scope.length" class="insight-cell">
                  <div class="insight-label">影响范围</div>
                  <p>{{ item.impact_scope.slice(0, 3).join(" / ") }}</p>
                </section>
                <section v-if="item.risk_or_limitations.length" class="insight-cell">
                  <div class="insight-label">风险限制</div>
                  <p>{{ item.risk_or_limitations.slice(0, 3).join(" / ") }}</p>
                </section>
              </div>
            </div>
          </div>
          <section v-if="relatedThirdParty(item).length" class="community-review">
            <div class="insight-label">三方评测</div>
            <div class="community-review-list">
              <a
                v-for="comment in relatedThirdParty(item)"
                :key="comment.key"
                class="community-review-row"
                :href="comment.original_url || '#'"
                target="_blank"
                rel="noreferrer"
              >
                <span class="community-review-source">{{ comment.source_display_name }} · {{ relationLabel(comment.relation_type) }}</span>
                <strong>{{ comment.title }}</strong>
                <p v-if="comment.summary">{{ comment.summary }}</p>
              </a>
            </div>
          </section>
          <dl class="home-news-details">
            <div>
              <dt>发布时间</dt>
              <dd>{{ formatBeijingTime(item.published_at) }}</dd>
            </div>
            <div>
              <dt>作者</dt>
              <dd>{{ item.author || "未知" }}</dd>
            </div>
            <div>
              <dt>信源</dt>
              <dd>{{ item.source_name }}</dd>
            </div>
            <div>
              <dt>原文链接</dt>
              <dd>
                <a :href="item.original_url || item.source_url || '#'" target="_blank" rel="noreferrer">
                  {{ compactUrl(item.original_url || item.source_url) }}
                </a>
              </dd>
            </div>
          </dl>
          <div class="home-news-tags">
            <span v-if="item.event_type" class="soft-token">{{ item.event_type }}</span>
            <span v-for="tag in item.tags.slice(0, 5)" :key="tag" class="soft-token">{{ tag }}</span>
          </div>
        </div>
      </article>
    </div>

    <div v-else class="empty-state home-empty">今日暂无消息</div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { api } from "../lib/api";
import type { HomeTodayResponse } from "../types";

const home = ref<HomeTodayResponse | null>(null);
const errorMessage = ref("");
const brokenImageUrls = ref(new Set<string>());

async function reload() {
  try {
    home.value = await api.homeToday();
    errorMessage.value = "";
  } catch {
    errorMessage.value = "无法连接系统后端，请检查 API 服务。";
  }
}

function formatBeijingTime(value?: string | null) {
  if (!value) return "未知";
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(value));
}

function compactUrl(value?: string | null) {
  if (!value) return "未提供";
  try {
    const url = new URL(value);
    return `${url.hostname}${url.pathname}`;
  } catch {
    return value;
  }
}

function isTrendingItem(item: HomeTodayResponse["top6"][number]) {
  return item.source_name === "github_trending";
}

function metricValue(item: HomeTodayResponse["top6"][number], key: string): number | null {
  const value = item.metadata[key];
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) return Number(value);
  return null;
}

function formatCount(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function valueReason(item: HomeTodayResponse["top6"][number]) {
  return stringFromRecord(item.value_interpretation, "reason");
}

function hasBriefingDetails(item: HomeTodayResponse["top6"][number]) {
  return Boolean(
    item.key_points.length ||
      valueReason(item) ||
      item.impact_scope.length ||
      item.risk_or_limitations.length,
  );
}

function primaryImageUrl(item: HomeTodayResponse["top6"][number]) {
  const url = stringFromRecord(item.primary_image, "url");
  return url && !brokenImageUrls.value.has(url) ? url : "";
}

function primaryImageAlt(item: HomeTodayResponse["top6"][number]) {
  return stringFromRecord(item.primary_image, "alt") || item.title;
}

function primaryImageCaption(item: HomeTodayResponse["top6"][number]) {
  return stringFromRecord(item.primary_image, "caption");
}

function stringFromRecord(record: Record<string, unknown> | null | undefined, key: string): string {
  if (!record) return "";
  const value = record[key];
  return typeof value === "string" ? value : "";
}

function markImageBroken(url: string) {
  if (!url) return;
  brokenImageUrls.value = new Set([...brokenImageUrls.value, url]);
}

function handleGlobalRefresh() {
  reload();
}

function relationLabel(value: string) {
  const labels: Record<string, string> = {
    commentary: "评论",
    benchmark: "评测",
    tutorial: "教程",
  };
  return labels[value] || value || "补充";
}

function relatedThirdParty(item: HomeTodayResponse["top6"][number]) {
  if (item.related_third_party.length) {
    return item.related_third_party.map((related, index) => ({
      ...related,
      key: `${related.source_name}-${related.original_url || index}`,
    }));
  }
  return item.comments.map((comment) => ({
    ...comment,
    key: String(comment.id),
    source_display_name: comment.source_name,
    relation_confidence: null,
    relation_reason: null,
    author: null,
  }));
}

onMounted(() => {
  reload();
  window.addEventListener("ai-tracing-data-updated", handleGlobalRefresh);
});

onUnmounted(() => {
  window.removeEventListener("ai-tracing-data-updated", handleGlobalRefresh);
});
</script>
