<template>
  <section class="stack">
    <!-- 顶栏 -->
    <header class="hero">
      <div>
        <h2>{{ activeTabLabel }}</h2>
        <p class="page-meta">{{ feedStore.videos.length }} {{ t("feed.itemsUnit") }}</p>
      </div>
      <div class="hero-controls">
        <div class="feed-filters">
          <button class="filter-btn" :class="{ active: contentType === 'video' }" @click="setContentType('video')">{{ t("feed.tabVideos") }}</button>
          <button class="filter-btn" :class="{ active: contentType === 'article' }" @click="setContentType('article')">{{ t("feed.tabArticles") }}</button>
          <button class="filter-btn" :class="{ active: contentType === 'news' }" @click="setContentType('news')">{{ t("feed.tabNews") }}</button>
          <button class="filter-btn" :class="{ active: contentType === 'market' }" @click="setContentType('market')">{{ t("feed.tabMarket") }}</button>
        </div>
        <div v-if="contentType === 'video'" class="feed-filters">
          <button class="filter-btn" :class="{ active: sortMode === 'time' }" @click="setSortMode('time')">{{ t("feed.sortByTime") }}</button>
          <button class="filter-btn" :class="{ active: sortMode === 'author' }" @click="setSortMode('author')">{{ t("feed.sortByAuthor") }}</button>
        </div>
        <button class="icon-btn" :title="t('feed.refresh')" @click="refresh">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 12a9 9 0 1 1-3.5-7.1" /><polyline points="21 4 21 12 13 12" /></svg>
        </button>
      </div>
    </header>

    <p v-if="feedStore.loading" class="muted feed-state">{{ t("feed.loading") }}</p>
    <p v-else-if="feedStore.error" class="error-msg feed-state">{{ t("feed.fetchError") }}</p>

    <!-- 资讯 / 市场：静态占位 -->
    <template v-else-if="contentType === 'news' || contentType === 'market'">
      <div class="card-grid">
        <div v-for="item in placeholderNews" :key="item.title" class="card card-news">
          <div class="card-news-header">
            <div class="source-chip"><span class="source-dot" :style="`background:${item.color}`"></span>{{ item.source }}</div>
            <span class="card-time">{{ item.time }}</span>
          </div>
          <div class="card-title">{{ item.title }}</div>
          <div class="card-summary">{{ item.summary }}</div>
        </div>
      </div>
      <p class="muted feed-state">{{ t("feed.placeholderHint") }}</p>
    </template>

    <template v-else-if="feedStore.videos.length === 0">
      <p class="muted feed-state">{{ t("feed.empty") }}</p>
    </template>

    <!-- 按作者分组 -->
    <template v-else-if="sortMode === 'author'">
      <div class="panel author-groups-panel">
        <div class="author-groups-scroll">
          <div v-for="group in pagedAuthorGroups" :key="group.sourceId" class="author-group">
            <div class="author-group-header">
              <img v-if="group.avatarUrl" :src="group.avatarUrl" class="creator-avatar" :alt="group.sourceName" referrerpolicy="no-referrer" />
              <div v-else class="creator-avatar creator-avatar-placeholder" />
              <div class="author-group-title-row">
                <RouterLink :to="`/source/${group.sourceId}`" class="author-group-name">{{ group.sourceName }}</RouterLink>
                <span class="platform-badge author-inline-platform" :class="group.sourceType">{{ group.sourceType }}</span>
              </div>
              <RouterLink :to="`/source/${group.sourceId}`" class="author-view-all muted">
                {{ t("feed.viewAll") }} {{ group.videos.length }} →
              </RouterLink>
            </div>
            <div class="video-grid-sm">
              <a
                v-for="video in group.videos.slice(0, 5)"
                :key="video.id"
                :href="video.video_url"
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
                    <span>{{ formatPublishedAt(video.published_at) }}</span>
                    <span>{{ formatDuration(video.duration_seconds) }}</span>
                  </div>
                </div>
              </a>
            </div>
          </div>

          <div v-if="canPaginateAuthors" class="pagination author-pagination">
            <button class="filter-btn" :disabled="page === 1 || feedStore.loadingMore" @click="page--">{{ t("feed.prevPage") }}</button>
            <span class="muted page-indicator">{{ authorPageLabel }}</span>
            <button class="filter-btn" :disabled="!canGoNextAuthor || feedStore.loadingMore" @click="goNextAuthorPage">{{ t("feed.nextPage") }}</button>
          </div>
        </div>
      </div>
    </template>

    <!-- 按时间：按天分组的大卡片 -->
    <template v-else>
      <div class="feed">
        <div class="feed-header">
          <div class="feed-stats">
            <span><strong>{{ feedStore.videos.length }}</strong>{{ t("feed.statTotal") }}</span>
            <span><strong>{{ authorGroups.length }}</strong>{{ t("feed.statSources") }}</span>
          </div>
        </div>

        <template v-for="dayGroup in pagedDayGroups" :key="dayGroup.key">
          <div class="day-divider"><span class="day-label">{{ dayGroup.label }}</span><span class="line"></span></div>
          <div class="card-grid">
            <a
              v-for="video in dayGroup.videos"
              :key="video.id"
              :href="video.video_url"
              target="_blank"
              rel="noopener noreferrer"
              class="card"
            >
              <div class="card-thumb">
                <img v-if="video.thumbnail_url" :src="video.thumbnail_url" :alt="video.title" loading="lazy" referrerpolicy="no-referrer" />
                <span class="platform-badge" :class="video.source_type">{{ video.source_type }}</span>
                <span v-if="formatDuration(video.duration_seconds)" class="duration">{{ formatDuration(video.duration_seconds) }}</span>
              </div>
              <div class="card-body">
                <div class="card-meta">
                  <span class="card-author">
                    <img v-if="video.data_source_avatar_url" :src="video.data_source_avatar_url" class="author-avatar" :alt="video.data_source_name" referrerpolicy="no-referrer" />
                    <span v-else class="author-avatar" />
                    <span class="author-name">{{ video.data_source_name }}</span>
                  </span>
                  <span>·</span>
                  <span class="card-time">{{ timeLabel(video.published_at) }}</span>
                </div>
                <div class="card-title">{{ video.title }}</div>
              </div>
            </a>
          </div>
        </template>
      </div>

      <div v-if="canPaginateTime" class="pagination">
        <button class="filter-btn" :disabled="page === 1 || feedStore.loadingMore" @click="page--">{{ t("feed.prevPage") }}</button>
        <span class="muted page-indicator">{{ timePageLabel }}</span>
        <button class="filter-btn" :disabled="!canGoNextTime || feedStore.loadingMore" @click="goNextTimePage">{{ t("feed.nextPage") }}</button>
      </div>
    </template>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { RouterLink } from "vue-router";

