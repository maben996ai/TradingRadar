<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-logo"></div>
        <div class="brand-name">Trading<span>Rader</span></div>
      </div>

      <div class="sidebar-search">
        <div class="search-box">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8" /><path d="m21 21-4.3-4.3" /></svg>
          <input type="text" :placeholder="t('nav.searchPlaceholder')" />
          <kbd>⌘K</kbd>
        </div>
      </div>

      <nav class="nav">
        <!-- 信源 -->
        <div class="nav-section">
          <div class="nav-section-title">
            <span>{{ t("nav.sectionSources") }}</span>
            <button class="nav-add-btn" :title="t('nav.dataSources')" @click="router.push('/sources')">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M12 5v14M5 12h14" /></svg>
            </button>
          </div>

          <!-- 金融时讯（内置金十数据） -->
          <div class="nav-item expandable" @click="openPlatform('financeNews', '/feed/finance_news')">
            <span class="nav-item-toggle" :class="{ expanded: expanded.financeNews }" @click.stop="toggleExpand('financeNews')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8"><polyline points="9 18 15 12 9 6" /></svg>
            </span>
            <span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" /><polyline points="14 2 14 8 20 8" /><line x1="8" y1="13" x2="16" y2="13" /><line x1="8" y1="17" x2="16" y2="17" /></svg></span>
            <span class="nav-item-label">{{ t("nav.financeNews") }}</span>
          </div>
          <div class="nav-children" :class="{ expanded: expanded.financeNews }">
            <RouterLink
              v-for="item in financeNewsTabs"
              :key="item.key"
              :to="item.path"
              class="nav-child"
            >
              <span class="nav-source-logo" :class="item.logoClass" aria-hidden="true">{{ item.logoText }}</span>
              <span class="nav-item-label">{{ item.label }}</span>
            </RouterLink>
          </div>

          <!-- 社交媒体（真实订阅博主） -->
          <div class="nav-item expandable" @click="openPlatform('socialMedia', '/feed/twitter')">
            <span class="nav-item-toggle" :class="{ expanded: expanded.socialMedia }" @click.stop="toggleExpand('socialMedia')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8"><polyline points="9 18 15 12 9 6" /></svg>
            </span>
            <span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" /></svg></span>
            <span class="nav-item-label">{{ t("nav.socialMedia") }}</span>
          </div>
          <div class="nav-children" :class="{ expanded: expanded.socialMedia }">
            <RouterLink v-for="s in twitterSources" :key="s.id" :to="`/source/${s.id}`" class="nav-child">
              <img v-if="sourceHasContent(s.id) && s.avatar_url" :src="s.avatar_url" :alt="s.name" class="nav-source-avatar" referrerpolicy="no-referrer" />
              <span v-else-if="sourceHasContent(s.id)" class="nav-source-avatar nav-source-avatar-placeholder">{{ sourceInitial(s.name) }}</span>
              <span v-else class="nav-item-icon"><span class="dot dot-twitter"></span></span>
              <span class="nav-item-label">{{ s.name }}</span>
            </RouterLink>
          </div>

          <!-- 财经视频（真实订阅博主） -->
          <div class="nav-item expandable" @click="openPlatform('financeVideo', '/feed/youtube')">
            <span class="nav-item-toggle" :class="{ expanded: expanded.financeVideo }" @click.stop="toggleExpand('financeVideo')">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8"><polyline points="9 18 15 12 9 6" /></svg>
            </span>
            <span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="2" y="5" width="20" height="14" rx="3" /><path d="M10 9l5 3-5 3z" /></svg></span>
            <span class="nav-item-label">{{ t("nav.financeVideo") }}</span>
          </div>
          <div class="nav-children" :class="{ expanded: expanded.financeVideo }">
            <RouterLink v-for="s in youtubeSources" :key="s.id" :to="`/source/${s.id}`" class="nav-child">
              <img v-if="sourceHasContent(s.id) && s.avatar_url" :src="s.avatar_url" :alt="s.name" class="nav-source-avatar" referrerpolicy="no-referrer" />
              <span v-else-if="sourceHasContent(s.id)" class="nav-source-avatar nav-source-avatar-placeholder">{{ sourceInitial(s.name) }}</span>
              <span v-else class="nav-item-icon"><span class="dot dot-youtube"></span></span>
              <span class="nav-item-label">{{ s.name }}</span>
            </RouterLink>
          </div>

          <!-- 市场宏观（真实看板，单一入口，无子项） -->
          <RouterLink to="/macro-market" class="nav-item">
            <span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="23 6 13.5 15.5 8.5 10.5 1 18" /><polyline points="17 6 23 6 23 12" /></svg></span>
            <span class="nav-item-label">{{ t("nav.macroMarket") }}</span>
          </RouterLink>

          <!-- 财经日历（真实事件日历，单一入口，无子项） -->
          <RouterLink to="/calendar" class="nav-item">
            <span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="3" y="4" width="18" height="18" rx="2" /><line x1="16" y1="2" x2="16" y2="6" /><line x1="8" y1="2" x2="8" y2="6" /><line x1="3" y1="10" x2="21" y2="10" /></svg></span>
            <span class="nav-item-label">{{ t("nav.financeCalendar") }}</span>
          </RouterLink>
        </div>

        <!-- 分析 -->
        <div class="nav-section">
          <div class="nav-section-title">{{ t("nav.sectionAnalysis") }}</div>
          <RouterLink to="/content-analysis" class="nav-item">
            <span class="nav-item-icon"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" /><polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" /></svg></span>
            <span class="nav-item-label">{{ t("nav.contentAnalysis") }}</span>
          </RouterLink>
          <div class="nav-children expanded">
            <RouterLink to="/stock-analysis" class="nav-child">
              <span class="nav-item-label">{{ t("nav.stockAnalysis") }}</span>
            </RouterLink>
            <div class="nav-child">
              <span class="nav-item-label">{{ t("nav.marketAnalysis") }}</span>
            </div>
          </div>
        </div>

        <!-- 控制中心 -->
        <div class="nav-section">
          <RouterLink to="/control-center" class="nav-section-title nav-section-link">
            {{ t("nav.controlCenter") }}
          </RouterLink>
        </div>
      </nav>

      <div class="locale-toggle">
        <button
          class="locale-link"
          :class="{ 'locale-link-active': locale === 'zh-CN' }"
          @click="setLocale('zh-CN')"
        >中文</button>
        <span class="locale-sep">/</span>
        <button
          class="locale-link"
          :class="{ 'locale-link-active': locale === 'en' }"
          @click="setLocale('en')"
        >EN</button>
      </div>

      <div class="user-area">
        <div class="user-avatar">{{ userInitials }}</div>
        <div class="user-info">
          <div class="user-name">{{ authStore.user?.display_name ?? authStore.user?.email }}</div>
          <div class="user-status">{{ t("nav.memberOnline") }}</div>
        </div>
        <button :title="t('nav.controlCenter')" @click="router.push('/control-center')">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" /></svg>
        </button>
        <button :title="t('nav.signOut')" @click="handleLogout">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" /></svg>
        </button>
      </div>
    </aside>

    <main class="content">
      <RouterView />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink, RouterView, useRouter } from "vue-router";

