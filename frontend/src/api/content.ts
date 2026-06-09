import { apiClient } from "./client";
import type { ContentItem, ContentItemListResponse, SourceType } from "../types";

export const contentApi = {
  list(sourceType?: SourceType, cursor?: string | null, limit?: number) {
    const params = {
      ...(sourceType ? { source_type: sourceType } : {}),
      ...(cursor ? { cursor } : {}),
      ...(limit ? { limit } : {}),
    };
    return apiClient.get<ContentItem[] | ContentItemListResponse>("/content-items", { params });
  },
};
