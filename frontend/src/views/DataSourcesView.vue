<template>
  <section class="stack">
    <!-- 头部 + tab -->
    <div class="hero">
      <div>
        <p class="eyebrow">{{ t("dataSources.eyebrow") }}</p>
        <h2>{{ t("dataSources.title") }}</h2>
      </div>
      <div class="feed-filters">
        <button class="filter-btn" :class="{ active: activeTab === 'finance_news' }" @click="switchTab('finance_news')">{{ t("nav.financeNews") }}</button>
        <button class="filter-btn" :class="{ active: activeTab === 'twitter' }" @click="switchTab('twitter')">{{ t("nav.socialMedia") }}</button>
        <button class="filter-btn" :class="{ active: activeTab === 'youtube' }" @click="switchTab('youtube')">{{ t("nav.financeVideo") }}</button>
        <button class="filter-btn" :class="{ active: activeTab === 'macro_market' }" @click="switchTab('macro_market')">{{ t("nav.macroMarket") }}</button>
        <button class="filter-btn" :class="{ active: activeTab === 'finance_calendar' }" @click="switchTab('finance_calendar')">{{ t("nav.financeCalendar") }}</button>
      </div>
    </div>

    <!-- 新增表单（金融时讯/市场宏观/财经日历暂不支持 URL 解析，显示提示） -->
    <div class="panel add-form">
      <template v-if="isPlaceholderTab">
        <p class="muted">{{ t("dataSources.comingSoon") }}</p>
      </template>
      <template v-else>
        <form class="add-row" @submit.prevent="handleAdd">
          <input
            v-model="addUrl"
            class="add-input"
            type="url"
            :placeholder="t('dataSources.addPlaceholder')"
            :disabled="adding"
            required
          />
          <button class="btn" type="submit" :disabled="adding || !addUrl.trim()">
            {{ adding ? t("dataSources.adding") : t("dataSources.addButton") }}
          </button>
        </form>
        <p v-if="addError" class="error-msg">{{ t("dataSources.addError") }}</p>
      </template>
    </div>

    <!-- 列表（占位板块由上方表单区提示，不渲染列表） -->
    <template v-if="!isPlaceholderTab">
    <p v-if="loading" class="muted feed-state">{{ t("dataSources.loading") }}</p>
    <p v-else-if="fetchError" class="error-msg feed-state">{{ t("dataSources.fetchError") }}</p>
    <p v-else-if="visibleSources.length === 0" class="muted feed-state">{{ t("dataSources.empty") }}</p>

    <div v-else class="panel creator-list-panel">
      <div ref="sourceListScrollRef" class="creator-list-scroll">
        <div class="creator-list">
          <div v-for="s in pagedSources" :key="s.id" class="creator-row">
            <img v-if="s.avatar_url" :src="s.avatar_url" class="creator-row-avatar" :alt="s.name" referrerpolicy="no-referrer" />
            <div v-else class="creator-row-avatar creator-row-avatar-placeholder" />

            <div class="creator-row-info">
              <div class="creator-row-name-line">
                <a :href="s.profile_url" target="_blank" rel="noopener noreferrer" class="creator-row-name">
                  {{ s.name }}
                </a>
                <span class="platform-badge creator-inline-platform" :class="s.source_type">
                  {{ sourceTypeLabel(s.source_type) }}
                </span>
                <span v-if="!s.initialized_at" class="creator-init-badge">
                  <span class="creator-init-spinner" aria-hidden="true" />
                  {{ t("dataSources.initializing") }}
                </span>
                <span v-if="s.starred" class="starred-badge">★</span>
                <span v-if="s.category" class="category-tag">{{ s.category }}</span>
              </div>
              <p v-if="s.note" class="muted creator-row-note">{{ s.note }}</p>
            </div>

            <div class="creator-row-actions">
              <button class="btn-icon" :title="s.starred ? t('dataSources.unstar') : t('dataSources.starred')" @click="toggleStar(s)">
                {{ s.starred ? "★" : "☆" }}
              </button>
              <button class="btn-icon edit-btn" :title="t('dataSources.edit')" @click="startEdit(s)">✎</button>
              <button class="btn-icon delete-btn" :title="t('dataSources.delete')" @click="handleDelete(s.id)">✕</button>
            </div>
          </div>
        </div>
        <div v-if="canPaginateSources" class="pagination creator-pagination">
          <button class="filter-btn" :disabled="page === 1" @click="page--">{{ t("feed.prevPage") }}</button>
          <span class="muted page-indicator">{{ sourcePageLabel }}</span>
          <button class="filter-btn" :disabled="page >= totalSourcePages" @click="page++">{{ t("feed.nextPage") }}</button>
        </div>
      </div>
    </div>
    </template>

    <!-- 编辑弹层 -->
    <div v-if="editTarget" class="modal-backdrop" @click.self="editTarget = null">
      <div class="modal panel">
        <h3>{{ t("dataSources.editTitle") }}</h3>
        <div class="form">
          <div class="field">
            <label>{{ t("dataSources.notePlaceholder") }}</label>
            <input v-model="editNote" type="text" :placeholder="t('dataSources.notePlaceholder')" />
          </div>
          <div class="field">
            <label>{{ t("dataSources.categoryPlaceholder") }}</label>
            <input v-model="editCategory" type="text" :placeholder="t('dataSources.categoryPlaceholder')" />
          </div>
          <div class="field">
            <label>{{ t("dataSources.contentTypeLabel") }}</label>
            <select v-model="editContentType">
              <option value="video">{{ t("dataSources.tabVideos") }}</option>
              <option value="article">{{ t("dataSources.tabArticles") }}</option>
              <option value="news">{{ t("dataSources.tabNews") }}</option>
              <option value="market">{{ t("dataSources.tabMarket") }}</option>
            </select>
          </div>
          <div class="modal-actions">
            <button class="btn" @click="submitEdit">{{ t("dataSources.save") }}</button>
            <button class="btn btn-ghost" @click="editTarget = null">{{ t("dataSources.cancel") }}</button>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

