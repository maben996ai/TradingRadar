import { apiClient } from "./client";
import type {
  AnalysisActionResponse,
  AnalysisArtifact,
  AnalysisDeletedSource,
  AnalysisListResponse,
  AnalysisProbeResponse,
  AnalysisStatus,
} from "../types";

// 下载/转写为长耗时任务，关闭默认 10s 超时
const NO_TIMEOUT = { timeout: 0 } as const;

export const contentAnalysisApi = {
  status() {
    return apiClient.get<AnalysisStatus>("/content-analysis/status");
  },
  list(type?: string, q?: string) {
    const params: Record<string, string> = {};
    if (type) params.type = type;
    if (q) params.q = q;
    return apiClient.get<AnalysisListResponse>("/content-analysis/artifacts", {
      params: Object.keys(params).length ? params : undefined,
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
  reveal(artifactId: string) {
    return apiClient.post<AnalysisActionResponse>(
      `/content-analysis/artifacts/${artifactId}/reveal`,
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
  deleteSource(sourceId: string, purge = false) {
    // purge=false：软删除（移入回收站）；purge=true：彻底删除来源与文件。
    return apiClient.delete<AnalysisActionResponse>(
      `/content-analysis/sources/${sourceId}`,
      { params: { purge } },
    );
  },
  deletedSources() {
    return apiClient.get<AnalysisDeletedSource[]>(
      "/content-analysis/sources/deleted",
    );
  },
  restoreSource(sourceId: string) {
    return apiClient.post<AnalysisActionResponse>(
      `/content-analysis/sources/${sourceId}/restore`,
    );
  },
  purgeSource(sourceId: string) {
    return apiClient.post<AnalysisActionResponse>(
      `/content-analysis/sources/${sourceId}/purge`,
    );
  },
  fromContentItem(contentItemId: string, mode: "video" | "audio" = "video") {
    return apiClient.post<AnalysisArtifact>(
      `/content-analysis/from-content-item/${contentItemId}`,
      { mode },
      NO_TIMEOUT,
    );
  },
  loginBrowser(browser: string, profile?: string) {
    return apiClient.post<AnalysisActionResponse>(
      "/content-analysis/login/browser",
      { browser, profile: profile || null },
      NO_TIMEOUT,
    );
  },
  probe() {
    return apiClient.post<AnalysisProbeResponse>(
      "/content-analysis/login/probe",
      {},
      NO_TIMEOUT,
    );
  },
  logout() {
    return apiClient.post<AnalysisActionResponse>("/content-analysis/logout");
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
