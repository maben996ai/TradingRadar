import { apiClient } from "./client";
import type { ResearchResolveResponse, ResearchSource, ResearchSourceResult } from "../types";

export const researchApi = {
  sources() {
    return apiClient.get<ResearchSource[]>("/research/sources");
  },
  resolve(ticker: string) {
    return apiClient.get<ResearchResolveResponse>("/research/resolve", { params: { ticker } });
  },
  searchSource(ticker: string, sourceKey: string) {
    return apiClient.get<ResearchSourceResult>("/research/search", {
      params: { ticker, source_key: sourceKey },
    });
  },
};
