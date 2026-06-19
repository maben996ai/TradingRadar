## Why

TradingRadar 的「内容分析」（前端 `ContentAnalysisView`）目前是占位页面。现有独立项目 `yt-dlp-x` 已实现一套可用的"YouTube 内容拉取 → 音视频下载 → Whisper 转写文本 → 产物血缘管理"能力，正好可作为投研分析中"内容分析"的输入来源（把视频/播客转成可分析的文本）。本变更将该后端能力以 TradingRadar 的分层规范重写接入，作为内容分析的第一个子模块。

## What Changes

- 新增内容分析能力：用户粘贴 YouTube URL → 下载音/视频 → 转写为文本，并以"来源(Source) → 产物(Artifact)"模型管理全过程（进度、状态、用时、报错、血缘）。
- 移植 `yt-dlp-x` 后端逻辑（`downloader.py` / `transcriber.py` / `store.py` / `app.py` 路由）到 TradingRadar 后端，遵循 `api/` + `services/` + `models/` 分层。
- 产物状态从源项目的 `data/store.json` **迁移为 Postgres 模型**（Source / Artifact），多用户隔离，新增 Alembic 迁移。
- 下载/转写为长耗时任务，由 FastAPI 后台任务（或工作线程）驱动，前端可轮询进度。
- YouTube 登录受限内容沿用 **cookies** 方案（移植 cookies 登录/浏览器导入能力）。
- 入口为**粘贴 URL 独立分析**，与现有 content-collection 的已采集内容解耦（本次不打通已采集内容的一键转写）。

## Capabilities

### New Capabilities
- `content-analysis`: 粘贴 YouTube URL 下载音/视频、Whisper 转写文本、以来源→产物模型管理产物（列出/获取/取消/删除）及 YouTube cookies 登录与转写后端可用性查询。

### Modified Capabilities
<!-- 无：与现有能力解耦，不修改 content-collection 等既有规格 -->

## Impact

- 后端新增：`app/api/content_analysis.py`、`app/services/content_analysis/`（downloader/transcriber/store 重写）、`app/models/models.py` 新增 Source/Artifact 模型、Alembic 迁移、`main.py` 注册 `/api/content-analysis` 路由。
- 配置：新增 yt-dlp / whisper 相关配置（下载根目录、whisper 后端选择、PO token / cookies），同步 `config.py` 与 `.env.example`。
- 依赖：后端新增 `yt-dlp`、Whisper 后端（`mlx-whisper` 或 `openai-whisper`），运行需 `ffmpeg`；`requirements.txt` 更新。
- 前端：`ContentAnalysisView` 从占位页改为真实功能页（URL 输入、产物管理、进度展示、文本查看）；新增 `api/contentAnalysis.ts`、类型与 i18n。
- 不影响：authentication / source-management / content-collection 等既有能力的规格与行为。
- 风险：长耗时任务与外部依赖（YouTube 风控、ffmpeg、whisper 模型体积）带来部署与稳定性复杂度，详见 design。
