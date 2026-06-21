## Why

上一期把源项目 yt-dlp-x 的内容分析能力移植进 TradingRadar 时，**代码逻辑搬全了，但运行依赖被注释/漏装**（如 `openai-whisper`、系统 `ffmpeg`），且主线规格只写了"行为"、从未写明"部署必须提供哪些运行依赖"。结果是环境缺依赖却"符合规格"——线上点「转文本」点不动、下载报 `No module named 'yt_dlp'`，这类环境缺口直接溜过了全部功能测试（功能测试为了不打外网会把下载/转写后端 mock 掉，永远走不到真正的 `import yt_dlp` / 调 ffmpeg）。

本变更把"内容分析"规格与 yt-dlp-x 的实际实现逐条对齐，并把已落地的运行依赖 hotfix 正式纳入规格，新增"运行依赖契约"这一防回归 Requirement，让"声明依赖但环境没装"在测试阶段就被拦截。

## What Changes

- **MODIFY「音视频转写为文本」**：补齐与 yt-dlp-x 对齐的三条行为——(1) 默认转写成功后删除源音/视频、只留文本（可配置）；(2) 视频不单独抽音频，Whisper 经 ffmpeg 从视频解码音轨；(3) 软取消语义：模型推理无法中途终止，取消时丢弃结果且**不删源**。
- **MODIFY「下载 YouTube 音视频产物」**：补明下载/合并/转 mp3 依赖系统 ffmpeg；受限/会员内容需 PO token provider（标注**未实现/未来项**）。
- **MODIFY「转写后端与登录状态查询」**：status 返回值补 `yt_dlp_available` / `ffmpeg_available`（对齐已落地代码）。
- **ADD 新 Requirement「内容分析运行依赖契约」**：系统 SHALL 要求部署提供 yt-dlp + 系统 ffmpeg + 至少一个 Whisper 后端；缺失时 status 报对应不可用、前端禁用相关入口、并由依赖接线冒烟测试（故意不打桩）拦截"声明依赖但环境没装"。
- 上述行为对应的代码改动已通过 hotfix 部分落地（requirements/Dockerfile/backends/api/schema/前端告警条/冒烟测试），本变更负责把它们正式写进规格并防回归，**无需重写实现**。

### 本轮增补（A/B 两类新发现，均待 RD 新实现）

- **ADD 新 Requirement「宿主耦合功能在容器部署下的处理」**（真 defect，待实现）：yt-dlp-x 原是单机桌面工具，假设"服务器=用户本机"；搬进 docker 前后端分离 Web 应用后，凡"在后端机器上操作宿主"的功能都失效——已确认两个：(1)「打开文件夹 reveal」`subprocess.Popen(["open"/"explorer"/"xdg-open"])` 在无 GUI 的 Linux 容器里什么都不发生/报错；(2)「从浏览器导入 cookies import_from_browser」读的是后端机器的浏览器配置，容器里没有浏览器→不可用。本变更要求系统能判断当前是否支持这类宿主功能（配置开关 + 容器环境检测如 `/.dockerenv`），不支持时这些接口返回**明确错误（400/501 + 文案）**、不静默不抛未捕获 500；`GET /status` 增加上报这类宿主功能可用性（`host_features_available` 等分项），供前端隐藏/禁用「打开文件夹」「从浏览器导入」入口，避免死按钮。文案明确这些功能仅在 macOS/Windows 宿主直跑后端时可用。**并修正误导性错误文案**：手测发现内容分析页多处 catch 分支统一复用 `contentAnalysis.downloadFailed`（如 `ContentAnalysisView.vue` 的 `onReveal` 打开文件夹失败却提示「下载失败，请稍后重试」，删除/转写等同样误报），本变更要求前端各操作失败时给与操作相符的提示，宿主功能在容器下不可用时提示「仅桌面/宿主可用」而非「下载失败」。
- **MODIFY「音视频转写为文本」（再次修订，B 类增强，待实现）**：openai/mlx 的 Whisper 对中文普遍输出繁体（指定 zh 亦然，非移植走样）。引入 **opencc**（繁→简，具体包见 design）对中文转写结果做后处理，默认转简体、非中文不受影响；该依赖**也纳入"运行依赖契约"与依赖冒烟测试**（与本变更主题一致）。落点为 `backends.py` 的 `transcribe_audio()` 在产出文本后、写文件前统一处理（mlx/openai 两分支）。
- **MODIFY「内容分析运行依赖契约」（再次修订，B 类）**：把 opencc（繁→简转换）纳入运行依赖契约与依赖接线冒烟测试覆盖范围。

### 本轮增补（C 类：内容分析 cookie 多用户隔离，待 RD 新实现）

- **ADD 新 Requirement「内容分析 cookie 的多用户隔离」**（真 defect，待实现）：现状 cookies 是**全局单文件**（`store.cookie_file()` → `base_dir()/youtube_cookies.txt`，无 user_id）。在多用户产品里这是账号串味——用户 A 登录的 YouTube cookies 被用户 B 的下载使用；任一用户「登出」会把所有人登出。DB 层产物已按 user_id 隔离，唯独 cookie 漏在外面。本变更要求 cookies 改为**每用户一份**，路径 `base_dir()/cookies/<user_id>.txt`；旧全局文件**弃用、不迁移**（让用户各自重登）。登录（粘贴 / 浏览器导入）、登出、活体探测、`GET /status` 的 `cookies_present`/`youtube_logged_in`、下载时所用 cookie，全部按当前用户隔离。修复账号串味与互相登出。

## Capabilities

### New Capabilities
<!-- 无新建 capability；运行依赖契约作为 content-analysis 内的新 Requirement，不另起 spec。 -->

