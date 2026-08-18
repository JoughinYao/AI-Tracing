<template>
  <article class="row-item" :class="{ 'has-index': displayIndex }">
    <div v-if="displayIndex" class="row-index">{{ displayIndex }}</div>
    <div class="row-main">
      <div class="row-title-line">
        <a :href="item.original_url || item.source_url || '#'" target="_blank" rel="noreferrer" class="row-title">
          {{ item.title }}
        </a>
        <span class="pill" :data-kind="item.event_type || 'other'">{{ item.event_type || "other" }}</span>
      </div>
      <p class="row-summary">{{ item.summary || "摘要待生成" }}</p>
      <div v-if="isTrendingItem && (stars !== null || starsToday !== null)" class="repo-metrics" aria-label="GitHub 仓库指标">
        <span v-if="stars !== null">Stars {{ formatCount(stars) }}</span>
        <span v-if="starsToday !== null" class="repo-stars-today">今日 +{{ formatCount(starsToday) }}</span>
      </div>
      <div v-if="primaryImageUrl" class="row-media">
        <img :src="primaryImageUrl" :alt="primaryImageAlt" loading="lazy" @error="markImageBroken(primaryImageUrl)" />
        <span v-if="primaryImageCaption">{{ primaryImageCaption }}</span>
      </div>
      <div v-if="hasBriefingDetails" class="briefing-columns">
        <div class="briefing-column primary">
          <div v-if="item.key_points.length" class="insight-block">
            <div class="insight-label">关键事实</div>
            <ul class="insight-list">
              <li v-for="point in item.key_points.slice(0, 4)" :key="point">{{ point }}</li>
            </ul>
          </div>
          <div v-if="valueReason" class="insight-grid">
            <section v-if="valueReason" class="insight-cell">
              <div class="insight-label">价值解读</div>
              <p>{{ valueReason }}</p>
            </section>
          </div>
        </div>
        <div class="briefing-column secondary">
          <div v-if="item.impact_scope.length || item.risk_or_limitations.length" class="insight-grid compact">
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
      <section v-if="relatedThirdParty.length" class="community-review">
        <div class="insight-label">三方评测</div>
        <div class="community-review-list">
          <a
            v-for="comment in relatedThirdParty"
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
      <div class="row-meta">
        <span>{{ item.source_name }}</span>
        <span v-if="item.published_at">{{ formatDate(item.published_at) }}</span>
        <span v-if="item.author">{{ item.author }}</span>
        <span v-if="item.content_depth">深度 {{ item.content_depth }}</span>
      </div>
    </div>
    <div class="row-tags">
      <span v-for="tag in item.tags.slice(0, 4)" :key="tag" class="tag">{{ tag }}</span>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { Item } from "../types";

import { computed, ref } from "vue";

const props = defineProps<{ item: Item; index?: number }>();
const brokenImageUrls = ref(new Set<string>());

const isTrendingItem = computed(() => props.item.source_name === "github_trending");
const displayIndex = computed(() => (typeof props.index === "number" ? String(props.index).padStart(2, "0") : ""));
const stars = computed(() => numberFromMetadata("stars"));
const starsToday = computed(() => numberFromMetadata("stars_today"));
const valueReason = computed(() => stringFromRecord(props.item.value_interpretation, "reason"));
const relatedThirdParty = computed(() => {
  if (props.item.related_third_party.length) {
    return props.item.related_third_party.map((item, index) => ({ ...item, key: `${item.source_name}-${item.original_url || index}` }));
  }
  return props.item.comments.map((comment) => ({
    ...comment,
    key: String(comment.id),
    source_display_name: comment.source_name,
    relation_confidence: null,
    relation_reason: null,
    author: null,
  }));
});
const hasBriefingDetails = computed(() =>
  Boolean(
    props.item.key_points.length ||
      valueReason.value ||
      props.item.impact_scope.length ||
      props.item.risk_or_limitations.length,
  ),
);
const primaryImageUrl = computed(() => {
  const url = stringFromRecord(props.item.primary_image, "url");
  return url && !brokenImageUrls.value.has(url) ? url : "";
});
const primaryImageAlt = computed(() => stringFromRecord(props.item.primary_image, "alt") || props.item.title);
const primaryImageCaption = computed(() => stringFromRecord(props.item.primary_image, "caption"));

function numberFromMetadata(key: string): number | null {
  const value = props.item.metadata[key];
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() !== "" && Number.isFinite(Number(value))) return Number(value);
  return null;
}

function formatCount(value: number) {
  return new Intl.NumberFormat("en-US").format(value);
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function relationLabel(value: string) {
  const labels: Record<string, string> = {
    commentary: "评论",
    benchmark: "评测",
    tutorial: "教程",
  };
  return labels[value] || value || "补充";
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
</script>
