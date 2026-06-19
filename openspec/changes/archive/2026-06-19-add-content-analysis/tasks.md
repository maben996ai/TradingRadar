## 1. 数据模型与迁移

- [x] 1.1 在 `app/models/models.py` 新增 `AnalysisSource`（user_id, url, video_id, title, author；UniqueConstraint(user_id, video_id)）
- [x] 1.2 新增 `AnalysisArtifact`（source_id, type, stage, status, progress, filepath, size, started_at, finished_at, error, error_log, source_artifact_id 自引用, meta JSON）
- [x] 1.3 编写 Alembic 迁移 `c3d4e5f6a7b8_add_content_analysis_tables`（`alembic upgrade head` 需在 Docker/PG 环境执行：本机 pyenv 缺 psycopg2；schema 已由测试 `Base.metadata.create_all` 验证）
- [x] 1.4 在 `app/schemas/schemas.py` 新增产物/来源请求与响应模型

## 2. 服务层（移植 yt-dlp-x 后端）

- [x] 2.1 新建 `app/services/content_analysis/store.py`：来源/产物的增删查改（基于 SQLAlchemy async，按 user 隔离）
- [x] 2.2 新建 `backends.py` 中的 `download_media`：移植 yt-dlp 下载（mode video/audio、cookies、PO token 重试、进度回写），在 `asyncio.to_thread` 中运行
- [x] 2.3 `backends.py` 中的 Whisper 后端选择（mlx 优先、openai 回退）与 `transcribe_audio`，text 产物记录血缘
- [x] 2.4 新建 `cookies.py`：cookies 登录（粘贴 / 浏览器导入），移植自 `auth.py`/`cookies_util.py`
- [x] 2.5 `runner.py` 后台任务推进产物状态（queued→running→finished/error）与进度回写（内存登记叠加）
- [x] 2.6 取消逻辑（内存集合，丢弃排队/进行中任务结果）

## 3. API 路由

- [x] 3.1 新建 `app/api/content_analysis.py`，实现 download / transcribe / list / file / cancel / delete artifact / delete source / status / login 端点
- [x] 3.2 文件获取做下载根目录越权校验（对齐 `app/api/fundamentals.py`）
- [x] 3.3 在 `app/main.py` 注册 `/api/content-analysis` 路由

## 4. 配置与依赖

- [x] 4.1 `config.py` 新增产物根目录、whisper 后端等配置；同步 `.env.example`
- [x] 4.2 `requirements.txt` 增加 yt-dlp 与 whisper 后端说明；补充 ffmpeg 部署说明

## 5. 前端

- [x] 5.1 `api/contentAnalysis.ts` 与 `types/index.ts` 类型定义
- [x] 5.2 `ContentAnalysisView.vue` 改造：URL 输入 + 下载、产物按来源分组管理、进度/状态展示、文本查看、转写/取消/删除、cookies 登录
- [x] 5.3 i18n（中英）与样式
- [x] 5.4 `npm run type-check` 与 `npm run build` 通过

## 6. 测试与验证

- [x] 6.1 后端针对各端点编写 pytest（下载/转写以打桩后端跑通状态流转，不真打外网）
- [x] 6.2 越权与鉴权用例（未登录 401、缺产物 404、越权路径 403）
- [x] 6.3 `pytest`（299 通过）、`ruff check .` 通过、新文件 `ruff format` 通过
- [ ] 6.4 本地真实跑通一条链路：粘贴 URL → 下载 → 转写 → 查看文本（需 ffmpeg + whisper，未在本环境执行）
- [x] 6.5 `openspec validate add-content-analysis --strict` 通过
