<template>
  <section class="stack">
    <div class="hero">
      <div>
        <p class="eyebrow">{{ t("macro.eyebrow") }}</p>
        <h2>{{ t("macro.title") }}</h2>
      </div>
    </div>

    <p v-if="loading" class="muted feed-state">{{ t("macro.loading") }}</p>
    <p v-else-if="error" class="muted feed-state">{{ t("macro.error") }}</p>
    <p v-else-if="!visibleIndicators.length" class="muted feed-state">{{ t("macro.empty") }}</p>

    <div v-else class="panel">
      <div class="macro-grid">
        <article v-for="ind in visibleIndicators" :key="ind.key" class="macro-card">
          <div class="macro-card-head">
            <div class="macro-card-titles">
              <span class="macro-card-name">{{ ind.name }}</span>
              <span class="macro-badge macro-badge-cat">
                <span class="macro-section-dot" :class="`macro-dot-${ind.category}`"></span>
                {{ categoryLabel(ind.category) }}
              </span>
            </div>
            <span class="macro-badge" :class="`macro-judge-${ind.judgment}`">
              {{ t(`macro.judge_${ind.judgment}`) }}
            </span>
          </div>

          <div class="macro-card-values">
            <span class="macro-latest">{{ formatNumber(ind.latest, ind.decimals) }}<small>{{ ind.unit_label }}</small></span>
            <span v-if="ind.change_abs !== null" class="macro-change" :class="`macro-change-${ind.judgment}`">
              {{ ind.change_abs >= 0 ? "▲" : "▼" }}
              {{ formatNumber(Math.abs(ind.change_abs), ind.decimals) }}
              <template v-if="ind.change_pct !== null">({{ formatNumber(Math.abs(ind.change_pct), 1) }}%)</template>
            </span>
          </div>

          <div class="macro-card-meta">
            <span>{{ t("macro.previous") }} {{ ind.previous !== null ? formatNumber(ind.previous, ind.decimals) + ind.unit_label : "—" }}</span>
            <span>{{ t("macro.updated") }} {{ ind.updated_at }}</span>
            <span>{{ t("macro.source") }} {{ ind.source }}</span>
          </div>

          <div class="macro-range">
            <button
              v-for="r in RANGES"
              :key="r"
              class="filter-btn"
              :class="{ active: rangeOf(ind.key) === r }"
              @click="setRange(ind.key, r)"
            >
              {{ t(`macro.range_${r}`) }}
            </button>
          </div>

          <MacroLineChart
            :points="slicedSeries(ind)"
            :judgment="ind.judgment"
            :decimals="ind.decimals"
            :unit-label="ind.unit_label"
            :empty-text="t('macro.empty')"
            :high="ind.high"
            :low="ind.low"
          />

          <p class="macro-reason">{{ ind.reason }}</p>

          <div v-if="ind.high !== null || ind.low !== null" class="macro-threshold">
            <div class="macro-threshold-head">
              <span class="macro-threshold-title">{{ t("macro.warnRange") }}</span>
              <span class="macro-threshold-range">
                <template v-if="ind.low !== null">{{ t("macro.warnLow") }} {{ formatNumber(ind.low, ind.decimals) }}{{ ind.unit_label }}</template>
                <template v-if="ind.low !== null && ind.high !== null"> · </template>
                <template v-if="ind.high !== null">{{ t("macro.warnHigh") }} {{ formatNumber(ind.high, ind.decimals) }}{{ ind.unit_label }}</template>
              </span>
              <span class="macro-zone" :class="`macro-zone-${ind.zone}`">{{ t(`macro.zone_${ind.zone}`) }}</span>
            </div>
            <p v-if="ind.high_note" class="macro-threshold-note" :class="{ active: ind.zone === 'high' }">{{ ind.high_note }}</p>
            <p v-if="ind.low_note" class="macro-threshold-note" :class="{ active: ind.zone === 'low' }">{{ ind.low_note }}</p>
          </div>

          <div v-if="ind.forecast !== null" class="macro-forecast">
            <span class="macro-forecast-label">{{ t("macro.forecast") }}</span>
            <span class="macro-forecast-val">{{ formatNumber(ind.forecast, ind.decimals) }}{{ ind.unit_label }}</span>
            <span class="macro-forecast-meta">{{ ind.forecast_label }} · {{ ind.forecast_source }}</span>
          </div>

          <p class="macro-explain muted">{{ ind.explanation }}</p>
        </article>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { useRoute } from "vue-router";

import { macroApi } from "../api/macro";
import MacroLineChart from "../components/macro/MacroLineChart.vue";
import { useI18n } from "../i18n";
import type { MacroCategory, MacroIndicator } from "../types";

const { t } = useI18n();
const route = useRoute();

const RANGES = ["3m", "6m", "1y", "3y"] as const;
type Range = (typeof RANGES)[number];
const RANGE_DAYS: Record<Range, number> = { "3m": 90, "6m": 180, "1y": 365, "3y": 1095 };

const indicators = ref<MacroIndicator[]>([]);
const loading = ref(true);
const error = ref(false);

// 每个指标独立的时间范围（默认 1Y）
const ranges = reactive<Record<string, Range>>({});
function rangeOf(key: string): Range {
  return ranges[key] ?? "1y";
}
function setRange(key: string, r: Range) {
  ranges[key] = r;
}

const CATEGORY_ORDER: MacroCategory[] = [
  "rates",
  "inflation",
  "growth",
  "employment",
  "liquidity",
  "risk",
];

const categoryFilter = computed(() => (route.query.category as string | undefined) ?? null);
// 同方向卡片相邻：按方向顺序排序后平铺在同一面板网格中
const visibleIndicators = computed(() =>
  [...indicators.value]
    .filter((i) => !categoryFilter.value || i.category === categoryFilter.value)
    .sort((a, b) => CATEGORY_ORDER.indexOf(a.category) - CATEGORY_ORDER.indexOf(b.category))
);

const CATEGORY_KEYS: Record<MacroCategory, string> = {
  rates: "nav.macroRates",
  inflation: "nav.macroInflation",
  growth: "nav.macroGrowth",
  employment: "nav.macroEmployment",
  liquidity: "nav.macroLiquidity",
  risk: "nav.macroRisk",
};
function categoryLabel(category: MacroCategory): string {
  return t(CATEGORY_KEYS[category] as never);
}

function slicedSeries(ind: MacroIndicator) {
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - RANGE_DAYS[rangeOf(ind.key)]);
  return ind.series.filter((p) => new Date(p.date) >= cutoff);
}

function formatNumber(value: number, decimals: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

onMounted(async () => {
  try {
    const resp = await macroApi.indicators();
    indicators.value = resp.data.indicators;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
});
</script>
