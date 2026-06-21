## Why

内容分析下载 YouTube 受限/登录内容需要该用户的 YouTube 登录 cookies。当前可用路径只有「手动粘贴 cookies.txt」（harden 变更已把它做成 per-user 隔离），但手动粘贴麻烦、且 cookie 会过期，用户得反复重粘。容器部署下，「从本机浏览器导入 cookies」已被判定为宿主耦合功能、容器内不可用（见 harden 变更）；而 TradingRadar 网页因同源/cookie 隔离也无法跨域读取 `youtube.com` 的 cookie（尤其 HttpOnly 鉴权 cookie）。

唯一能"读取当前浏览器的 YouTube cookie 并自动持续同步"的合法机制是**浏览器扩展**——扩展通过 `chrome.cookies` 权限可跨域读指定域的 cookie（含 HttpOnly）。本变更引入一个配套 Chrome 扩展（MV3）+ 后端接收端点，实现"装一次扩展 → 自动、持续、保持新鲜地把当前浏览器的 YouTube 登录 cookie 同步到该用户的内容分析 cookie 存储"，免去手动粘贴与反复重粘。扩展是体验升级，不取代「粘贴 cookies」兜底：未装扩展 / 非 Chrome 用户仍可粘贴，两者共用同一 per-user cookie 落点。

## What Changes

- **ADD 新能力 `youtube-cookie-sync`**，包含：
  - **设备令牌（device token）**：登录用户在设置页签发一个长期、可吊销、作用域仅"写本人 cookie"的设备令牌；支持列出与吊销；用户把令牌复制粘进扩展 popup 一次完成配对。**不**采用"扩展自动读前端 localStorage 的 JWT"（JWT 短期会话、登出即失效、过脆）。
  - **cookie 同步端点**（`POST /api/content-analysis/cookies/sync`）：接收扩展推送的 `youtube.com` cookie（JSON 结构）+ 设备令牌鉴权 → 序列化为 Netscape 格式 → 写入该令牌归属用户的 per-user cookie 文件（复用 harden 的 `cookie_file(user_id)` 与 `cookies.py` 校验/落盘逻辑）。无效/吊销令牌返回 401/403；令牌只能写自己的 cookie。
  - **Chrome 扩展（MV3）脚手架**（规格层描述，本变更不实现）：新目录 `extension/`；host 权限仅 `*://*.youtube.com/*`，只读 `youtube.com` 域 cookie；配对码绑定；`chrome.alarms` 定时（如每 6h）+ `chrome.cookies.onChanged`（youtube 域变化即推）保持新鲜；YouTube 登出（cookie 消失）时推空并通知，后端 `live_probe` 兜底判未登录。
- **依赖声明**：本变更**依赖 harden-content-analysis-runtime 先落地**——同步端点必须把 cookie 写进 harden 引入的 per-user 路径 `base_dir()/cookies/<user_id>.txt`。harden 先实现，本变更后续。

## 风险与安全说明

扩展持续把"活的"YouTube 会话 cookie 同步到服务器并落盘，比一次性粘贴**暴露时间更久**；服务器被攻破即等于泄露活跃会话。缓解措施：

- **只抓 `youtube.com`**：扩展 host 权限只要 `*://*.youtube.com/*`，**先不抓 `.google.com`**（那会读到含 Gmail 的整个 Google 会话，爆炸半径过大）。
- **设备令牌可吊销 + 强鉴权**：令牌仅能写本人 cookie，泄露/换设备可随时吊销。
- **传输 HTTPS**；落盘建议加密 / 短保留（列为安全要求/Open Question）。
- **明确知情同意**：在设置页与扩展 popup 明确告知用户"扩展会读取并上传你的 YouTube 登录 cookie 到 TradingRadar 服务器"。

对个位数自用、仅 `youtube.com` 范围，风险可接受；将来多租户/对外需重新评估。

## Capabilities

### New Capabilities
- `youtube-cookie-sync`: 设备令牌签发/吊销、cookie 同步端点、配套 Chrome 扩展（MV3）行为与安全要求。

### Modified Capabilities
<!-- 无。本变更新增能力，不 MODIFY content-analysis 既有 Requirement；per-user cookie 落点由 harden 变更引入并被本变更复用。 -->

## Impact

- 新增能力规格：`openspec/specs/youtube-cookie-sync/spec.md`（归档时由本 delta 写入）。
- 后端（待 RD 实现）：
  - 模型：新增设备令牌模型（`user_id` / 令牌哈希 / 名称 / 作用域 / `created_at` / `revoked_at` / `last_used_at`），含 alembic 迁移。
  - service：新增设备令牌签发/校验/吊销逻辑；cookie 同步逻辑复用 `backend/app/services/content_analysis/cookies.py` 的校验+落盘与 `store.cookie_file(user_id)`（harden 引入）。
  - API：`backend/app/api/content_analysis.py`（或新路由模块）新增设备令牌 CRUD 与 `POST /api/content-analysis/cookies/sync`；schema 在 `backend/app/schemas/schemas.py`。
  - 同步成功后 `GET /status` 的 `cookies_present` / `youtube_logged_in` 随之反映该用户最新 cookie 状态（沿用现有 status 行为，不改其契约）。
- 前端（待 RD 实现）：内容分析设置区新增"设备令牌"管理（生成/复制/列出/吊销）+ 扩展安装与配对引导文案；`api` / `types` / `i18n`（中英 + `MessageKey`）。
- 新目录（待 RD 实现）：`extension/`（Chrome MV3 扩展：`manifest.json` / background service worker / popup）。
- 依赖：**harden-content-analysis-runtime 须先落地**（per-user cookie 存储 `cookie_file(user_id)`）。

## 依赖（显式声明）

- **强依赖** `harden-content-analysis-runtime` 中「内容分析 cookie 的多用户隔离」Requirement 先实现：cookie 同步端点写入的目标即该 Requirement 定义的 `base_dir()/cookies/<user_id>.txt`。harden 未落地前，本变更不能实现（无 per-user 落点可写）。
- 排序：`add-content-analysis-gaps` 收尾归档 → `harden-content-analysis-runtime` 实现（含 per-user cookie）→ 本变更 `add-youtube-cookie-extension`。
