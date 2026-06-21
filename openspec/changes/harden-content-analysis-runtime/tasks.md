## 1. 运行依赖声明（已 hotfix 落地，复核为主）

- [ ] 1.1 复核 `backend/requirements.txt`：`yt-dlp`、`openai-whisper` 均未被注释；mlx-whisper 的 macOS-only 说明注释保留
- [ ] 1.2 复核 `backend/Dockerfile`：系统 `ffmpeg` 由 apt 安装（合并/转码/转 mp3/Whisper 解码音轨）

## 2. 后端依赖探测与 status（已 hotfix 落地，复核为主）

- [ ] 2.1 复核 `backend/app/services/content_analysis/backends.py`：`yt_dlp_available()` 真实 `import yt_dlp`、`ffmpeg_available()` 用 `shutil.which("ffmpeg")`
- [ ] 2.2 复核 `backend/app/schemas/schemas.py` 的 `AnalysisStatusResponse` 含 `yt_dlp_available` / `ffmpeg_available` 布尔字段
- [ ] 2.3 复核 `backend/app/api/content_analysis.py` 的 `GET /status` 返回上述两字段
- [ ] 2.4 `cd backend && python -m pytest -q` 通过
- [ ] 2.5 `cd backend && ruff check .` 通过

## 3. 依赖接线冒烟测试（防回归，已 hotfix 落地，复核为主）

- [ ] 3.1 复核 `backend/tests/test_content_analysis_deps.py` 故意不打桩：断言 yt-dlp 可导入、ffmpeg 在 PATH、status 暴露依赖位、helper 在完整环境为 True、缺 ffmpeg 时 helper 报 False
- [ ] 3.2 在完整环境 `cd backend && python -m pytest -q tests/test_content_analysis_deps.py` 全绿

## 4. 转写/下载行为与规格对齐（已对齐，复核为主）

- [ ] 4.1 复核 `backends.py` 转写：`resolve_backend()` auto 优先 mlx 回退 openai；`transcribe_audio()` 经 Whisper（ffmpeg 解码音轨）直接处理音/视频，不单独抽音频
- [ ] 4.2 复核 `runner.py`：转写成功后按 `content_analysis_delete_source_after_transcribe`（默认 True）删源、断开血缘外键、meta 记录删源信息
- [ ] 4.3 复核 `runner.py` 软取消：取消时模型推理结束后丢弃结果、不写 text 文件、不删源音/视频产物
- [ ] 4.4 复核下载链路依赖系统 ffmpeg（合并 mp4 / 提取 mp3）；PO token provider 标注为未来项、当前未实现

## 5. 前端缺依赖禁用入口（已 hotfix 落地，复核为主）

- [ ] 5.1 复核 `frontend/src/types/index.ts` status 类型含 `yt_dlp_available` / `ffmpeg_available`
- [ ] 5.2 复核 `frontend/src/i18n.ts` 含 `contentAnalysis.depsMissing`（中英）并更新 MessageKey
- [ ] 5.3 复核 `frontend/src/views/ContentAnalysisView.vue` 与 `SourceFeedView.vue`：缺依赖时展示告警条并禁用下载/转写入口
- [ ] 5.4 `cd frontend && npm run type-check` 通过
- [ ] 5.5 `cd frontend && npm run build` 通过

## 6. 真实验证

- [ ] 6.1 镜像/环境装齐依赖后，`GET /status` 实测返回 `transcribe_available:true`（如 openai:base）、`yt_dlp_available:true`、`ffmpeg_available:true`
- [ ] 6.2 人工浏览器验证：打开 `/content-analysis`，依赖齐全时下载/转写入口可用、无告警条；（如可模拟）缺依赖时出现告警条且入口禁用

---
以下为本轮新增（A/B），**待 RD 新实现 + QA 验证**，非复核已落地。

## 7. 宿主耦合功能：后端检测与配置（A，待实现）

- [ ] 7.1 `backend/app/core/config.py` 新增宿主功能开关（如 `content_analysis_host_features_enabled`，默认按容器检测推断 / 可显式覆盖）
- [ ] 7.2 新增宿主环境检测（如 `services/content_analysis/host_env.py` 的 `host_features_available()`）：配置开关优先 + 容器检测（`/.dockerenv` 等）兜底，集中一处供 api/status 复用
- [ ] 7.3 `cd backend && ruff check .` 通过

## 8. 宿主耦合功能：接口降级与 status（A，待实现）

- [ ] 8.1 `backend/app/api/content_analysis.py` 的 `reveal_artifact`：宿主功能不可用时返回明确错误（如 501 + 文案），不调用 subprocess、不抛未捕获 500
- [ ] 8.2 `backend/app/api/content_analysis.py` 的 `login/browser`（`import_from_browser`）：宿主功能不可用时返回明确错误（如 501 + 文案），不读取本机浏览器
- [ ] 8.3 `backend/app/schemas/schemas.py` 的 `AnalysisStatusResponse` 增 `host_features_available`；`GET /status` 上报
- [ ] 8.4 `cd backend && ruff check .` 通过

