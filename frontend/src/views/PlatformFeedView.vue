<template>
  <section class="stack">
    <div class="hero">
      <div>
        <p class="eyebrow">{{ t("dataSources.eyebrow") }}</p>
        <h2>{{ platformLabel }}</h2>
      </div>
      <div v-if="isJin10" class="feed-filters">
        <button
          v-for="section in jin10Sections"
          :key="section.id"
          class="filter-btn"
          :class="{ active: activeJin10Section === section.id }"
          @click="activeJin10Section = section.id"
        >
          {{ section.label }}
        </button>
      </div>
    </div>

    <div v-if="isJin10Calendar" class="jin10-calendar-rangebar">
      <div class="jin10-calendar-filter-group">
        <span class="jin10-calendar-filter-label">日期</span>
        <button
          v-for="option in calendarRangeOptions"
          :key="option.id"
          type="button"
          class="filter-btn"
          :class="{ active: activeCalendarRange === option.id }"
          @click="activeCalendarRange = option.id"
        >
          {{ option.label }}
        </button>
      </div>
      <div v-if="activeCalendarRange === 'custom'" class="jin10-calendar-custom-range">
        <input v-model="customCalendarStart" type="date" class="jin10-calendar-date-input" aria-label="开始日期" />
        <span>至</span>
        <input v-model="customCalendarEnd" type="date" class="jin10-calendar-date-input" aria-label="结束日期" />
      </div>
      <div class="jin10-calendar-filter-group">
        <span class="jin10-calendar-filter-label">重要度</span>
        <button
          v-for="option in calendarImportanceOptions"
          :key="option.id"
          type="button"
          class="filter-btn"
          :class="{ active: activeCalendarImportance === option.id }"
          @click="activeCalendarImportance = option.id"
        >
          {{ option.label }}
        </button>
      </div>
    </div>

    <template v-if="isPlaceholder">
      <p class="muted feed-state">{{ t("dataSources.comingSoon") }}</p>
    </template>
    <template v-else>
      <p v-if="feedStore.loading" class="muted feed-state">{{ t("feed.loading") }}</p>
      <p v-else-if="!platformVideos.length" class="muted feed-state">{{ t("feed.empty") }}</p>

      <template v-else>
        <div v-if="isJin10Calendar" class="jin10-calendar-list">
          <div class="jin10-calendar-summary">
            <span>北京时间</span>
            <span>{{ platformVideos.length }} 项事件</span>
            <span class="jin10-calendar-legend"><i class="imp-high"></i>高重要性</span>
          </div>
          <div v-for="group in calendarGroups" :key="group.date" class="jin10-calendar-day">
            <div class="jin10-calendar-day-head">
              <div>
                <span class="jin10-calendar-date">{{ group.date }}</span>
                <span class="jin10-calendar-weekday">{{ group.weekday }}</span>
              </div>
              <span class="jin10-calendar-count">{{ group.events.length }} 项</span>
            </div>
            <div class="jin10-calendar-table-wrap">
              <table class="jin10-calendar-table">
                <thead>
                  <tr>
                    <th>时间</th>
                    <th>重要性</th>
                    <th class="jin10-calendar-event-col">事件</th>
                    <th>前值</th>
                    <th>预期</th>
                    <th>公布值</th>
                    <th>修正</th>
                    <th>影响</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="event in group.events"
                    :key="event.id"
                    class="jin10-calendar-row"
                    :class="`importance-${event.importance}`"
                  >
                    <td class="jin10-calendar-time">{{ event.time }}</td>
                    <td>
                      <span class="jin10-calendar-stars" :class="`stars-${event.importance}`">{{ stars(event.importance) }}</span>
                    </td>
                    <td class="jin10-calendar-event-col">
                      <span class="jin10-calendar-event-name">{{ event.title }}</span>
                    </td>
                    <td>{{ event.previous }}</td>
                    <td>{{ event.consensus }}</td>
                    <td class="jin10-calendar-actual">{{ event.actual }}</td>
                    <td>{{ event.revised }}</td>
                    <td>
                      <span class="jin10-calendar-affect" :class="event.affectClass">{{ event.affect }}</span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <div v-else-if="isTextFeed" class="social-timeline">
          <article v-for="post in pagedVideos" :key="post.id" class="social-post">
            <img
              v-if="post.data_source_avatar_url"
              :src="post.data_source_avatar_url"
              class="social-avatar"
              :alt="post.data_source_name"
              referrerpolicy="no-referrer"
            />
            <div v-else class="social-avatar social-avatar-placeholder" />
            <div class="social-body">
              <div class="social-head">
                <span class="social-author">{{ post.data_source_name }}</span>
                <span class="social-dot">·</span>
                <span class="social-time">{{ formatPublishedAt(post.published_at) }}</span>
              </div>
              <p class="social-text" :class="{ collapsed: isCollapsed(post) }">{{ post.content_text }}</p>
              <div
                v-if="post.thumbnail_url"
                class="social-media-frame"
                :class="{ collapsed: isCollapsed(post) }"
              >
                <img
                  :src="post.thumbnail_url"
                  class="social-media"
                  :alt="post.content_text"
                  loading="lazy"
                  referrerpolicy="no-referrer"
                  @click="lightboxUrl = post.thumbnail_url"
                />
              </div>
              <div class="social-actions">
                <button
                  v-if="canCollapse(post)"
                  type="button"
                  class="social-more"
                  @click="toggleExpand(post.id)"
                >
                  {{ expandedPosts.has(post.id) ? t("feed.showLess") : t("feed.showMore") }}
                </button>
                <span v-else></span>
                <a :href="post.content_url" target="_blank" rel="noopener noreferrer" class="social-source-link">{{ t("feed.viewOriginal") }}</a>
              </div>
            </div>
          </article>
        </div>

        <div v-else class="video-grid-sm">
          <a
            v-for="video in pagedVideos"
            :key="video.id"
            :href="video.content_url"
            target="_blank"
            rel="noopener noreferrer"
            class="video-card-sm"
          >
              <div class="video-thumb-sm">
                <img v-if="video.thumbnail_url" :src="video.thumbnail_url" :alt="video.title" loading="lazy" referrerpolicy="no-referrer" />
                <div v-else class="video-thumb-placeholder" />
              </div>
            <div class="video-info-sm">
              <p class="video-title-sm">{{ video.title }}</p>
              <div class="video-meta-sm">
                <span class="muted">{{ formatPublishedAt(video.published_at) }}</span>
                <span class="muted">{{ formatDuration(video.duration_seconds) }}</span>
              </div>
            </div>
          </a>
        </div>

        <div v-if="totalPages > 1" class="pagination">
          <button class="filter-btn" :disabled="page === 1" @click="page--">{{ t("feed.prevPage") }}</button>
          <span class="muted page-indicator">{{ page }} / {{ totalPages }}</span>
          <button class="filter-btn" :disabled="page === totalPages" @click="page++">{{ t("feed.nextPage") }}</button>
        </div>
      </template>
    </template>

    <div v-if="lightboxUrl" class="lightbox" @click="lightboxUrl = null">
      <img :src="lightboxUrl" class="lightbox-img" alt="" referrerpolicy="no-referrer" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { useI18n } from "../i18n";