import { dataSourcesApi } from "../api/data-sources";
import { useI18n } from "../i18n";
import type { ContentType, DataSource, SourceType } from "../types";

const { t } = useI18n();

type SourceTab = "twitter" | "youtube" | "finance_news" | "macro_market" | "finance_calendar";
const PLACEHOLDER_TABS: SourceTab[] = ["finance_news", "macro_market", "finance_calendar"];
const activeTab = ref<SourceTab>("twitter");
const dataSources = ref<DataSource[]>([]);
const loading = ref(false);
const fetchError = ref(false);
const page = ref(1);
const SOURCE_PAGE_SIZE = 8;
const sourceListScrollRef = ref<HTMLElement | null>(null);

const addUrl = ref("");
const adding = ref(false);
const addError = ref(false);

const editTarget = ref<DataSource | null>(null);
const editNote = ref("");
const editCategory = ref("");
const editContentType = ref<ContentType>("video");
let initPollTimer: number | null = null;

const isPlaceholderTab = computed(() => PLACEHOLDER_TABS.includes(activeTab.value));
const visibleSources = computed(() => {
  if (activeTab.value === "twitter") return dataSources.value.filter((s) => s.source_type === "twitter");
  if (activeTab.value === "youtube") return dataSources.value.filter((s) => s.source_type === "youtube");
  return [];
});
const totalSourcePages = computed(() => Math.max(1, Math.ceil(visibleSources.value.length / SOURCE_PAGE_SIZE)));
const pagedSources = computed(() => {
  const start = (page.value - 1) * SOURCE_PAGE_SIZE;
  return visibleSources.value.slice(start, start + SOURCE_PAGE_SIZE);
});
const canPaginateSources = computed(() => visibleSources.value.length > SOURCE_PAGE_SIZE);
const sourcePageLabel = computed(() => `${page.value} / ${totalSourcePages.value}`);

function clearInitPollTimer() {
  if (initPollTimer !== null) {
    window.clearTimeout(initPollTimer);
    initPollTimer = null;
  }
}

function scheduleInitPoll() {
  clearInitPollTimer();
  if (!dataSources.value.some((s) => !s.initialized_at)) return;
  initPollTimer = window.setTimeout(() => {
    fetchDataSources();
  }, 2000);
}

async function fetchDataSources() {
  loading.value = true;
  fetchError.value = false;
  try {
    const resp = await dataSourcesApi.list();
    dataSources.value = resp.data;
    if (page.value > totalSourcePages.value) {
      page.value = totalSourcePages.value;
    }
  } catch {
    fetchError.value = true;
  } finally {
    loading.value = false;
    scheduleInitPoll();
  }
}

function switchTab(tab: SourceTab) {
  // 数据已全量加载，切 tab 仅前端按平台过滤 + 重置页码，无需重新请求
  activeTab.value = tab;
  page.value = 1;
}

async function handleAdd() {
  addError.value = false;
  adding.value = true;
  try {
    // X 信源为帖子/短文，YouTube 为视频，按当前平台 tab 映射内容类型
    const contentTypeForTab: ContentType = activeTab.value === "twitter" ? "article" : "video";
    const resp = await dataSourcesApi.create({ url: addUrl.value.trim(), content_type: contentTypeForTab });
    dataSources.value.unshift(resp.data);
    page.value = 1;
    addUrl.value = "";
    scheduleInitPoll();
  } catch {
    addError.value = true;
  } finally {
    adding.value = false;
  }
}

async function handleDelete(id: string) {
  if (!confirm(t("dataSources.deleteConfirm"))) return;
  await dataSourcesApi.remove(id);
  dataSources.value = dataSources.value.filter((s) => s.id !== id);
  if (page.value > totalSourcePages.value) {
    page.value = totalSourcePages.value;
  }
}

async function toggleStar(source: DataSource) {
  const resp = await dataSourcesApi.patch(source.id, { starred: !source.starred });
  const idx = dataSources.value.findIndex((s) => s.id === source.id);
  if (idx !== -1) dataSources.value[idx] = resp.data;
}

function startEdit(source: DataSource) {
  editTarget.value = source;
  editNote.value = source.note ?? "";
  editCategory.value = source.category ?? "";
  editContentType.value = source.content_type;
}

async function submitEdit() {
  if (!editTarget.value) return;
  const resp = await dataSourcesApi.patch(editTarget.value.id, {
    note: editNote.value || null,
    category: editCategory.value || null,
    content_type: editContentType.value,
  });
  const idx = dataSources.value.findIndex((s) => s.id === editTarget.value!.id);
  if (idx !== -1) dataSources.value[idx] = resp.data;
  editTarget.value = null;
}

function sourceTypeLabel(type: SourceType): string {
  switch (type) {
    case "youtube": return t("dataSources.platformYoutube");
    case "twitter": return t("dataSources.platformTwitter");
    case "wechat_article": return t("dataSources.platformWechat");
    case "website": return t("dataSources.platformWebsite");
    case "rss": return "RSS";
    case "pdf": return "PDF";
  }
}

watch(page, async () => {
  await nextTick();
  if (sourceListScrollRef.value) {
    sourceListScrollRef.value.scrollTo({ top: 0, behavior: "smooth" });
  }
});

onMounted(fetchDataSources);
onBeforeUnmount(clearInitPollTimer);
</script>
