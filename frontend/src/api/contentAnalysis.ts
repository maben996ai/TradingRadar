import { apiClient } from "./client";
import type {
  AnalysisActionResponse,
  AnalysisArtifact,
  AnalysisListResponse,
  AnalysisStatus,
} from "../types";

// 下载/转写为长耗时任务，关闭默认 10s 超时
const NO_TIMEOUT = { timeout: 0 } as const;

export const contentAnalysisApi = {
  status() {
    return apiClient.get<AnalysisStatus>("/content-analysis/status");
  },
  list(type?: string) {
    return apiClient.get<AnalysisListResponse>("/content-analysis/artifacts", {
      params: type ? { type } : undefined,
    });
  },
  download(url: string, mode: "video" | "audio") {
    return apiClient.post<AnalysisArtifact>(
      "/content-analysis/download",
      { url, mode },
      NO_TIMEOUT,
    );
  },
  transcribe(artifactId: string) {
    return apiClient.post<AnalysisArtifact>(
      `/content-analysis/artifacts/${artifactId}/transcribe`,
      {},
      NO_TIMEOUT,
    );
  },
  cancel(artifactId: string) {
    return apiClient.post<AnalysisActionResponse>(
      `/content-analysis/artifacts/${artifactId}/cancel`,
    );
  },
  deleteArtifact(artifactId: string, deleteFile = false) {
    return apiClient.delete<AnalysisActionResponse>(
      `/content-analysis/artifacts/${artifactId}`,
      { params: { delete_file: deleteFile } },
    );
  },
  deleteSource(sourceId: string, deleteFiles = false) {
    return apiClient.delete<AnalysisActionResponse>(
      `/content-analysis/sources/${sourceId}`,
      { params: { delete_files: deleteFiles } },
    );
  },
  loginCookies(cookies: string) {
    return apiClient.post<AnalysisActionResponse>(
      "/content-analysis/login/cookies",
      { cookies },
      NO_TIMEOUT,
    );
  },
  fileUrl(artifactId: string) {
    return `/api/content-analysis/artifacts/${artifactId}/file`;
  },
  async fetchText(artifactId: string): Promise<string> {
    const resp = await apiClient.get(
      `/content-analysis/artifacts/${artifactId}/file`,
      { responseType: "text", ...NO_TIMEOUT },
    );
    return resp.data as string;
  },
};