import { useFeedStore } from "../stores/feed";
import type { ContentItem } from "../types";
import { formatPublishedAt } from "../utils/datetime";
import { formatDuration } from "../utils/duration";

const { t } = useI18n();
const route = useRoute();
const feedStore = useFeedStore();

const PAGE_SIZE = 15;
const page = ref(1);
const lightboxUrl = ref<string | null>(null);
type Jin10CalendarRangePreset = "week" | "month" | "custom";
type Jin10CalendarImportance = "all" | "5" | "4" | "3" | "2" | "1";

const platform = computed(() => (route.params.platform as string) ?? "twitter");
const isJin10 = computed(() => platform.value === "finance_news");
const isJin10Calendar = computed(() => isJin10.value && activeJin10Section.value === "jin10_calendar");
const isTextFeed = computed(() => platform.value === "twitter" || platform.value === "finance_news");
const activeJin10Section = ref("jin10_flash");
const activeCalendarRange = ref<Jin10CalendarRangePreset>("week");
const activeCalendarImportance = ref<Jin10CalendarImportance>("all");
const customCalendarStart = ref("");
const customCalendarEnd = ref("");
const jin10Sections = [
  { id: "jin10_flash", label: "市场快讯" },
  { id: "jin10_news", label: "财经资讯" },
  { id: "jin10_calendar", label: "财经日历" },
];
const calendarRangeOptions: Array<{ id: Jin10CalendarRangePreset; label: string }> = [
  { id: "week", label: "最近1周" },
  { id: "month", label: "最近1月" },
  { id: "custom", label: "日期范围" },
];
const calendarImportanceOptions: Array<{ id: Jin10CalendarImportance; label: string }> = [
  { id: "all", label: "全部" },
  { id: "5", label: "5星" },
  { id: "4", label: "4星" },
  { id: "3", label: "3星" },
  { id: "2", label: "2星" },
  { id: "1", label: "1星" },
];

