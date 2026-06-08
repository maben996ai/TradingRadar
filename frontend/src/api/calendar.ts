import { apiClient } from "./client";
import type {
  CalendarCategory,
  CalendarEventListResponse,
  TrackedTicker,
} from "../types";

export interface CalendarQuery {
  start: string; // ISO UTC
  end: string; // ISO UTC
  categories?: CalendarCategory[];
  importance?: number;
  kind?: "macro" | "earnings";
  trackedOnly?: boolean;
}

export const calendarApi = {
  events(q: CalendarQuery) {
    const p = new URLSearchParams();
    p.set("start", q.start);
    p.set("end", q.end);
    for (const c of q.categories ?? []) p.append("categories", c);
    if (q.importance) p.set("importance", String(q.importance));
    if (q.kind) p.set("kind", q.kind);
    if (q.trackedOnly) p.set("tracked_only", "true");
    return apiClient.get<CalendarEventListResponse>(`/calendar/events?${p.toString()}`);
  },
  refresh() {
    return apiClient.post<{ inserted: number }>("/calendar/refresh");
  },
  trackedTickers() {
    return apiClient.get<TrackedTicker[]>("/calendar/tracked-tickers");
  },
  addTicker(ticker: string, companyName?: string) {
    return apiClient.post<TrackedTicker>("/calendar/tracked-tickers", {
      ticker,
      company_name: companyName ?? null,
    });
  },
  removeTicker(id: string) {
    return apiClient.delete(`/calendar/tracked-tickers/${id}`);
  },
};
