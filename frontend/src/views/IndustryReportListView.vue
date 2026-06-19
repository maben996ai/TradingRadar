<template>
  <section class="stack">
    <div class="panel">
      <p class="eyebrow">{{ t("industryReport.eyebrow") }}</p>
      <h2>{{ t("industryReport.title") }}</h2>
      <p class="muted">{{ t("industryReport.description") }}</p>

      <form class="research-bar" @submit.prevent="search">
        <input
          v-model="ticker"
          class="research-input"
          :placeholder="t('industryReport.tickerPlaceholder')"
        />
        <button class="filter-btn primary" :disabled="searching || !ticker.trim()" type="submit">
          {{ searching ? t("industryReport.searching") : t("industryReport.search") }}
        </button>
      </form>
      <p v-if="error" class="report-error">{{ error }}</p>
      <p v-if="company" class="muted research-company">
        {{ company.company_name }}（{{ company.ticker }}）·
        {{ t("industryReport.windowPrefix") }} {{ company.lookback_days }} {{ t("industryReport.windowSuffix") }}
      </p>
    </div>

    <div v-if="rows.length" class="panel">
      <div v-for="row in rows" :key="row.source.key" class="research-source">
        <div class="research-source-head">
          <span class="research-source-name">{{ row.source.name }}</span>
          <span v-if="row.status === 'pending'" class="report-status status-pending">
            {{ t("industryReport.statusPending") }}
          </span>
          <span v-else-if="row.status === 'searching'" class="report-status status-generating">
            {{ t("industryReport.statusSearching") }}
          </span>
          <span v-else-if="row.status === 'failed'" class="report-status status-failed">
            {{ t("industryReport.statusFailed") }}
          </span>
          <span v-else class="report-status" :class="row.items.length ? 'status-success' : 'status-empty'">
            {{ row.items.length ? `${row.items.length} ${t("industryReport.hitsSuffix")}` : t("industryReport.noHits") }}
          </span>
        </div>

        <p v-if="row.error" class="muted research-source-note">{{ row.error }}</p>
        <ul v-if="row.items.length" class="report-list">
          <li v-for="item in row.items" :key="item.url" class="report-row">
            <div class="report-row-main">
              <a :href="item.url" target="_blank" rel="noopener noreferrer" class="report-row-title research-link">
                {{ item.title }}
              </a>
              <span class="muted report-row-summary">{{ item.meta }}</span>
            </div>
            <a :href="item.url" target="_blank" rel="noopener noreferrer" class="filter-btn">
              {{ t("industryReport.open") }}
            </a>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import { researchApi } from "../api/industry";
import { useI18n } from "../i18n";
import type { ResearchItem, ResearchResolveResponse, ResearchSource } from "../types";

const { t } = useI18n();

interface SourceRow {
  source: ResearchSource;
  status: "pending" | "searching" | "done" | "failed";
  items: ResearchItem[];
  error: string | null;
}

const ticker = ref("");
const searching = ref(false);
const error = ref("");
const company = ref<ResearchResolveResponse | null>(null);
const sources = ref<ResearchSource[]>([]);
const rows = ref<SourceRow[]>([]);
let searchSeq = 0;

onMounted(async () => {
  try {
    const res = await researchApi.sources();
    sources.value = res.data;
  } catch {
    // 源清单加载失败时检索按钮仍可用，点击时会再报错
  }
});

async function search() {
  const code = ticker.value.trim().toUpperCase();
  if (!code || searching.value) return;
  const seq = ++searchSeq;
  searching.value = true;
  error.value = "";
  company.value = null;
  rows.value = [];

  try {
    if (!sources.value.length) {
      sources.value = (await researchApi.sources()).data;
    }
    const resolved = await researchApi.resolve(code);
    if (seq !== searchSeq) return;
    company.value = resolved.data;
    rows.value = sources.value.map((source) => ({
      source,
      status: "pending" as const,
      items: [],
      error: null,
    }));

    // 逐源检索，实时更新各行状态
    for (const row of rows.value) {
      if (seq !== searchSeq) return;
      row.status = "searching";
      try {
        const res = await researchApi.searchSource(code, row.source.key);
        row.items = res.data.items;
        row.error = res.data.error;
        row.status = "done";
      } catch {
        row.status = "failed";
      }
    }
  } catch (e: unknown) {
    const detail = (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
    error.value = detail || t("industryReport.searchFailed");
  } finally {
    if (seq === searchSeq) searching.value = false;
  }
}
</script>