### Modified Capabilities
- `content-analysis`: MODIFY 既有 Requirement（音视频转写为文本 / 下载 YouTube 音视频产物 / 转写后端与登录状态查询），并 ADD 三个新 Requirement（「内容分析运行依赖契约」「宿主耦合功能在容器部署下的处理」「内容分析 cookie 的多用户隔离」）。其中「音视频转写为文本」与「内容分析运行依赖契约」在本轮再次修订（中文简体转换 + opencc 依赖）。cookie per-user 隔离以**新增 ADD Requirement** 承载——cookie 的登录/登出/活体探测语义分散在主线与尚未归档的 `add-content-analysis-gaps` delta 两处，为避免去 MODIFY「主线尚不含」的 Requirement（如登出/活体探测），本变更不重复 MODIFY 那些 Requirement，统一用一条新 ADD 表达 per-user 语义，使 strict 校验稳定通过、且与 gaps 的 delta 不冲突。

## Impact

- 规格：`openspec/specs/content-analysis/spec.md`（经本变更 delta 修订）。
- 已落地代码（本变更纳入规格、QA 复核即可，不重写）：
  - `backend/requirements.txt`（装回 `openai-whisper`，注释说明 mlx-whisper 仅 macOS 宿主手动装）
  - `backend/Dockerfile`（装回系统 `ffmpeg`）
  - `backend/app/services/content_analysis/backends.py`（`yt_dlp_available()` / `ffmpeg_available()`）
  - `backend/app/api/content_analysis.py` + `backend/app/schemas/schemas.py`（`GET /status` 返回 `yt_dlp_available` / `ffmpeg_available`）
  - `backend/tests/test_content_analysis_deps.py`（依赖接线冒烟测试，故意不打桩）
  - `frontend/src/types/index.ts`、`frontend/src/views/ContentAnalysisView.vue`、`frontend/src/views/SourceFeedView.vue`、`frontend/src/i18n.ts`（缺依赖告警条 + 禁用入口，新增 i18n key `contentAnalysis.depsMissing`）
- 运行依赖（部署契约）：pip `yt-dlp`、pip `openai-whisper`（Linux/docker）/ `mlx-whisper`（macOS 宿主可选）、系统 `ffmpeg`、pip `opencc`（繁→简，新增）；`bgutil-ytdlp-pot-provider`（PO token，**未来项**）。
- 无对外 API 破坏性变更（status 仅新增返回字段：`host_features_available` 等宿主功能位）。

### 本轮增补影响（待 RD 新实现，非复核）

- 宿主耦合处理（A）：
  - `backend/app/core/config.py`（新增宿主功能开关 / 容器检测配置项）。
  - `backend/app/services/content_analysis/`（新增宿主环境检测工具，如 `host_env.py` 或在 backends/cookies 内提供判定函数）。
  - `backend/app/api/content_analysis.py`（`reveal_artifact` 与 `login/browser` 接口在不支持宿主功能时返回明确 400/501 + 文案，不抛未捕获 500）。
  - `backend/app/schemas/schemas.py`（`AnalysisStatusResponse` 增 `host_features_available` 等分项）。
  - `frontend/src/types/index.ts`、`ContentAnalysisView.vue`（按 status 隐藏/禁用「打开文件夹」「从浏览器导入」入口；**各操作 catch 分支改用与操作相符的文案，不再统一复用 `downloadFailed`**——涉及约 305/316/326-330/423 行等 reveal/删除/转写/导入失败分支）、`frontend/src/i18n.ts`（新增宿主功能不可用文案 key + 各操作失败文案 key，中英 + `MessageKey`）。
  - `backend/tests/`（宿主功能不支持时接口返回明确错误、status 上报、可用环境下行为不变的测试）。
- 中文简体转换（B）：
  - `backend/requirements.txt`（新增 `opencc`，纳入依赖契约）。
  - `backend/app/core/config.py`（复用/扩展 `whisper_language` 或新增 `transcribe_to_simplified` 开关，默认开）。
  - `backend/app/services/content_analysis/backends.py`（`transcribe_audio()` 产出后、写文件前对中文统一转简体）。
  - `backend/tests/test_content_analysis_deps.py`（opencc 可导入纳入冒烟）+ 转换行为单测（中文→简体、英文不被破坏）。
- 内容分析 cookie 多用户隔离（C）：
  - `backend/app/services/content_analysis/store.py`：`cookie_file()` → `cookie_file(user_id)`，返回 `base_dir()/cookies/<user_id>.txt`。
  - `backend/app/services/content_analysis/cookies.py`：`validate_cookie_file / save_text_cookies / import_from_browser / live_probe / clear_cookies / cookies_present` 全部带 `user_id`（当前都隐式用全局文件）。
  - `backend/app/services/content_analysis/runner.py`（约第 61 行）：下载时 `cookie = store.cookie_file()` 改为取该产物归属用户的 cookie（runner 需拿到 user_id）。
  - `backend/app/api/content_analysis.py`：cookie 相关路由（save/import/probe/logout/status）本就有 `current_user`，传 `current_user.id` 即可（几乎免费）。
  - `backend/app/services/content_analysis/backends.py`：`download_media(... cookie_path)` 已参数化，**无需改**。
  - 旧全局 `youtube_cookies.txt` 弃用、不迁移；`import_from_browser` 为宿主耦合功能（A 类已要求容器下禁用），per-user 实际主要作用于「粘贴 cookies」这条路。
  - `backend/tests/`：用户 A/B 互不影响（登录/登出/探测/status 隔离）、下载用产物归属用户 cookie 的测试。
