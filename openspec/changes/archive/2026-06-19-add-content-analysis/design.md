## Context

源项目 `yt-dlp-x`（`/Users/maben996/Projects/yt-dlp-x`）是 Flask 单体：
- `downloader.py`：`ThreadPoolExecutor` 跑 yt-dlp，`progress_hooks` 回写进度；支持 cookies 与 PO token；下载完可自动转写。
- `transcriber.py`：Whisper 后端自动选择（Apple Silicon 优先 `mlx-whisper`，回退 `openai-whisper`），从音/视频产物转出 text。
- `store.py`：内存 + `data/store.json` 持久化；数据模型 `Source → Artifact(type=video/audio/text, stage, status, progress, filepath, size, started_at/finished_at, error, error_log, source_artifact 血缘, meta)`；首启自动导入磁盘已有文件。
- `app.py`：JSON API（download / transcribe / list / file / cancel / reveal / delete source/artifact）+ cookies 登录。

TradingRadar 后端是 FastAPI + SQLAlchemy async + Postgres + Alembic + APScheduler，单用户隔离贯穿全部业务接口。本设计解决"如何把 Flask 同步线程池 + JSON 文件存储的能力，重写为符合 TradingRadar 分层与多用户模型的内容分析能力"。

## Goals / Non-Goals

**Goals:**
- 把下载/转写/产物管理重写进 `api/` + `services/` + `models/` 分层，产物状态入 Postgres 并按用户隔离。
- 保留源项目的产物血缘语义（text 记录来源 audio/video 产物）与进度/报错可观测性。
- 长耗时任务异步执行，前端可轮询产物状态/进度。
- YouTube 受限内容用 cookies 登录可用。

**Non-Goals:**
- 不在本次打通"已采集 youtube ContentItem 一键转写"（入口仅粘贴 URL）。
- 不做大模型摘要/投研洞察（本次只产出文本，供后续能力消费）。
- 不迁移源项目的前端模板（TradingRadar 用 Vue 自建页面）。
- 不实现源项目的"首启自动导入磁盘已有文件"（新系统从零积累）。

## Decisions

**决策 1：产物存 Postgres，新增 `Source` 与 `Artifact` 模型，按 user_id 隔离。**
- `Source(user_id, url, video_id, title, author, created_at)`，`UniqueConstraint(user_id, video_id)` 去重同一用户的同一视频来源。
- `Artifact(source_id, type[video|audio|text], stage[download|transcribe], status[queued|running|processing|finished|error], progress, filepath, size, started_at, finished_at, error, error_log, source_artifact_id 自引用血缘, meta JSON)`。
- 理由：与项目数据层一致、天然多用户、可被后续能力 join 查询。备选：沿用 store.json → 否决（无多用户、与项目不一致）。

**决策 2：长耗时任务用后台执行 + 状态轮询，不在请求内同步等待。**
- `POST /download`、`POST /transcribe` 立即创建 `queued` 产物并返回，后台推进 `running/processing/finished/error` 并回写进度。
- 进度回写：yt-dlp `progress_hooks` / whisper 完成后更新 Artifact。前端轮询 `GET /artifacts`。
- 实现方式：优先复用 FastAPI `BackgroundTasks` + 线程执行（yt-dlp/whisper 为阻塞型，需 `run_in_executor` 或独立线程），避免阻塞事件循环。备选：引入 Celery/RQ → 否决（当前无消息队列基建，过重）。

**决策 3：API 前缀 `/api/content-analysis`，端点对齐源项目语义。**
- `POST /download {url, mode:video|audio}` → 产出 video/audio 产物
- `POST /artifacts/{aid}/transcribe` → 从音/视频产物转出 text 产物
- `GET /artifacts?type=` → 按来源分组列出 + 计数
- `GET /artifacts/{aid}/file` → 文本 inline、媒体下载（路径校验限定在下载根目录内）
- `POST /artifacts/{aid}/cancel` → 取消排队/进行中的任务
- `DELETE /artifacts/{aid}?delete_file=` / `DELETE /sources/{sid}?delete_files=`
- `GET /status` → 转写后端可用性与登录态
- 登录：`POST /login/cookies`、`POST /login/browser`（移植 cookies 能力）

**决策 4：文件落盘在配置化下载根目录，路径访问做越权校验。**
- 沿用 `stock-fundamentals` 已有的"目标路径必须在 base 目录内否则 403"模式（参见 `app/api/fundamentals.py`）。

**决策 5：whisper 后端自动选择沿用源项目策略（mlx 优先、openai 回退），通过 `GET /status` 暴露当前后端与是否可用。**

## Risks / Trade-offs

- [YouTube 风控/受限] 纯下载可能失败 → 提供 cookies 登录与 PO token 支持；失败写入 Artifact.error/error_log 可观测。
- [whisper 模型体积与耗时] 大模型下载与转写慢 → 后台异步 + 进度状态；后端不可用时 `GET /status` 显式告知，转写接口返回明确错误。
- [阻塞型库与 async 事件循环] yt-dlp/whisper 是同步阻塞 → 在 executor/线程中运行，不阻塞 FastAPI。
- [ffmpeg 系统依赖] 容器/环境需装 ffmpeg → 文档与镜像更新；缺失时下载/转写报错可观测。
- [多用户磁盘占用] 媒体文件体积大 → 删除产物/来源支持连带删盘；后续可加配额（非本次）。
- [取消语义有限] whisper 调用无法中途杀死，cancel 只丢弃结果 → 与源项目一致，规格如实描述。

## Migration Plan

1. 新增 Source/Artifact 模型 + Alembic 迁移；`alembic upgrade head`。
2. 落地 `services/content_analysis/` 与 `/api/content-analysis` 路由，注册到 `main.py`。
3. 更新 `requirements.txt`、`config.py`、`.env.example`；补充 ffmpeg 部署说明。
4. 前端改造 `ContentAnalysisView` + API/类型/i18n。
5. 回滚：下线路由、回退迁移（`alembic downgrade`），删除新增模块；对既有能力无影响。

## Open Questions

- 下载/转写并发上限与每用户配额如何设定？（先沿用源项目固定 worker 数，配额留后续）
- 是否在 Docker 镜像内置 ffmpeg 与预下载 whisper 模型？（部署阶段确认）
- 后续大模型摘要/投研洞察作为独立能力消费本能力产出的 text（不在本变更范围）。
- 是否需要把生成的 text 反向关联到已采集的 youtube ContentItem？（本次解耦，留待后续）
