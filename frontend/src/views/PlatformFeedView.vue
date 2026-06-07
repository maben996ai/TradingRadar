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
        <div class="video-grid-sm">
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
              <span class="platform-badge" :class="video.source_type">{{ video.source_type }}</span>
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
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute } from "vue-router";

import { useI18n } from "../i18n";
import { useFeedStore } from "../stores/feed";
import { formatPublishedAt } from "../utils/datetime";
import { formatDuration } from "../utils/duration";

const { t } = useI18n();
const route = useRoute();
const feedStore = useFeedStore();

const PAGE_SIZE = 15;
const page = ref(1);

const platform = computed(() => (route.params.platform as string) ?? "twitter");

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

// 切换平台时重置分页
watch(platform, () => {
  page.value = 1;
});

onMounted(() => {
  if (!feedStore.videos.length) feedStore.fetchVideos();
});
</script>
