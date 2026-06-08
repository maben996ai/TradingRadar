import { apiClient } from "./client";
import type { ContentItem, ContentItemListResponse } from "../types";

export const contentApi = {
  list(platform?: "youtube" | "twitter", cursor?: string | null, limit?: number) {
    const params = {
      ...(platform ? { platform } : {}),
      ...(cursor ? { cursor } : {}),
      ...(limit ? { limit } : {}),
    };
    return apiClient.get<ContentItem[] | ContentItemListResponse>("/content-items", { params });
  },
};
