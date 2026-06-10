<template>
  <section class="panel stock-analysis">
    <p class="eyebrow">{{ t("stockAnalysis.eyebrow") }}</p>
    <h2>{{ t("stockAnalysis.title") }}</h2>
    <p class="muted">{{ t("stockAnalysis.description") }}</p>

    <div class="sa-form">
      <input
        v-model="ticker"
        class="sa-input"
        :placeholder="t('stockAnalysis.tickerPlaceholder')"
        @keyup.enter="onDownload"
      />
      <button class="sa-btn" :disabled="loading" @click="onDownload">
        {{ loading ? t("stockAnalysis.downloading") : t("stockAnalysis.downloadBtn") }}
      </button>
    </div>

    <div v-if="sources.length" class="sa-sources">
      <span class="sa-sources-label">{{ t("stockAnalysis.sourcesLabel") }}</span>
      <label v-for="s in sources" :key="s.name" class="sa-source-chip">
        <input v-model="selected" type="checkbox" :value="s.name" />
        <span>{{ sourceLabel(s.name) }}</span>
      </label>
    </div>

    <p v-if="error" class="sa-error">{{ error }}</p>

    <div v-if="results.length" class="sa-results">
      <div v-for="r in results" :key="r.source" class="sa-result-block">
        <div class="sa-result-head">
          <span class="sa-result-name">{{ sourceLabel(r.source) }}</span>
          <span v-if="r.skipped" class="sa-tag sa-tag-skip">{{ t("stockAnalysis.skipped") }}</span>
          <span v-else class="sa-tag">{{ r.artifacts.length }} {{ t("stockAnalysis.files") }}</span>
        </div>
        <p v-if="r.message" class="muted sa-result-msg">{{ r.message }}</p>
        <table v-if="r.artifacts.length" class="sa-table">
          <thead>
            <tr>
              <th>{{ t("stockAnalysis.colType") }}</th>
              <th>{{ t("stockAnalysis.colTitle") }}</th>
              <th>{{ t("stockAnalysis.colPeriod") }}</th>
              <th>{{ t("stockAnalysis.colSize") }}</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(a, i) in r.artifacts" :key="i">
              <td>{{ a.doc_type }}</td>
              <td>{{ a.title }}</td>
              <td>{{ a.period ?? "—" }}</td>
              <td>{{ fmtSize(a.bytes_written) }}</td>
              <td>
                <button class="sa-link" :disabled="savingPath === a.file_path" @click="onSave(a.file_path)">
                  {{ savingPath === a.file_path ? "…" : t("stockAnalysis.downloadFile") }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";

import { fundamentalsApi } from "../api/fundamentals";
import { useI18n } from "../i18n";
import type { FundamentalsSource, FundamentalsSourceResult } from "../types";

const { t } = useI18n();

const SOURCE_LABELS: Record<string, string> = {
  sec_edgar: "SEC EDGAR",
  fmp: "FMP",
  finnhub: "Finnhub",
  quartr: "Quartr",
};

// 默认仅勾选已配置 key 的数据源（Finnhub/Quartr 需另配 key，默认不勾）
const DEFAULT_SELECTED = ["sec_edgar", "fmp"];

const ticker = ref("");
const sources = ref<FundamentalsSource[]>([]);
const selected = ref<string[]>([]);
const results = ref<FundamentalsSourceResult[]>([]);
const loading = ref(false);
const savingPath = ref<string | null>(null);
const error = ref("");

function sourceLabel(name: string): string {
  return SOURCE_LABELS[name] ?? name;
}

function fmtSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function basename(p: string): string {
  return p.split(/[\\/]/).pop() ?? "download";
}

onMounted(async () => {
  try {
    const { data } = await fundamentalsApi.sources();
    sources.value = data;
    selected.value = data.map((s) => s.name).filter((n) => DEFAULT_SELECTED.includes(n));
  } catch {
    // 信源列表拉取失败不阻断输入
  }
});

async function onDownload() {
  const code = ticker.value.trim().toUpperCase();
  if (!code) {
    error.value = t("stockAnalysis.noTicker");
    return;
  }
  loading.value = true;
  error.value = "";
  results.value = [];
  try {
    const { data } = await fundamentalsApi.download(code, selected.value);
    results.value = data.results;
  } catch {
    error.value = t("stockAnalysis.error");
  } finally {
    loading.value = false;
  }
}

async function onSave(path: string) {
  savingPath.value = path;
  try {
    await fundamentalsApi.downloadFile(path, basename(path));
  } catch {
    error.value = t("stockAnalysis.error");
  } finally {
    savingPath.value = null;
  }
}
</script>

<style scoped>
.stock-analysis h2 {
  margin: 0.2rem 0 0.4rem;
}
.sa-form {
  display: flex;
  gap: 0.6rem;
  margin: 1rem 0 0.8rem;
}
.sa-input {
  flex: 0 0 240px;
  padding: 0.55rem 0.8rem;
  border: 1px solid var(--border, #d0d7de);
  border-radius: 8px;
  font-size: 0.95rem;
  text-transform: uppercase;
}
.sa-btn {
  padding: 0.55rem 1.2rem;
  border: none;
  border-radius: 8px;
  background: var(--accent, #2563eb);
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}
.sa-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.sa-sources {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.6rem;
  margin-bottom: 0.6rem;
}
.sa-sources-label {
  color: var(--muted, #6b7280);
  font-size: 0.85rem;
}
.sa-source-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
  padding: 0.25rem 0.6rem;
  border: 1px solid var(--border, #d0d7de);
  border-radius: 999px;
  font-size: 0.85rem;
  cursor: pointer;
}
.sa-error {
  color: #dc2626;
  margin: 0.4rem 0;
}
.sa-results {
  margin-top: 1rem;
  display: flex;
  flex-direction: column;
  gap: 1.2rem;
}
.sa-result-head {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  margin-bottom: 0.3rem;
}
.sa-result-name {
  font-weight: 700;
}
.sa-tag {
  font-size: 0.75rem;
  padding: 0.1rem 0.5rem;
  border-radius: 999px;
  background: rgba(37, 99, 235, 0.12);
  color: var(--accent, #2563eb);
}
.sa-tag-skip {
  background: rgba(107, 114, 128, 0.15);
  color: #6b7280;
}
.sa-result-msg {
  margin: 0.2rem 0 0.4rem;
  font-size: 0.85rem;
}
.sa-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.88rem;
}
.sa-table th,
.sa-table td {
  text-align: left;
  padding: 0.45rem 0.6rem;
  border-bottom: 1px solid var(--border, #eaecef);
}
.sa-table th {
  color: var(--muted, #6b7280);
  font-weight: 600;
}
.sa-link {
  border: none;
  background: none;
  color: var(--accent, #2563eb);
  cursor: pointer;
  font-weight: 600;
  padding: 0;
}
.sa-link:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
