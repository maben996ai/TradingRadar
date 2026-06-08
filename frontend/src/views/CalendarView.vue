<template>
  <section class="stack">
    <div class="hero">
      <div>
        <p class="eyebrow">{{ t("calendar.eyebrow") }}</p>
        <h2>{{ t("calendar.title") }}</h2>
      </div>
      <div class="cal-seg">
        <button class="filter-btn" :class="{ active: tz === BEIJING }" @click="tz = BEIJING">{{ t("calendar.tzBeijing") }}</button>
        <button class="filter-btn" :class="{ active: tz === EASTERN }" @click="tz = EASTERN">{{ t("calendar.tzEastern") }}</button>
      </div>
    </div>

    <!-- 筛选条 -->
    <div class="cal-filters">
      <div class="cal-chip-group">
        <button
          v-for="c in CATEGORIES"
          :key="c"
          class="cal-chip"
          :class="{ active: categories.includes(c) }"
          @click="toggleCategory(c)"
        >{{ t(`calendar.cat_${c}`) }}</button>
      </div>

      <div class="cal-seg">
        <button
          v-for="opt in IMPORTANCE_OPTS"
          :key="opt.value"
          class="filter-btn"
          :class="{ active: importanceMin === opt.value }"
          @click="importanceMin = opt.value"
        >{{ opt.label }}</button>
      </div>

      <div class="cal-range">
        <button v-for="p in PRESETS" :key="p.key" class="filter-btn" @click="applyPreset(p.key)">{{ t(`calendar.preset_${p.key}`) }}</button>
        <input type="date" v-model="startDate" class="cal-date" />
        <span class="cal-range-sep">~</span>
        <input type="date" v-model="endDate" class="cal-date" />
      </div>
    </div>

    <!-- 关注的财报代码 -->
    <div class="cal-tracked">
      <span class="cal-tracked-label">{{ t("calendar.tracked") }}</span>
      <span v-for="tk in trackedTickers" :key="tk.id" class="cal-ticker-chip">
        {{ tk.ticker }}
        <button class="cal-ticker-x" @click="removeTicker(tk.id)">×</button>
      </span>
      <input
        v-model="tickerInput"
        class="cal-ticker-input"
        :placeholder="t('calendar.addTickerPlaceholder')"
        @keyup.enter="addTicker"
      />
      <button class="filter-btn" :disabled="!tickerInput.trim()" @click="addTicker">{{ t("calendar.add") }}</button>
      <label class="cal-tracked-only">
        <input type="checkbox" v-model="trackedOnly" />
        {{ t("calendar.trackedOnly") }}
      </label>
    </div>

    <p v-if="loading" class="muted feed-state">{{ t("calendar.loading") }}</p>
    <p v-else-if="error" class="muted feed-state">{{ t("calendar.error") }}</p>
    <p v-else-if="!groupedEvents.length" class="muted feed-state">{{ t("calendar.empty") }}</p>

    <div v-else class="cal-list">
      <div v-for="group in groupedEvents" :key="group.date" class="cal-day">
        <div class="cal-day-head">
          <span class="cal-day-date">{{ group.date }}</span>
          <span class="cal-day-weekday">{{ group.weekday }}</span>
        </div>
        <div class="cal-table-wrap">
          <table class="cal-table">
            <thead>
              <tr>
                <th>{{ t("calendar.colTime") }}</th>
                <th>{{ t("calendar.colImportance") }}</th>
                <th class="cal-col-event">{{ t("calendar.colEvent") }}</th>
                <th>{{ t("calendar.colPrevious") }}</th>
                <th>{{ t("calendar.colForecast") }}</th>
                <th>{{ t("calendar.colActual") }}</th>
                <th>{{ t("calendar.colAssets") }}</th>
                <th>{{ t("calendar.colSource") }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="ev in group.events" :key="ev.id" class="cal-row" :class="`cal-row-imp${ev.importance}`">
                <td class="cal-time">{{ ev.all_day ? t("calendar.allDay") : fmtTime(ev.scheduled_at) }}</td>
                <td class="cal-stars" :class="`cal-stars-${ev.importance}`">{{ stars(ev.importance) }}</td>
                <td class="cal-col-event">
                  <span class="cal-country">{{ ev.country }}</span>
                  <span class="cal-event-name">{{ ev.title }}</span>
                  <button
                    v-if="ev.kind === 'earnings' && ev.ticker"
                    class="cal-follow"
                    :class="{ followed: isTracked(ev.ticker) }"
                    @click="toggleFollow(ev.ticker, ev.company_name)"
                  >{{ isTracked(ev.ticker) ? t("calendar.followed") : t("calendar.follow") }}</button>
                </td>
                <td class="cal-val">{{ fmtValue(ev.previous, ev.value_unit) }}</td>
                <td class="cal-val">{{ fmtValue(ev.forecast, ev.value_unit) }}</td>
                <td class="cal-val cal-actual" :class="actualClass(ev)">{{ fmtValue(ev.actual, ev.value_unit) }}</td>
                <td class="cal-assets">{{ ev.impact_assets ?? "—" }}</td>
                <td class="cal-source">{{ ev.source }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import { calendarApi } from "../api/calendar";
import { useI18n } from "../i18n";
import type { CalendarCategory, CalendarEvent, TrackedTicker } from "../types";

const { t } = useI18n();

const BEIJING = "Asia/Shanghai";
const EASTERN = "America/New_York";
const CATEGORIES: CalendarCategory[] = ["inflation", "employment", "rates", "growth", "earnings"];
const IMPORTANCE_OPTS = [
  { value: 0, label: "全部" },
  { value: 1, label: "★" },
  { value: 2, label: "★★" },
  { value: 3, label: "★★★" },
];
const PRESETS = [{ key: "today" }, { key: "week" }, { key: "month" }] as const;

const tz = ref(BEIJING);
const categories = ref<CalendarCategory[]>([]);
const importanceMin = ref(0);
const trackedOnly = ref(false);

function toISODate(d: Date): string {
  return d.toISOString().slice(0, 10);
}
const today = new Date();
const startDate = ref(toISODate(new Date(today.getTime() - 7 * 86400000)));
const endDate = ref(toISODate(new Date(today.getTime() + 30 * 86400000)));

const events = ref<CalendarEvent[]>([]);
const trackedTickers = ref<TrackedTicker[]>([]);
const tickerInput = ref("");
const loading = ref(true);
const error = ref(false);

function toggleCategory(c: CalendarCategory) {
  categories.value = categories.value.includes(c)
    ? categories.value.filter((x) => x !== c)
    : [...categories.value, c];
}

function applyPreset(key: string) {
  const now = new Date();
  startDate.value = toISODate(now);
  if (key === "today") endDate.value = toISODate(now);
  else if (key === "week") endDate.value = toISODate(new Date(now.getTime() + 7 * 86400000));
  else endDate.value = toISODate(new Date(now.getTime() + 30 * 86400000));
}

// 时区相关格式化器
const dateKeyFmt = computed(() => new Intl.DateTimeFormat("en-CA", { timeZone: tz.value }));
const timeFmt = computed(
  () => new Intl.DateTimeFormat("en-GB", { timeZone: tz.value, hour: "2-digit", minute: "2-digit", hour12: false })
);
const weekdayFmt = computed(
  () => new Intl.DateTimeFormat("zh-CN", { timeZone: tz.value, weekday: "long" })
);
function fmtTime(iso: string): string {
  return timeFmt.value.format(new Date(iso));
}

const groupedEvents = computed(() => {
  const map = new Map<string, CalendarEvent[]>();
  for (const ev of events.value) {
    const key = dateKeyFmt.value.format(new Date(ev.scheduled_at));
    if (key < startDate.value || key > endDate.value) continue;
    (map.get(key) ?? map.set(key, []).get(key)!).push(ev);
  }
  return [...map.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([date, evs]) => ({
      date,
      weekday: weekdayFmt.value.format(new Date(`${date}T12:00:00Z`)),
      events: evs.sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at)),
    }));
});

