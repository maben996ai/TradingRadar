export type ContentType = "video" | "article" | "news" | "market";

export type SourceType =
  | "youtube"
  | "twitter"
  | "finance_news"
  | "wechat_article"
  | "website"
  | "rss"
  | "pdf";

export interface DataSource {
  id: string;
  name: string;
  source_type: SourceType;
  external_id: string;
  profile_url: string;
  avatar_url?: string | null;
  note?: string | null;
  category?: string | null;
  content_type: ContentType;
  starred: boolean;
  notifications_enabled: boolean;
  initialized_at?: string | null;
  created_at: string;
  source_config?: Record<string, unknown> | null;
}

export interface QuotedContent {
  text: string;
  author_name: string;
  author_username: string;
  author_avatar_url?: string | null;
  thumbnail_url?: string | null;
  url?: string | null;
}

export interface ContentItem {
  id: string;
  data_source_id: string;
  platform_id: string;
  source_type: SourceType;
  title: string;
  content_text: string;
  thumbnail_url?: string | null;
  content_url: string;
  published_at: string;
  raw_data?: Record<string, unknown> | null;
  quoted?: QuotedContent | null;
  duration_seconds?: number | null;
  data_source_name: string;
  data_source_avatar_url?: string | null;
  data_source_external_id: string;
}

export interface ResearchSource {
  key: string;
  name: string;
}

export interface ResearchResolveResponse {
  ticker: string;
  company_name: string;
  lookback_days: number;
}

export interface ResearchItem {
  title: string;
  url: string;
  meta: string;
  published_at: string | null;
}

export interface ResearchSourceResult {
  items: ResearchItem[];
  error: string | null;
}

export interface ContentItemListResponse {
  items: ContentItem[];
  next_cursor: string | null;
  has_more: boolean;
}

export type MacroJudgment = "bullish" | "neutral" | "bearish";

export type MacroZone = "high" | "normal" | "low";

export type MacroCategory =
  | "rates"
  | "inflation"
  | "growth"
  | "employment"
  | "liquidity"
  | "risk";

export interface MacroPoint {
  date: string;
  value: number;
}

export interface MacroIndicator {
  key: string;
  category: MacroCategory;
  name: string;
  name_en: string;
  unit_label: string;
  decimals: number;
  source: string;
  explanation: string;
  latest: number;
  previous: number | null;
  change_abs: number | null;
  change_pct: number | null;
  updated_at: string;
  judgment: MacroJudgment;
  reason: string;
  high: number | null;
  low: number | null;
  high_note: string;
  low_note: string;
  zone: MacroZone;
  forecast: number | null;
  forecast_label: string | null;
  forecast_source: string | null;
  series: MacroPoint[];
}

export interface MacroDashboardResponse {
  indicators: MacroIndicator[];
}

export type CalendarKind = "macro" | "earnings";

export type CalendarCategory =
  | "inflation"
  | "employment"
  | "rates"
  | "growth"
  | "earnings";

export interface CalendarEvent {
  id: string;
  event_key: string;
  kind: CalendarKind;
  category: CalendarCategory;
  title: string;
  title_en: string;
  country: string;
  scheduled_at: string;
  all_day: boolean;
  importance: number;
  impact_assets: string | null;
  previous: number | null;
  forecast: number | null;
  actual: number | null;
  value_unit: string | null;
  ticker: string | null;
  company_name: string | null;
  source: string;
}

export interface CalendarEventListResponse {
  events: CalendarEvent[];
}

export interface TrackedTicker {
  id: string;
  ticker: string;
  company_name: string | null;
  created_at: string;
}

export interface FundamentalsSource {
  name: string;
}

export interface FundamentalsArtifact {
  source: string;
  doc_type: string;
  title: string;
  file_path: string;
  url: string | null;
  period: string | null;
  bytes_written: number;
}

export interface FundamentalsSourceResult {
  source: string;
  skipped: boolean;
  message: string | null;
  artifacts: FundamentalsArtifact[];
}

export interface FundamentalsDownloadResponse {
  ticker: string;
  results: FundamentalsSourceResult[];
}

// 内容分析（yt-dlp 下载 + Whisper 转写）
export type AnalysisArtifactType = "video" | "audio" | "text";
export type AnalysisArtifactStatus =
  | "queued"
  | "running"
  | "processing"
  | "finished"
  | "error"
  | "canceled";

export interface AnalysisArtifact {
  id: string;
  type: AnalysisArtifactType;
  stage: string;
  status: AnalysisArtifactStatus;
  progress: number;
  filename: string | null;
  size: number | null;
  error: string | null;
  source_artifact_id: string | null;
  meta: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface AnalysisSource {
  id: string;
  url: string;
  title: string;
  author: string | null;
  created_at: string;
  artifacts: AnalysisArtifact[];
}

export interface AnalysisListResponse {
  sources: AnalysisSource[];
  counts: Record<string, number>;
}

export interface AnalysisStatus {
  transcribe_available: boolean;
  transcribe_backend: string;
  youtube_logged_in: boolean;
  cookies_present: boolean;
}

export interface AnalysisActionResponse {
  ok: boolean;
  message: string | null;
}

// cookies 活体探测三态：已登录 / 已失效 / 无法判定
export type AnalysisProbeState = "logged_in" | "logged_out" | "inconclusive";

export interface AnalysisProbeResponse {
  state: AnalysisProbeState;
  ok: boolean;
  message: string | null;
}

// 回收站条目：已软删除的来源
export interface AnalysisDeletedSource {
  id: string;
  url: string;
  title: string;
  author: string | null;
  created_at: string;
  deleted_at: string | null;
}
