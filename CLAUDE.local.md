# CLAUDE.local.md — 开发进度记录

## 当前状态（2026-04-19）

### 已完成
- Feed 页 CSS 5 列网格（`.video-grid-sm`）Vite 缓存问题已修复（`docker compose restart frontend`）
- 前端导航与文案调整：
  - 标题：「投资信号驾驶舱」→「金融资讯」
  - 导航「动态」→「最新内容动态」
  - 导航「创作者」→「信源管理」
  - 「抓取日志」+「设置」合并为「控制中心」（`/control-center`，`ControlCenterView.vue`）
  - 新增「内容分析」导航入口（`/content-analysis`，`ContentAnalysisView.vue`，占位页面）
  - Feed 每页从 20 改为 15（5×3 网格，便于翻页验证）

### 已修改文件
| 文件 | 改动 |
|---|---|
| `frontend/src/i18n.ts` | nav.title/feed/creators 文案；新增 nav.controlCenter/contentAnalysis key；新增 contentAnalysis.* 消息块；更新 MessageKey 类型 |
| `frontend/src/views/FeedView.vue` | PAGE_SIZE 20→15 |
| `frontend/src/components/layout/AppShell.vue` | 导航链接调整为 /content-analysis 和 /control-center |
| `frontend/src/router/index.ts` | 路由替换：settings+crawl-logs → control-center+content-analysis |
| `frontend/src/views/ControlCenterView.vue` | 新建，合并 settings+crawlLogs 内容 |
| `frontend/src/views/ContentAnalysisView.vue` | 新建，占位页面 |

### 待验证
- 刷新浏览器确认 5 列网格正常（上次 Vite 已重启）
- 确认新导航路由均可访问（/content-analysis, /control-center）
- 确认翻页功能（15 条/页）

### 下一步主线
1. 打通飞书 Webhook 通知（控制中心配置表单）
2. 内容分析页接入大模型（视频摘要/投研洞察）
3. 控制中心展示真实抓取日志

## 开发环境注意事项

### 前端重启用 `up -d`，不要用 `restart`
- macOS Docker Desktop 上 `docker compose restart frontend` 偶发 bind-mount（`./frontend:/app`）未正确重挂，容器内 `/app/package.json` 瞬时不可见，`npm run dev` 立即 ENOENT 退出（退出码 254），表现为 `http://localhost:3000` 无法访问。
- 正确做法：`docker compose up -d frontend`（复用未变更镜像，仅重建容器，重新建立挂载）。
- 同理，删除/新增前端文件（如 `videos.ts`→`content.ts`）后，Vite 缓存偶尔不干净，也优先用 `up -d` 重建而非 `restart`。

## 进度（2026-06-08）：video → content_item 通用化改名

将「视频」专用模型泛化为通用内容模型（X 推文等非视频内容不再借用 video 字段）。后端 167 测试全过、ruff 通过；前端 type-check 通过。

- 模型：`Video`→`ContentItem`，表 `videos`→`content_items`，列 `platform_video_id`→`platform_id`、`video_url`→`content_url`，`CrawlLog.videos_found`→`items_found`
- 采集层：`CrawledVideo`→`CrawledItem`，方法 `fetch_latest_videos`→`fetch_latest_items`
- 对外契约：路由 `/api/videos`→`/api/content-items`，`app/api/videos.py`→`content_items.py`；schema `VideoResponse/VideoListResponse`→`ContentItemResponse/ContentItemListResponse`
- 前端：`api/videos.ts`→`content.ts`（`contentApi`，endpoint `/content-items`）、`types` 接口与字段、store/views 引用对齐；局部变量/CSS 类名/i18n 文案未改
- 迁移：`a7c3f1e29b84`（表/列/约束/索引/`items_found`）+ `b8d4e2f6a1c0`（主键 `videos_pkey`→`content_items_pkey`），均已 `alembic upgrade head` 应用到本地 PG，数据保留
- content_type 仍由用户在添加信源时通过 payload 选择（payload 驱动，未改）

## 进度（2026-06-08）：导航重构 + 社交媒体内容流

后端 168 测试通过、ruff 通过；前端 type-check 通过。

- **首次抓取失败可观测**：`_run_initial_crawl` 失败时除 warning 外，写一条 `CrawlLog(status=FAILED)`，避免信源一直停在「初始化中」（修复 X 限流 429 时的盲区）。
- **信源管理页**：tab 从「内容类型」改为「平台/板块」维度，5 个板块统一为 `金融时讯 / 社交媒体 / 财经视频 / 市场宏观 / 财经日历`；社交媒体(twitter)、财经视频(youtube)可添加，其余为占位。
- **左侧导航**：精简为「信源 / 分析 / 控制中心」三个一级 tab（放大字号，控制中心提升为一级）。信源段做成可展开树：社交媒体/财经视频展开为**真实订阅博主**（来自 `dataSourcesApi.list()`，点博主进 `SourceFeedView`），金融时讯/市场宏观/财经日历展开为静态占位分类。
- **聚合页下线**：删除 `FeedView.vue`（聚合信息流），新增 `PlatformFeedView.vue`（按平台过滤，`/feed/:platform`），`/` 默认重定向 `/feed/twitter`。
- **社交媒体 timeline（folo 风格）**：`SourceFeedView` 按 `source_type` 分流——twitter 用文本流（头像+作者+时间+正文），长推文折叠 6 行 + 「显示更多」；youtube 保持视频网格。
- **完整正文**：`ContentItemResponse` 新增 `content_text`（从 `raw_data.text` 取完整推文，回退 `title`）；前端 timeline 用之。
- **图片 lightbox**：推文配图点击打开全屏大图预览（点背景关闭），不再跳转 X；「查看原文」链接保留。
- 清理：删除多个 unused i18n key 与 `FeedView`；新增板块/静态分类/`showMore` 等 i18n（中英）。