function stars(n: number): string {
  return "★".repeat(Math.max(1, Math.min(3, n)));
}
function fmtValue(v: number | null, unit: string | null): string {
  if (v === null || v === undefined) return "—";
  const num = v.toLocaleString("en-US", { maximumFractionDigits: 2 });
  if (!unit) return num;
  // 字母单位（如 EPS）加空格更易读；符号/中文单位（%/千人）直接拼接
  return /[A-Za-z]/.test(unit) ? `${num} ${unit}` : `${num}${unit}`;
}
function actualClass(ev: CalendarEvent): string {
  if (ev.actual === null || ev.forecast === null) return "";
  if (ev.actual > ev.forecast) return "cal-actual-up";
  if (ev.actual < ev.forecast) return "cal-actual-down";
  return "";
}

const trackedSet = computed(() => new Set(trackedTickers.value.map((tk) => tk.ticker)));
function isTracked(ticker: string): boolean {
  return trackedSet.value.has(ticker.toUpperCase());
}

async function loadTracked() {
  try {
    const resp = await calendarApi.trackedTickers();
    trackedTickers.value = resp.data;
  } catch {
    /* 忽略，不阻塞日历 */
  }
}
async function addTicker() {
  const v = tickerInput.value.trim();
  if (!v) return;
  await calendarApi.addTicker(v);
  tickerInput.value = "";
  await loadTracked();
}
async function removeTicker(id: string) {
  await calendarApi.removeTicker(id);
  await loadTracked();
}
async function toggleFollow(ticker: string, name: string | null) {
  const sym = ticker.toUpperCase();
  const existing = trackedTickers.value.find((x) => x.ticker === sym);
  if (existing) await calendarApi.removeTicker(existing.id);
  else await calendarApi.addTicker(sym, name ?? undefined);
  await loadTracked();
}

async function fetchEvents() {
  loading.value = true;
  error.value = false;
  // 给前端时区分组留 1 天缓冲
  const start = new Date(`${startDate.value}T00:00:00Z`);
  start.setUTCDate(start.getUTCDate() - 1);
  const end = new Date(`${endDate.value}T23:59:59Z`);
  end.setUTCDate(end.getUTCDate() + 1);
  try {
    const resp = await calendarApi.events({
      start: start.toISOString(),
      end: end.toISOString(),
      categories: categories.value,
      importance: importanceMin.value || undefined,
      trackedOnly: trackedOnly.value,
    });
    events.value = resp.data.events;
  } catch {
    error.value = true;
  } finally {
    loading.value = false;
  }
}

watch([categories, importanceMin, startDate, endDate, trackedOnly], fetchEvents, { deep: true });

onMounted(() => {
  loadTracked();
  fetchEvents();
});
</script>
