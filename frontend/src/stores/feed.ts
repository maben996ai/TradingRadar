import { defineStore } from "pinia";
import { ref } from "vue";

import { contentApi } from "../api/content";
import type { ContentItem, ContentItemListResponse } from "../types";

const API_PAGE_SIZE = 15;

function isContentItemListResponse(
  data: ContentItem[] | ContentItemListResponse,
): data is ContentItemListResponse {
  return !Array.isArray(data) && Array.isArray(data.items);
}

export const useFeedStore = defineStore("feed", () => {
  const videos = ref<ContentItem[]>([]);
  const loading = ref(false);
  const loadingMore = ref(false);
  const error = ref<string | null>(null);
  const nextCursor = ref<string | null>(null);
  const hasMore = ref(true);

  function mergeVideos(incoming: ContentItem[]) {
    const byId = new Map(videos.value.map((video) => [video.id, video]));
    for (const video of incoming) {
      byId.set(video.id, video);
    }
    videos.value = [...byId.values()];
  }

  async function fetchNextPage() {
    if (loadingMore.value) return;
    if (!hasMore.value && videos.value.length > 0) return;

    loadingMore.value = true;
    try {
      const resp = await contentApi.list(undefined, nextCursor.value, API_PAGE_SIZE);
      const data = isContentItemListResponse(resp.data)
        ? resp.data
        : { items: resp.data, next_cursor: null, has_more: false };
      mergeVideos(data.items);
      nextCursor.value = data.next_cursor;
      hasMore.value = data.has_more;
    } finally {
      loadingMore.value = false;
    }
  }

  async function fetchVideos(initialPages = 3) {
    loading.value = true;
    error.value = null;
    videos.value = [];
    nextCursor.value = null;
    hasMore.value = true;
    try {
      for (let i = 0; i < initialPages; i += 1) {
        await fetchNextPage();
        if (!hasMore.value) break;
      }
    } catch {
      error.value = "fetch_failed";
      videos.value = [];
      nextCursor.value = null;
      hasMore.value = false;
    } finally {
      loading.value = false;
    }
  }

  async function ensureVideoCount(count: number) {
    while (videos.value.length < count && hasMore.value) {
      await fetchNextPage();
    }
  }

  return { videos, loading, loadingMore, error, hasMore, fetchVideos, fetchNextPage, ensureVideoCount };
});
