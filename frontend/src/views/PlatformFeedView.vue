<template>
  <section class="stack">
    <div class="hero">
      <div>
        <p class="eyebrow">{{ t("dataSources.eyebrow") }}</p>
        <h2>{{ platformLabel }}</h2>
      </div>
    </div>

    <template v-if="isPlaceholder">
      <p class="muted feed-state">{{ t("dataSources.comingSoon") }}</p>
    </template>
    <template v-else>
      <p v-if="feedStore.loading" class="muted feed-state">{{ t("feed.loading") }}</p>
      <p v-else-if="!platformVideos.length" class="muted feed-state">{{ t("feed.empty") }}</p>

      <template v-else>
        <div v-if="isSocial" class="social-timeline">
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

const platform = computed(() => (route.params.platform as string) ?? "twitter");
const isSocial = computed(() => platform.value === "twitter");

const PLACEHOLDER_PLATFORMS = ["finance_news", "macro_market", "finance_calendar"];
const isPlaceholder = computed(() => PLACEHOLDER_PLATFORMS.includes(platform.value));

const platformLabel = computed(() => {
  switch (platform.value) {
    case "twitter": return t("nav.socialMedia");
    case "youtube": return t("nav.financeVideo");
    case "finance_news": return t("nav.financeNews");
    case "macro_market": return t("nav.macroMarket");
    case "finance_calendar": return t("nav.financeCalendar");
    default: return platform.value;
  }
});

const platformVideos = computed(() =>
  feedStore.videos
    .filter((v) => v.source_type === platform.value)
    .sort((a, b) => new Date(b.published_at).getTime() - new Date(a.published_at).getTime())
);

const totalPages = computed(() => Math.max(1, Math.ceil(platformVideos.value.length / PAGE_SIZE)));
const pagedVideos = computed(() => {
  const start = (page.value - 1) * PAGE_SIZE;
  return platformVideos.value.slice(start, start + PAGE_SIZE);
});

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

onMounted(() => {
  if (!feedStore.videos.length) feedStore.fetchVideos();
});
</script>