const PLACEHOLDER_PLATFORMS = ["bloomberg", "reuters", "macro_market", "finance_calendar"];
const isPlaceholder = computed(() => PLACEHOLDER_PLATFORMS.includes(platform.value));

const platformLabel = computed(() => {
  switch (platform.value) {
    case "twitter": return t("nav.socialMedia");
    case "youtube": return t("nav.financeVideo");
    case "finance_news": return t("nav.financeNews");
    case "bloomberg": return t("nav.srcBloomberg");
    case "reuters": return t("nav.srcReuters");
    case "macro_market": return t("nav.macroMarket");
    case "finance_calendar": return t("nav.financeCalendar");
    default: return platform.value;
  }
});

const basePlatformVideos = computed(() =>
  feedStore.videos
    .filter((v) => v.source_type === platform.value)
    .filter((v) => !isJin10.value || v.data_source_external_id === activeJin10Section.value)
);

const platformVideos = computed(() => {
  const items = isJin10Calendar.value
    ? basePlatformVideos.value.filter(isInCalendarRange).filter(isInCalendarImportance)
    : [...basePlatformVideos.value];
  return items.sort((a, b) => {
    const aTime = new Date(a.published_at).getTime();
    const bTime = new Date(b.published_at).getTime();
    return isJin10Calendar.value ? aTime - bTime : bTime - aTime;
  });
});

const currentPageSize = computed(() => (isJin10Calendar.value ? 50 : PAGE_SIZE));
const totalPages = computed(() => Math.max(1, Math.ceil(platformVideos.value.length / currentPageSize.value)));
const pagedVideos = computed(() => {
  const start = (page.value - 1) * currentPageSize.value;
  return platformVideos.value.slice(start, start + currentPageSize.value);
});

interface CalendarRow {
  id: string;
  date: string;
  weekday: string;
  time: string;
  importance: number;
  title: string;
  previous: string;
  consensus: string;
  actual: string;
  revised: string;
  affect: string;
  affectClass: string;
}

const calendarGroups = computed(() => {
  const groups = new Map<string, { date: string; weekday: string; events: CalendarRow[] }>();
  for (const item of pagedVideos.value) {
    const row = toCalendarRow(item);
    const group = groups.get(row.date) ?? { date: row.date, weekday: row.weekday, events: [] };
    group.events.push(row);
    groups.set(row.date, group);
  }
  return [...groups.values()];
});

