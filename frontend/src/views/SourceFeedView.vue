<template>
  <section class="stack">
    <div class="hero">
      <div class="author-hero-info">
        <RouterLink to="/" class="back-link">{{ t("feed.backToFeed") }}</RouterLink>
        <div class="author-hero-identity">
          <img v-if="sourceAvatar" :src="sourceAvatar" class="creator-avatar-lg" :alt="sourceName" referrerpolicy="no-referrer" />
          <div v-else class="creator-avatar-lg creator-avatar-placeholder" />
          <div>
            <p class="eyebrow">{{ sourceType }}</p>
            <h2>{{ sourceName }}</h2>
          </div>
        </div>
      </div>
    </div>

    <p v-if="feedStore.loading" class="muted feed-state">{{ t("feed.loading") }}</p>
    <p v-else-if="!sourceVideos.length" class="muted feed-state">{{ t("feed.empty") }}</p>

    <template v-else>
      <!-- 社交媒体：folo 风格 timeline 文本流 -->
      <div v-if="isSocial" class="social-timeline">
        <article v-for="post in pagedVideos" :key="post.id" class="social-post">
          <img v-if="sourceAvatar" :src="sourceAvatar" class="social-avatar" :alt="sourceName" referrerpolicy="no-referrer" />
          <div v-else class="social-avatar social-avatar-placeholder" />
          <div class="social-body">
            <div class="social-head">
              <span class="social-author">{{ sourceName }}</span>
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
            <!-- 引用推文：展示被引用原帖的完整内容 -->
            <a
              v-if="post.quoted"
              :href="post.quoted.url ?? undefined"
              target="_blank"
              rel="noopener noreferrer"
              class="social-quote"
              :class="{ collapsed: isCollapsed(post) }"
            >
              <div class="social-quote-head">
                <img
                  v-if="post.quoted.author_avatar_url"
                  :src="post.quoted.author_avatar_url"
                  class="social-quote-avatar"
                  :alt="post.quoted.author_name"
                  referrerpolicy="no-referrer"
                />
                <span class="social-quote-author">{{ post.quoted.author_name }}</span>
                <span v-if="post.quoted.author_username" class="social-quote-handle">@{{ post.quoted.author_username }}</span>
              </div>
              <p v-if="post.quoted.text" class="social-quote-text">{{ post.quoted.text }}</p>
              <div v-if="post.quoted.thumbnail_url" class="social-quote-media-frame">
                <img
                  :src="post.quoted.thumbnail_url"
                  class="social-quote-media"
                  :alt="post.quoted.text"
                  loading="lazy"
                  referrerpolicy="no-referrer"
                  @click.prevent.stop="lightboxUrl = post.quoted.thumbnail_url"
                />
              </div>
            </a>
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

      <!-- 财经视频等：网格卡片 -->
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
            <button
              v-if="isYoutube"
              type="button"
              class="video-download-btn"
              :disabled="downloadingId === video.id || !caDepsReady"
              :title="caMissingDeps.length ? `${t('contentAnalysis.depsMissing')}: ${caMissingDeps.join(', ')}` : ''"
              @click.prevent.stop="onDownload(video.id)"
            >
              {{ downloadingId === video.id ? "…" : t("feed.downloadToAnalysis") }}
            </button>
          </div>
        </a>
      </div>

      <!-- 下载/转写：成功/失败三态提示 -->
      <div v-if="downloadMsg" class="download-toast" :class="downloadOk ? 'ok' : 'err'">
        <span>{{ downloadMsg }}</span>
        <RouterLink v-if="downloadOk" to="/content-analysis" class="download-toast-link">
          {{ t("feed.goToAnalysis") }}
        </RouterLink>
      </div>

      <div v-if="totalPages > 1" class="pagination">
        <button class="filter-btn" :disabled="page === 1" @click="page--">{{ t("feed.prevPage") }}</button>
        <span class="muted page-indicator">{{ page }} / {{ totalPages }}</span>
        <button class="filter-btn" :disabled="page === totalPages" @click="page++">{{ t("feed.nextPage") }}</button>
      </div>
    </template>

    <!-- 图片大图预览 -->
    <div v-if="lightboxUrl" class="lightbox" @click="lightboxUrl = null">
      <img :src="lightboxUrl" class="lightbox-img" alt="" referrerpolicy="no-referrer" />
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { RouterLink, useRoute } from "vue-router";

