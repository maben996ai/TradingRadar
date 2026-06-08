import { apiClient } from "./client";
import type { MacroDashboardResponse } from "../types";

export const macroApi = {
  indicators() {
    return apiClient.get<MacroDashboardResponse>("/macro/indicators");
  },
  refresh() {
    return apiClient.post<{ inserted: number }>("/macro/refresh");
  },
};