import { useI18n } from "../i18n";
import { useFeedStore } from "../stores/feed";
import type { Video } from "../types";
import { formatPublishedAt } from "../utils/datetime";
import { formatDuration } from "../utils/duration";

const { t } = useI18n();
const feedStore = useFeedStore();

const VIDEO_PAGE_SIZE = 15;
const AUTHOR_PAGE_SIZE = 4;
const contentType = ref<"video" | "article" | "news" | "market">("video");
const sortMode = ref<"time" | "author">("time");
const page = ref(1);

const activeTabLabel = computed(() => {
  switch (contentType.value) {
    case "video": return t("feed.tabVideos");
    case "article": return t("feed.tabArticles");
    case "news": return t("feed.tabNews");
    case "market": return t("feed.tabMarket");
  }
});

function timeLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

function dayKey(iso: string): string {
  const d = new Date(iso);
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`;
}

function dayLabel(iso: string): string {
  const d = new Date(iso);
  const today = new Date();
  const yesterday = new Date();
  yesterday.setDate(today.getDate() - 1);
  const sameDay = (a: Date, b: Date) =>
    a.getFullYear() === b.getFullYear() && a.getMonth() === b.getMonth() && a.getDate() === b.getDate();
  const weekdays = ["日", "一", "二", "三", "四", "五", "六"];
  const dateStr = `${d.getMonth() + 1}月${d.getDate()}日 星期${weekdays[d.getDay()]}`;
  if (sameDay(d, today)) return `${t("feed.today")} · ${dateStr}`;
  if (sameDay(d, yesterday)) return `${t("feed.yesterday")} · ${dateStr}`;
  return dateStr;
}

const sortedByTime = computed(() =>
  [...feedStore.videos].sort(
    (a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime()
  )
);

const knownTimePages = computed(() => Math.max(1, Math.ceil(sortedByTime.value.length / VIDEO_PAGE_SIZE)));
const pagedVideos = computed(() => {
  const start = (page.value - 1) * VIDEO_PAGE_SIZE;
  return sortedByTime.value.slice(start, start + VIDEO_PAGE_SIZE);
});

interface DayGroup {
  key: string;
  label: string;
  videos: Video[];
}

const pagedDayGroups = computed((): DayGroup[] => {
  const groups: DayGroup[] = [];
  let current: DayGroup | null = null;
  for (const video of pagedVideos.value) {
    const key = dayKey(video.published_at);
    if (!current || current.key !== key) {
      current = { key, label: dayLabel(video.published_at), videos: [] };
      groups.push(current);
    }
    current.videos.push(video);
  }
  return groups;
});

interface AuthorGroup {
  sourceId: string;
  sourceName: string;
  avatarUrl: string | null | undefined;
  sourceType: string;
  videos: Video[];
}

const authorGroups = computed((): AuthorGroup[] => {
  const map = new Map<string, AuthorGroup>();
  for (const video of feedStore.videos) {
    if (!map.has(video.data_source_id)) {
      map.set(video.data_source_id, {
        sourceId: video.data_source_id,
        sourceName: video.data_source_name,
        avatarUrl: video.data_source_avatar_url,
        sourceType: video.source_type,
        videos: [],
      });
    }
    map.get(video.data_source_id)!.videos.push(video);
  }
  for (const group of map.values()) {
    group.videos.sort(
      (a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime()
    );
  }
  return [...map.values()].sort(
    (a, b) =>
      new Date(b.videos[0].published_at).getTime() -
      new Date(a.videos[0].published_at).getTime()
  );
});

const knownAuthorPages = computed(() => Math.max(1, Math.ceil(authorGroups.value.length / AUTHOR_PAGE_SIZE)));
const pagedAuthorGroups = computed(() => {
  const start = (page.value - 1) * AUTHOR_PAGE_SIZE;
  return authorGroups.value.slice(start, start + AUTHOR_PAGE_SIZE);
});

const canGoNextTime = computed(() => page.value < knownTimePages.value || feedStore.hasMore);
const canGoNextAuthor = computed(() => page.value < knownAuthorPages.value || feedStore.hasMore);
const canPaginateTime = computed(() => knownTimePages.value > 1 || feedStore.hasMore);
const canPaginateAuthors = computed(() => knownAuthorPages.value > 1 || feedStore.hasMore);
const timePageLabel = computed(() =>
  feedStore.hasMore ? `${page.value} / ${knownTimePages.value}+` : `${page.value} / ${knownTimePages.value}`
);
const authorPageLabel = computed(() =>
  feedStore.hasMore ? `${page.value} / ${knownAuthorPages.value}+` : `${page.value} / ${knownAuthorPages.value}`
);

const placeholderNews = computed(() => [
  {
    source: "华尔街见闻",
    color: "#6366f1",
    time: "11:42",
    title: t("feed.placeholderHint"),
    summary: t("feed.placeholderSummary"),
  },
  {
    source: "财联社",
    color: "#6366f1",
    time: "09:18",
    title: t("feed.placeholderHint"),
    summary: t("feed.placeholderSummary"),
  },
]);

function setContentType(type: typeof contentType.value) {
  contentType.value = type;
  page.value = 1;
}

function setSortMode(mode: "time" | "author") {
  sortMode.value = mode;
  page.value = 1;
}

async function refresh() {
  await feedStore.fetchVideos(3);
  page.value = 1;
  await ensureCurrentPageLoaded();
}

async function ensureTimePageLoaded(targetPage: number) {
  await feedStore.ensureVideoCount(targetPage * VIDEO_PAGE_SIZE);
}

async function ensureAuthorPageLoaded(targetPage: number) {
  const requiredAuthors = targetPage * AUTHOR_PAGE_SIZE;
  while (authorGroups.value.length < requiredAuthors && feedStore.hasMore) {
    await feedStore.fetchNextPage();
  }
}

async function ensureCurrentPageLoaded() {
  if (contentType.value !== "video") return;
  if (sortMode.value === "author") {
    await ensureAuthorPageLoaded(page.value);
    return;
  }
  await ensureTimePageLoaded(page.value);
}

async function goNextTimePage() {
  const nextPage = page.value + 1;
  await ensureTimePageLoaded(nextPage);
  if (nextPage <= knownTimePages.value || feedStore.hasMore || sortedByTime.value.length >= nextPage * VIDEO_PAGE_SIZE) {
    page.value = nextPage;
  }
}

async function goNextAuthorPage() {
  const nextPage = page.value + 1;
  await ensureAuthorPageLoaded(nextPage);
  if (nextPage <= knownAuthorPages.value || feedStore.hasMore || authorGroups.value.length >= nextPage * AUTHOR_PAGE_SIZE) {
    page.value = nextPage;
  }
}

watch([contentType, sortMode], () => {
  page.value = 1;
  void ensureCurrentPageLoaded();
});

watch(page, () => {
  void ensureCurrentPageLoaded();
});

onMounted(async () => {
  await feedStore.fetchVideos(3);
  await ensureCurrentPageLoaded();
});
</script>
