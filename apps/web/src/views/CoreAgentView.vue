<template>
  <section class="core-metrics-page">
    <header class="core-metrics-header">
      <div>
        <div class="rotor-kicker">核心Agent</div>
        <h1>Agent 指标趋势</h1>
      </div>
      <div class="range-control" aria-label="时间范围">
        <button
          v-for="option in rangeOptions"
          :key="option.value"
          type="button"
          :class="{ active: selectedRange === option.value }"
          @click="setRange(option.value)"
        >
          {{ option.label }}
        </button>
      </div>
    </header>

    <p v-if="errorMessage" class="error-text">{{ errorMessage }}</p>

    <section class="metrics-chart-grid">
      <article v-for="chart in charts" :key="chart.key" class="metric-chart-panel">
        <div class="chart-heading">
          <strong>{{ chart.label }}</strong>
        </div>

        <div class="chart-legend" aria-label="Agent 图例">
          <span v-for="agent in agentLines" :key="agent.source_name" class="legend-item">
            <i
              class="legend-sample"
              :style="{
                '--legend-color': agent.color,
                '--legend-style': agent.lineStyle,
              }"
            />
            <span>{{ agent.display_name }}</span>
          </span>
        </div>

        <div class="line-chart-frame">
          <svg class="line-chart" viewBox="0 0 860 320" role="img" :aria-label="`${chart.label} 折线图`">
            <g class="grid-lines">
              <line v-for="tick in yTicks" :key="tick" x1="54" :y1="tick" x2="704" :y2="tick" />
            </g>
            <g class="axis-labels">
              <text x="54" y="24">{{ formatCompact(chartMax(chart.key)) }}</text>
              <text x="54" y="294">{{ formatCompact(chartMin(chart.key)) }}</text>
            </g>
            <path
              v-for="agent in agentLines"
              :key="`${chart.key}-${agent.source_name}`"
              class="metric-line"
              :d="linePath(agent.source_name, chart.key)"
              :stroke="agent.color"
              :style="{
                '--line-length': lineLength(agent.source_name, chart.key),
                '--line-dash': agent.dash,
              }"
            />
            <g v-for="agent in agentLines" :key="`dots-${chart.key}-${agent.source_name}`">
              <circle
                v-for="point in chartPoints(agent.source_name, chart.key)"
                :key="`${agent.source_name}-${chart.key}-${point.x}-${point.y}`"
                class="metric-dot"
                :cx="point.x"
                :cy="point.y"
                r="3.8"
                :fill="agent.color"
              />
            </g>
            <g
              v-for="label in lastValueLabels(chart.key)"
              :key="`${chart.key}-${label.sourceName}-label`"
              class="last-value-label"
            >
              <line
                class="last-value-connector"
                :x1="label.connectorStart"
                :y1="label.pointY"
                :x2="label.connectorEnd"
                :y2="label.y"
                :stroke="label.color"
              />
              <text :x="label.x" :y="label.y" :fill="label.color">
                {{ label.displayName }} · {{ label.text }}
              </text>
            </g>
          </svg>
        </div>
      </article>
    </section>

    <SectionView section="core-agent" title="核心Agent" description="按日期筛选核心 Agent 更新。" hide-header />
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import SectionView from "./SectionView.vue";
import { api } from "../lib/api";
import type { CoreAgentMetricsResponse, MetricsPoint } from "../types";

type RangeValue = "all" | "week" | "month";
type MetricKey = "stars" | "forks" | "subscribers" | "open_issues";

const rangeOptions: { label: string; value: RangeValue }[] = [
  { label: "记录以来", value: "all" },
  { label: "近一周", value: "week" },
  { label: "近一个月", value: "month" },
];

const charts: { key: MetricKey; label: string }[] = [
  { key: "stars", label: "Stars" },
  { key: "forks", label: "Forks" },
  { key: "subscribers", label: "Subscribers" },
  { key: "open_issues", label: "Open issues" },
];

const palette = ["#10a37f", "#2563eb", "#8b5cf6", "#f97316"];
const dashPatterns = ["0", "10 7", "2 7", "16 6 2 6"];
const lineStyles = ["solid", "dashed", "dotted", "double"];
const selectedRange = ref<RangeValue>("all");
const metrics = ref<CoreAgentMetricsResponse>({ range: "all", agents: [] });
const errorMessage = ref("");

