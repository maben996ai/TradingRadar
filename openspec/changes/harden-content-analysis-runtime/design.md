## Context

内容分析的实现逻辑移植自源项目 yt-dlp-x（下载 `downloader.py`、转写 `transcriber.py`），TradingRadar 侧对应 `backend/app/services/content_analysis/{backends,runner,store,cookies}.py`，逐行对齐。问题不在逻辑，而在两处缺口：

1. **运行依赖被注释/漏装**：移植时 `openai-whisper`、系统 `ffmpeg` 等运行依赖在 `requirements.txt` / `Dockerfile` 被注释或遗漏，环境缺依赖导致「转文本点不动」、下载报 `No module named 'yt_dlp'`。
2. **测试盲区**：功能测试为了不打外网，把下载/转写后端 mock 掉，永远走不到真正的 `import yt_dlp` / 调 ffmpeg，于是环境缺依赖能溜过全部测试。

主线规格 `openspec/specs/content-analysis/spec.md` 只写了行为，从未写明"部署必须提供哪些运行依赖"——这正是要补的契约缺口。本变更大部分实现已通过 hotfix 落地，设计聚焦于"把已落地行为固化为规格 + 防回归测试策略"。

## Goals / Non-Goals

**Goals:**
- 把 yt-dlp-x 的三条已对齐行为（转写后删源、ffmpeg 解码音轨、软取消保留源）正式写进规格。
- 把"运行依赖契约"立为一条独立 Requirement，使"声明依赖但环境没装"在测试阶段被拦截。
- status 接口的依赖可用性字段（`yt_dlp_available` / `ffmpeg_available`）与前端禁用入口纳入规格。
- QA 可对照规格复核已落地的 hotfix，无需 RD 重写实现。

**Non-Goals:**
- 不重写已落地的 backends/runner/api/schema/前端代码。
- 不实现 PO token provider（`bgutil-ytdlp-pot-provider`）——明确标注为未来项。
- 不改动 mlx-whisper 在 Linux 镜像的安装策略（无 Linux wheel，仅 macOS 宿主手动装，保持注释说明）。

## Decisions

**决策 1：依赖接线冒烟测试故意不打桩。**
新增 `test_content_analysis_deps.py` 直接 `import yt_dlp`、断言 `shutil.which("ffmpeg")` 非空、断言 `/status` 暴露依赖位。备选是继续靠功能测试覆盖——已被证伪（mock 掩盖缺口）。代价是该测试文件依赖真实环境，但这正是其价值：它就是要在缺依赖的环境失败。

**决策 2：运行依赖契约作为 content-analysis 内的新 Requirement，而非另起 spec。**
依赖契约只服务于内容分析能力，归在同一 capability 内便于归档与追溯；不污染顶层 specs 目录。

**决策 3：openai-whisper 进镜像、mlx-whisper 仅 macOS 宿主手动装。**
mlx-whisper 是 Apple Silicon 专用、无 Linux wheel，无法装进 Linux 镜像；`resolve_backend()` 的 auto 策略已优先 mlx、回退 openai，故 Linux/docker 用 openai-whisper（CPU，拉 torch）、macOS 宿主可手动装 mlx 走 GPU。requirements 中保留注释说明这一分叉，避免下次又有人"清理"掉。

**决策 4：删源/取消语义严格对齐 yt-dlp-x。**
转写成功默认删源（`content_analysis_delete_source_after_transcribe` 默认 True，可关）；软取消时模型推理不可中途杀，推理结束后丢弃结果且不删源（源保留可重试）。runner 已如此实现，规格逐条固化。

**决策 5（A，本轮新增，待实现）：宿主耦合功能用"环境能力位 + 明确降级"处理，不静默失败。**
背景：yt-dlp-x 是单机桌面工具，`reveal`（在后端机器开文件管理器）与 `import_from_browser`（读后端机器浏览器配置）都假设"后端=用户本机"。搬进 docker 前后端分离 Web 后这两类功能在容器里失效（Linux 无 GUI、容器无浏览器）。
- 检测：新增宿主能力判定（如 `host_features_available()`），判据为 **配置开关优先 + 容器环境兜底**——存在 `/.dockerenv` 或环境变量标识为容器时视为不支持；显式配置项（如 `content_analysis_host_features_enabled`）可强制开/关，便于"在 macOS/Windows 宿主直跑后端"时手动开启。判定逻辑集中在一处（如 `services/content_analysis/host_env.py`）供 api 与 status 复用。
- 接口降级：`POST /artifacts/{aid}/reveal` 与 `POST /login/browser` 在不支持宿主功能时返回**明确错误**（选用 501 Not Implemented 表"此部署形态不提供该能力"，附中文文案"该功能仅在 macOS/Windows 宿主直跑后端时可用"），不再走到 `subprocess.Popen`/读浏览器并抛未捕获 500，也不静默成功。
- 前端联动：`GET /status` 增 `host_features_available`（必要时拆分项），前端据此**隐藏/禁用**「打开文件夹」「从浏览器导入」入口，杜绝点了没反应的死按钮。
- 备选与否决：①只在前端隐藏不改后端——否决，接口仍可被直接调用并抛 500，不可观测；②直接删掉这两个功能——否决，宿主直跑场景仍需要，降级而非移除更稳。

