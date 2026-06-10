import { apiClient } from "./client";
import type { FundamentalsDownloadResponse, FundamentalsSource } from "../types";

// 下载可能较慢（SEC 10-K 等大文件），关闭默认 10s 超时
const NO_TIMEOUT = { timeout: 0 } as const;

export const fundamentalsApi = {
  sources() {
    return apiClient.get<FundamentalsSource[]>("/fundamentals/sources");
  },
  download(ticker: string, sources?: string[]) {
    return apiClient.post<FundamentalsDownloadResponse>(
      "/fundamentals/download",
      { ticker, sources: sources && sources.length ? sources : null },
      NO_TIMEOUT,
    );
  },
  async downloadFile(path: string, filename: string) {
    const resp = await apiClient.get("/fundamentals/files", {
      params: { path },
      responseType: "blob",
      ...NO_TIMEOUT,
    });
    const url = URL.createObjectURL(resp.data as Blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
};