const agentLines = computed(() =>
  metrics.value.agents.map((agent, index) => ({
    ...agent,
    color: palette[index % palette.length],
    dash: dashPatterns[index % dashPatterns.length],
    lineStyle: lineStyles[index % lineStyles.length],
  })),
);

const yTicks = [52, 112, 172, 232, 292];

async function setRange(range: RangeValue) {
  selectedRange.value = range;
  await loadMetrics();
}

async function loadMetrics() {
  try {
    metrics.value = await api.coreAgentMetrics({ range: selectedRange.value });
    errorMessage.value = "";
  } catch {
    metrics.value = { range: selectedRange.value, agents: [] };
    errorMessage.value = "无法加载核心 Agent 指标。";
  }
}

function metricValue(point: MetricsPoint, key: MetricKey) {
  const value = point[key];
  return typeof value === "number" ? value : null;
}

function allValues(key: MetricKey) {
  return metrics.value.agents.flatMap((agent) =>
    agent.series.map((point) => metricValue(point, key)).filter((value): value is number => value !== null),
  );
}

function chartMin(key: MetricKey) {
  const values = allValues(key);
  if (!values.length) return 0;
  return Math.min(...values);
}

function chartMax(key: MetricKey) {
  const values = allValues(key);
  if (!values.length) return 1;
  const min = Math.min(...values);
  const max = Math.max(...values);
  return max === min ? max + 1 : max;
}

function chartPoints(sourceName: string, key: MetricKey) {
  const agent = metrics.value.agents.find((item) => item.source_name === sourceName);
  const series = agent?.series || [];
  const values = series.map((point) => metricValue(point, key));
  const min = chartMin(key);
  const max = chartMax(key);
  const range = Math.max(max - min, 1);
  const left = 64;
  const right = 704;
  const top = 42;
  const bottom = 282;
  const width = right - left;

  return values
    .map((value, index) => {
      if (value === null) return null;
      const x = series.length <= 1 ? left + width / 2 : left + (width * index) / (series.length - 1);
      const y = bottom - ((value - min) / range) * (bottom - top);
      return { x, y, value, snapshot_at: series[index].snapshot_at };
    })
    .filter((point): point is { x: number; y: number; value: number; snapshot_at: string } => point !== null);
}

function lastValueLabels(key: MetricKey) {
  const labels = agentLines.value
    .map((agent) => {
      const points = chartPoints(agent.source_name, key);
      const point = points.at(-1);
      if (!point) return null;
      return {
        sourceName: agent.source_name,
        displayName: agent.display_name,
        text: formatCompact(point.value),
        color: agent.color,
        x: 722,
        y: point.y,
        pointY: point.y,
        connectorStart: 708,
        connectorEnd: 716,
      };
    })
    .filter(
      (
        label,
      ): label is {
        sourceName: string;
        displayName: string;
        text: string;
        color: string;
        x: number;
        y: number;
        pointY: number;
        connectorStart: number;
        connectorEnd: number;
      } => label !== null,
    );

  labels.sort((a, b) => a.y - b.y);
  for (let index = 1; index < labels.length; index += 1) {
    if (labels[index].y - labels[index - 1].y < 26) {
      labels[index].y = labels[index - 1].y + 26;
    }
  }
  for (let index = labels.length - 2; index >= 0; index -= 1) {
    if (labels[index + 1].y > 286 && labels[index + 1].y - labels[index].y < 26) {
      labels[index].y = labels[index + 1].y - 26;
    }
  }

  return labels.map((label) => ({ ...label, y: Math.max(34, Math.min(286, label.y)) }));
}

function linePath(sourceName: string, key: MetricKey) {
  const points = chartPoints(sourceName, key);
  if (!points.length) return "";
  if (points.length === 1) {
    const point = points[0];
    return `M ${point.x - 6} ${point.y} L ${point.x + 6} ${point.y}`;
  }
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
}

function lineLength(sourceName: string, key: MetricKey) {
  const points = chartPoints(sourceName, key);
  if (points.length < 2) return 12;
  return points.slice(1).reduce((sum, point, index) => {
    const prev = points[index];
    return sum + Math.hypot(point.x - prev.x, point.y - prev.y);
  }, 0);
}

function formatCompact(value: number) {
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

onMounted(loadMetrics);
</script>