**决策 6（B，本轮新增，待实现）：转写中文用 opencc 后处理转简体，依赖纳入运行契约。**
事实：openai/mlx 的 Whisper 对中文普遍输出繁体（`whisper_language` 指定 zh 也常繁体），yt-dlp-x 同款。
- 选包：用 **`opencc`**（OpenCC 官方 PyPI 包，自带 `s2t/t2s` 等配置；纯转换、无模型、跨平台有 wheel），转换器用 `t2s`（繁→简）。该包加入 `requirements.txt` 并**纳入依赖契约 + 依赖冒烟测试**（与本变更"声明依赖必须真装到"主题一致）。
- 开关：新增 `transcribe_to_simplified: bool = True`（默认对中文转写结果转简体）；非中文不受影响（仅对含中日韩中文字符的文本做转换，或在中文语言判定下转换，避免破坏英文等其他语言）。
- 落点：`backends.py` 的 `transcribe_audio()` 在 mlx/openai 两分支**产出文本后、return 前**统一调用转换函数（抽出 `_to_simplified(text)` 便于单测与打桩），保证两个后端行为一致。runner 写文件用的是该返回值，无需改 runner。
- 备选与否决：①让 Whisper 直接出简体——否决，模型不可控、指定 zh 仍繁体；②前端展示时转换——否决，落盘文本仍是繁体、下载的 text 产物不一致。后处理落盘是唯一一致点。

**决策 7（C，本轮新增，待实现）：内容分析 cookie 改为 per-user 隔离，旧全局文件弃用不迁移。**
事实：现状 cookies 是全局单文件——`store.cookie_file()` 返回 `base_dir()/youtube_cookies.txt`，无 user_id。`cookies.py` 的 `validate_cookie_file / save_text_cookies / import_from_browser / live_probe / clear_cookies / cookies_present` 全部隐式用这一个文件；`runner.py` 下载时 `cookie = store.cookie_file()`。在多用户产品里这导致账号串味：A 登录的 YouTube cookies 被 B 的下载使用，任一用户登出会把所有人登出。DB 层产物已按 user_id 隔离，唯独 cookie 漏在外面。
- 路径：cookie 改为每用户一份 `base_dir()/cookies/<user_id>.txt`。`store.cookie_file()` → `store.cookie_file(user_id)`。
- user_id 穿透：`cookies.py` 上述六个函数全部加 `user_id` 形参（向 `store.cookie_file(user_id)` 传递）；`runner.py` 取该产物归属用户的 user_id 选 cookie；api 路由本就有 `current_user`，传 `current_user.id` 即可（几乎免费）。`backends.download_media(... cookie_path)` 已参数化，无需改。
- 旧全局文件：`youtube_cookies.txt` 本就是登录态、不是用户数据，**直接弃用、不迁移**——升级后用户按未登录处理，各自重登。否决「自动迁移给某个用户」：无法判定归属，迁错比重登更糟。
- 规格表达（重要）：cookie 的登出 / 活体探测语义当前**只在尚未归档的 `add-content-analysis-gaps` delta** 里、主线 `content-analysis/spec.md` 还没有；而 status 与「YouTube Cookies 登录」两个 Requirement 主线有、且 gaps 与本 harden 都已对其做 MODIFY。为避免 MODIFY 一个「主线还不存在」的 Requirement（会让 strict 失败或强行依赖 gaps 先 sync），本变更把 per-user 的全部 cookie 语义（登录/登出/探测/status 的 cookies_present+youtube_logged_in/下载用 cookie）统一承载在**一条新 ADD Requirement「内容分析 cookie 的多用户隔离」**里，不去重复 MODIFY gaps/主线已触及的那些 Requirement。这样 harden 的 delta 只 ADD、不与 gaps 的 MODIFY 撞车，strict 校验稳定通过。
- 排序建议（非 spec 硬依赖）：推荐 `add-content-analysis-gaps` 先归档（把 probe/logout/recycle + status/login 的 MODIFY 同步进主线），harden 再转 prd.json 实现。harden 的 spec delta 本身**不**结构性依赖 gaps 已归档（只 ADD），故无论 gaps 何时归档都不影响本变更 validate。

## Risks / Trade-offs

- [依赖冒烟测试在缺依赖的 CI/本地会"红"] → 这是预期行为，是契约的执行手段；文档与测试 docstring 已写明意图，避免误判为 flaky。
- [openai-whisper 拉入 torch，镜像变大、首次转写慢] → 接受：Linux 无 mlx 可选，CPU 转写是唯一跨平台回退；macOS 宿主可装 mlx 提速。
- [PO token 未实现，受限/会员内容只能靠 cookies] → 已在规格标注未来项；当前 cookies 登录链路覆盖大部分受限场景。
- [mlx 安装说明被未来"清理"误删] → 用 requirements 内注释 + 本设计 + 规格三处记录降低风险。

## Migration Plan

无数据迁移。本变更主要是规格固化 + 防回归测试，实现已通过 hotfix 落地：
1. 确认 `requirements.txt` / `Dockerfile` 依赖声明就位（已落地）。
2. 镜像重建后 `/status` 应返回 `transcribe_available:true`（openai:base）、`yt_dlp_available:true`、`ffmpeg_available:true`（已实测）。
3. 回滚策略：本变更不引入破坏性 API 变更，status 仅新增返回字段，前端容错（缺字段视为 false），无需特殊回滚。

## Open Questions

- 无阻塞性问题。PO token provider 的接入时机待主线排期，不在本变更范围。
- 宿主功能降级状态码用 501（决策 5 默认选择）；若主线已有 400 系约定可在实现时统一，规格只要求"明确错误 + 不静默 + 不抛未捕获 500"。
- 中文判定粒度（按检测语言 vs 按是否含中文字符）由实现选定，规格只约束"中文转简体、非中文不被破坏"。
- per-user cookie 的 user_id 来源：cookie 路由从 `current_user.id` 取，runner 从产物归属用户取；具体 runner 如何拿到 owner user_id 由实现选定，规格只约束"下载用产物归属用户的 cookie"。