import { contentAnalysisApi } from "../api/contentAnalysis";
import { useI18n } from "../i18n";
import { useFeedStore } from "../stores/feed";
import type { AnalysisStatus, ContentItem } from "../types";
import { formatPublishedAt } from "../utils/datetime";
import { formatDuration } from "../utils/duration";

const { t } = useI18n();
const route = useRoute();
const feedStore = useFeedStore();

const PAGE_SIZE = 15;
const page = ref(1);
const lightboxUrl = ref<string | null>(null);

const sourceId = computed(() => route.params.sourceId as string);

const sourceVideos = computed(() =>
  feedStore.videos
    .filter((v) => v.data_source_id === sourceId.value)
    .sort((a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime())
);

const sourceName = computed(() => sourceVideos.value[0]?.data_source_name ?? "");
const sourceAvatar = computed(() => sourceVideos.value[0]?.data_source_avatar_url ?? null);
const sourceType = computed(() => sourceVideos.value[0]?.source_type ?? "");
const isSocial = computed(() => sourceType.value === "twitter");
const isYoutube = computed(() => sourceType.value === "youtube");

// YouTube 视频卡片「下载/转写」三态反馈
const downloadingId = ref<string | null>(null);
const downloadMsg = ref("");
const downloadOk = ref(true);
let downloadMsgTimer: number | undefined;

// 下载依赖（yt-dlp/ffmpeg）缺失时禁用入口，避免点了之后后台静默报错。
const caStatus = ref<AnalysisStatus | null>(null);
const caMissingDeps = computed<string[]>(() => {
  const s = caStatus.value;
  if (!s) return [];
  const missing: string[] = [];
  if (!s.yt_dlp_available) missing.push("yt-dlp");
  if (!s.ffmpeg_available) missing.push("ffmpeg");
  return missing;
});
const caDepsReady = computed(() => !!caStatus.value && caMissingDeps.value.length === 0);

async function onDownload(contentItemId: string) {
  if (downloadingId.value) return;
  downloadingId.value = contentItemId;
  downloadMsg.value = "";
  try {
    await contentAnalysisApi.fromContentItem(contentItemId, "video");
    downloadOk.value = true;
    downloadMsg.value = t("feed.downloadQueued");
  } catch {
    downloadOk.value = false;
    downloadMsg.value = t("feed.downloadFailed");
  } finally {
    downloadingId.value = null;
    if (downloadMsgTimer) window.clearTimeout(downloadMsgTimer);
    downloadMsgTimer = window.setTimeout(() => {
      downloadMsg.value = "";
    }, 6000);
  }
}

// 过长推文默认折叠，点击「显示更多」展开
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

const totalPages = computed(() => Math.max(1, Math.ceil(sourceVideos.value.length / PAGE_SIZE)));
const pagedVideos = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE;
  return sourceVideos.value.slice(start, start + PAGE_SIZE);
});

onMounted(async () => {
  if (!feedStore.videos.length) feedStore.fetchVideos();
  // 拉取内容分析依赖可用性，用于禁用「下载/转写」入口。
  try {
    caStatus.value = (await contentAnalysisApi.status()).data;
  } catch {
    caStatus.value = null;
  }
});
</script>

<style scoped>
.video-download-btn {
  margin-top: 0.5rem;
  width: 100%;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--accent, #2563eb);
  border-radius: 8px;
  background: transparent;
  color: var(--accent, #2563eb);
  font-size: 0.82rem;
  font-weight: 600;
  cursor: pointer;
}
.video-download-btn:hover:not(:disabled) {
  background: rgba(37, 99, 235, 0.1);
}
.video-download-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.download-toast {
  position: fixed;
  left: 50%;
  bottom: 1.6rem;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 0.8rem;
  padding: 0.7rem 1.2rem;
  border-radius: 10px;
  color: #fff;
  font-size: 0.88rem;
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.2);
  z-index: 60;
}
.download-toast.ok {
  background: #16a34a;
}
.download-toast.err {
  background: #dc2626;
}
.download-toast-link {
  color: #fff;
  text-decoration: underline;
  font-weight: 600;
}
</style>
