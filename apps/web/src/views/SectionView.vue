<template>
  <section class="stack">
    <div v-if="!hideHeader" class="hero-band compact">
      <div class="hero-copy">
        <div class="eyebrow">分类</div>
        <h1>{{ title }}</h1>
        <p>{{ description }}</p>
      </div>
    </div>

    <section class="panel">
      <div class="filter-bar">
        <label class="field">
          <span>日期</span>
          <input v-model="date" type="date" />
        </label>
        <label class="field">
          <span>分页</span>
          <select v-model.number="pageSize">
            <option :value="10">10</option>
            <option :value="20">20</option>
            <option :value="50">50</option>
          </select>
        </label>
        <button class="search-icon-btn" type="button" aria-label="查询" title="查询" @click="loadCurrentPage">
          <img src="/icons/search.svg" alt="" aria-hidden="true" />
        </button>
      </div>

      <div v-if="page.items.length" class="item-list">
        <ItemRow
          v-for="(item, index) in page.items"
          :key="item.external_id"
          :item="item"
          :index="(page.page - 1) * page.page_size + index + 1"
        />
      </div>
      <div v-else-if="errorMessage" class="empty-state error-state">{{ errorMessage }}</div>
      <div v-else class="empty-state">暂无内容</div>

      <div class="pager">
        <button class="nav-btn" :disabled="page.page <= 1" @click="goPrev">上一页</button>
        <span>{{ page.page }} / {{ page.total_pages }}</span>
        <button class="nav-btn" :disabled="page.page >= page.total_pages" @click="goNext">下一页</button>
      </div>
    </section>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import ItemRow from "../components/ItemRow.vue";
import { api } from "../lib/api";
import type { ItemPage } from "../types";

const props = defineProps<{ section: string; title: string; description: string; hideHeader?: boolean }>();
const date = ref(new Date().toISOString().slice(0, 10));
const pageSize = ref(20);
const page = ref<ItemPage>({ items: [], page: 1, page_size: 20, total: 0, total_pages: 1 });
const errorMessage = ref("");

async function loadPage(nextPage = page.value.page) {
  try {
    page.value = await api.items({ section: props.section, date: date.value, page: nextPage, page_size: pageSize.value });
    errorMessage.value = "";
  } catch {
    page.value = { items: [], page: 1, page_size: pageSize.value, total: 0, total_pages: 1 };
    errorMessage.value = "无法加载真实数据，请检查系统后端。";
  }
}

function goPrev() {
  if (page.value.page > 1) loadPage(page.value.page - 1);
}

function goNext() {
  if (page.value.page < page.value.total_pages) loadPage(page.value.page + 1);
}

function loadCurrentPage() {
  loadPage(page.value.page);
}

watch([date, pageSize, () => props.section], () => loadPage(1));

onMounted(() => loadPage(1));
</script>
