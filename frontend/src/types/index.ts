export type ContentType = "video" | "article" | "news" | "market";

export type SourceType =
  | "bilibili"
  | "youtube"
  | "twitter"
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
  duration_seconds?: number | null;
  data_source_name: string;
  data_source_avatar_url?: string | null;
}

export interface ContentItemListResponse {
  items: ContentItem[];
  next_cursor: string | null;
  has_more: boolean;
}