import { dataSourcesApi } from "../../api/data-sources";
import { useI18n } from "../../i18n";
import { useAuthStore } from "../../stores/auth";
import { useFeedStore } from "../../stores/feed";
import type { DataSource } from "../../types";

const router = useRouter();
const authStore = useAuthStore();
const feedStore = useFeedStore();
const { t, locale, setLocale } = useI18n();

// 真实订阅信源：社交媒体 / 财经视频 展开后的博主来自这里
const sources = ref<DataSource[]>([]);
const latestBySourceId = computed(() => {
  const latest = new Map<string, number>();
  for (const item of feedStore.videos) {
    const ts = new Date(item.published_at).getTime();
    const current = latest.get(item.data_source_id) ?? 0;
    if (ts > current) latest.set(item.data_source_id, ts);
  }
  return latest;
});
// 按最新发文时间降序：新发内容的作者排最前；无内容的按添加时间兜底
function sortByLatest(list: DataSource[]): DataSource[] {
  return [...list].sort((a, b) => {
    const aLatest = latestBySourceId.value.get(a.id) ?? 0;
    const bLatest = latestBySourceId.value.get(b.id) ?? 0;
    if (aLatest !== bLatest) return bLatest - aLatest;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });
}
const twitterSources = computed(() =>
  sortByLatest(sources.value.filter((s) => s.source_type === "twitter"))
);
const youtubeSources = computed(() =>
  sortByLatest(sources.value.filter((s) => s.source_type === "youtube"))
);
const financeNewsSources = computed(() =>
  sortByLatest(sources.value.filter((s) => s.source_type === "finance_news"))
);
const financeNewsTabs = computed(() => {
  const jin10Source = financeNewsSources.value[0];
  return [
    {
      key: "jin10",
      label: "jin10",
      path: "/feed/finance_news",
      logoClass: "nav-source-logo-jin10",
      logoText: "10",
    },
    {
      key: "bloomberg",
      label: "Bloomberg",
      path: "/feed/bloomberg",
      logoClass: "nav-source-logo-bloomberg",
      logoText: "B",
    },
    {
      key: "reuters",
      label: "Reuters",
      path: "/feed/reuters",
      logoClass: "nav-source-logo-reuters",
      logoText: "R",
    },
  ];
});

const expanded = reactive<Record<string, boolean>>({});
function toggleExpand(key: string) {
  expanded[key] = !expanded[key];
}

function openPlatform(key: string, path: string) {
  expanded[key] = true;
  router.push(path);
}

function sourceHasContent(sourceId: string): boolean {
  return latestBySourceId.value.has(sourceId);
}

function sourceInitial(name: string): string {
  return name.trim().slice(0, 1).toUpperCase() || "?";
}

const userInitials = computed(() => {
  const name = authStore.user?.display_name ?? authStore.user?.email ?? "";
  return name.slice(0, 2).toUpperCase();
});

function handleLogout() {
  authStore.logout();
  router.push("/login");
}

onMounted(async () => {
  if (!feedStore.videos.length) feedStore.fetchVideos();
  try {
    const resp = await dataSourcesApi.list();
    sources.value = resp.data as DataSource[];
  } catch {
    // 信源列表加载失败时，导航博主子项为空，不阻塞页面
  }
});
</script>