function toCalendarRow(item: ContentItem): CalendarRow {
  const raw = item.raw_data ?? {};
  const dt = new Date(item.published_at);
  const affect = rawText(raw.affect_txt);
  const title = rawText(raw.title) || item.title;
  return {
    id: item.id,
    date: formatCalendarDate(dt),
    weekday: formatCalendarWeekday(dt),
    time: formatCalendarTime(dt),
    importance: calendarImportance(item),
    title,
    previous: formatCalendarValue(raw.previous, title),
    consensus: formatCalendarValue(raw.consensus, title),
    actual: formatCalendarValue(raw.actual, title),
    revised: formatCalendarValue(raw.revised, title),
    affect: affect || "-",
    affectClass: affect.includes("利多") ? "positive" : affect.includes("利空") ? "negative" : "neutral",
  };
}

function formatCalendarValue(value: unknown, title: string): string {
  const text = rawText(value);
  if (!text) return "-";
  if (text.includes("%") || !isPercentCalendarEvent(title)) return text;
  return `${text}%`;
}

function isPercentCalendarEvent(title: string): boolean {
  return /年率|月率|季率|利率|通胀率|失业率|增长率|环比|同比/.test(title);
}

function calendarImportance(item: ContentItem): number {
  return Math.max(1, Math.min(5, Number(item.raw_data?.star) || 1));
}

function rawText(value: unknown): string {
  if (value === null || value === undefined || value === "") return "";
  return String(value);
}

function formatCalendarDate(value: Date): string {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    timeZone: "Asia/Shanghai",
  }).format(value);
}

function formatCalendarWeekday(value: Date): string {
  return new Intl.DateTimeFormat("zh-CN", {
    weekday: "long",
    timeZone: "Asia/Shanghai",
  }).format(value);
}

function formatCalendarTime(value: Date): string {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Shanghai",
  }).format(value);
}

function isInCalendarRange(item: ContentItem): boolean {
  const itemDate = calendarDateKey(new Date(item.published_at));
  if (activeCalendarRange.value === "week") {
    return itemDate >= todayCalendarDateKey() && itemDate <= futureCalendarDateKey(7);
  }
  if (activeCalendarRange.value === "month") {
    return itemDate >= todayCalendarDateKey() && itemDate <= futureCalendarDateKey(30);
  }
  return (
    (!customCalendarStart.value || itemDate >= customCalendarStart.value) &&
    (!customCalendarEnd.value || itemDate <= customCalendarEnd.value)
  );
}

function calendarDateKey(value: Date): string {
  return new Intl.DateTimeFormat("sv-SE", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    timeZone: "Asia/Shanghai",
  }).format(value);
}

function todayCalendarDateKey(): string {
  return calendarDateKey(new Date());
}

function futureCalendarDateKey(days: number): string {
  const value = new Date();
  value.setDate(value.getDate() + days);
  return calendarDateKey(value);
}

function isInCalendarImportance(item: ContentItem): boolean {
  return activeCalendarImportance.value === "all" || calendarImportance(item) === Number(activeCalendarImportance.value);
}

function stars(value: number): string {
  return "★".repeat(value);
}

const COLLAPSE_THRESHOLD = 140;
const expandedPosts = reactive(new Set<string>());
function canCollapse(item: ContentItem): boolean {
  return (item.content_text?.length ?? 0) > COLLAPSE_THRESHOLD || Boolean(item.thumbnail_url);
}
function isCollapsed(item: ContentItem): boolean {
  return canCollapse(item) && !expandedPosts.has(item.id);
}
function toggleExpand(id: string): void {
  if (expandedPosts.has(id)) expandedPosts.delete(id);
  else expandedPosts.add(id);
}

// 切换平台时重置分页
watch(platform, () => {
  page.value = 1;
  expandedPosts.clear();
});

watch(activeJin10Section, () => {
  page.value = 1;
  expandedPosts.clear();
});

watch([activeCalendarRange, activeCalendarImportance, customCalendarStart, customCalendarEnd], () => {
  page.value = 1;
  expandedPosts.clear();
});

onMounted(() => {
  if (!feedStore.videos.length) feedStore.fetchVideos();
});
</script>