## 9. 宿主耦合功能：后端测试（A，待实现）

- [ ] 9.1 新增测试：宿主功能不可用时 reveal / login/browser 返回明确错误（非 500、非静默成功）、不触发 subprocess / 浏览器读取（打桩验证未被调用）
- [ ] 9.2 新增测试：`GET /status` 在容器/非容器下分别返回 `host_features_available` false/true
- [ ] 9.3 新增测试：宿主功能可用时 reveal / login/browser 走原有逻辑（行为不变）
- [ ] 9.4 `cd backend && python -m pytest -q` 通过

## 10. 宿主耦合功能：前端隐藏入口（A，待实现）

- [ ] 10.1 `frontend/src/types/index.ts` status 类型增 `host_features_available`
- [ ] 10.2 `frontend/src/i18n.ts` 新增宿主功能不可用文案（中英）并更新 MessageKey
- [ ] 10.3 `frontend/src/views/ContentAnalysisView.vue`：`host_features_available` 为 false 时隐藏/禁用「打开文件夹」「从浏览器导入」入口
- [ ] 10.4 `frontend/src/views/ContentAnalysisView.vue`：按操作区分错误文案——各操作（下载/转写/打开文件夹 reveal/从浏览器导入/删除/还原/彻底清除/登出/探测）catch 分支改用与该操作相符的文案，不再统一复用 `contentAnalysis.downloadFailed`（修正约 305/316/326-330/423 行等误报「下载失败」的分支）；宿主耦合操作在容器下不可用时提示「该功能仅在桌面/宿主部署可用」；对应文案 key 在 `frontend/src/i18n.ts` 按操作补齐（中英）并更新 `MessageKey`
- [ ] 10.5 `cd frontend && npm run type-check` 通过
- [ ] 10.6 `cd frontend && npm run build` 通过

## 11. 中文转写转简体（B，待实现）

- [ ] 11.1 `backend/requirements.txt` 新增 `opencc`（纳入依赖契约，不被注释）
- [ ] 11.2 `backend/app/core/config.py` 新增 `transcribe_to_simplified: bool = True`
- [ ] 11.3 `backend/app/services/content_analysis/backends.py`：抽出 `_to_simplified(text)`（opencc t2s），`transcribe_audio()` 在 mlx/openai 两分支产出后、return 前对中文统一转简体；非中文不被破坏；开关关闭时不转换
- [ ] 11.4 `backend/tests/test_content_analysis_deps.py` 增 `import opencc` 冒烟断言
- [ ] 11.5 新增转换行为单测：繁体中文→简体、英文等非中文不被破坏、开关关闭时按原始输出
- [ ] 11.6 `cd backend && python -m pytest -q` 通过
- [ ] 11.7 `cd backend && ruff check .` 通过

## 12. 真实验证（A/B 新增）

- [ ] 12.1 人工浏览器验证：容器部署下打开 `/content-analysis`，「打开文件夹」「从浏览器导入」入口被隐藏/禁用；（如可模拟宿主可用）入口出现且可用
- [ ] 12.2 真实验证：对一段中文音/视频转写，落盘 text 产物为简体；对一段英文音/视频转写，文本不被破坏

## 13. 内容分析 cookie 多用户隔离（C，待 RD 新实现）

- [ ] 13.1 `backend/app/services/content_analysis/store.py`：`cookie_file()` → `cookie_file(user_id)`，返回 `base_dir()/cookies/<user_id>.txt`（目录不存在时创建）
- [ ] 13.2 `backend/app/services/content_analysis/cookies.py`：`validate_cookie_file / save_text_cookies / import_from_browser / live_probe / clear_cookies / cookies_present` 全部加 `user_id` 形参并传给 `store.cookie_file(user_id)`，不再用全局文件
- [ ] 13.3 `backend/app/services/content_analysis/runner.py`：下载时不再 `cookie = store.cookie_file()`，改为取该下载产物归属用户的 cookie（runner 拿到 owner user_id）
- [ ] 13.4 `backend/app/api/content_analysis.py`：cookie 相关路由（save/import/probe/logout/status）把 `current_user.id` 传入对应 cookies 函数
- [ ] 13.5 旧全局 `youtube_cookies.txt` 不读取、不迁移（升级后按未登录处理，用户各自重登）
- [ ] 13.6 `backend/app/services/content_analysis/backends.py` 无需改（`download_media(... cookie_path)` 已参数化）——确认即可
- [ ] 13.7 新增测试：用户 A 保存 cookies 后，用户 B 的 status/活体探测 仍为未登录（互不串味）
- [ ] 13.8 新增测试：用户 B 登出仅清除 B 的 `cookies/<B_id>.txt`，用户 A 的 cookies/登录态不变
- [ ] 13.9 新增测试：下载某用户产物时用其 `cookies/<owner_id>.txt`（断言传给 download 的 cookie_path 为该用户路径）
- [ ] 13.10 `cd backend && python -m pytest -q` 通过
- [ ] 13.11 `cd backend && ruff check .` 通过
