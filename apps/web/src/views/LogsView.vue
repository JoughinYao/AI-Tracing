<template>
  <section class="stack">
    <div class="hero-band compact">
      <div class="hero-copy">
        <div class="eyebrow">日志</div>
        <h1>系统日志</h1>
        <p>查看采集大事件、信源调用、失败重试和错误记录。</p>
      </div>
    </div>

    <section class="panel">
      <div class="filter-bar">
        <label class="field">
          <span>日期</span>
          <input v-model="date" type="date" />
        </label>
        <button class="action-btn primary" @click="loadLogs">查询</button>
      </div>
      <div class="log-table">
        <div class="log-head">
          <span>时间</span>
          <span>级别</span>
          <span>信源</span>
          <span>动作</span>
          <span>消息</span>
        </div>
        <div v-for="log in logs" :key="log.id" class="log-row">
          <span>{{ formatDate(log.log_date) }}</span>
          <span>{{ log.level }}</span>
          <span>{{ log.source_name || "-" }}</span>
          <span>{{ log.action }}</span>
          <span>{{ log.message }}</span>
        </div>
      </div>
      <div v-if="errorMessage" class="empty-state error-state">{{ errorMessage }}</div>
      <div v-if="!logs.length" class="empty-state">暂无日志</div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { api } from "../lib/api";
import type { SystemLog } from "../types";

const date = ref(new Date().toISOString().slice(0, 10));
const logs = ref<SystemLog[]>([]);
const errorMessage = ref("");

async function loadLogs() {
  try {
    logs.value = await api.systemLogs(date.value);
    errorMessage.value = "";
  } catch {
    logs.value = [];
    errorMessage.value = "无法加载真实日志，请检查系统后端。";
  }
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

onMounted(loadLogs);
</script>
