## Context

内容分析下载 YouTube 受限/登录内容需要用户的 YouTube 登录 cookie。已有路径与其局限：

- **手动粘贴 cookies.txt**：可用但麻烦，cookie 过期需反复重粘。harden 变更已把它做成 per-user（`base_dir()/cookies/<user_id>.txt`）。
- **从本机浏览器导入 cookies（`import_from_browser`）**：宿主耦合，容器部署下不可用（harden 已判定降级）。
- **网页内 JS 跨域读 youtube.com cookie**：被同源策略与 cookie 隔离阻断，且 HttpOnly 鉴权 cookie 对 JS 不可见。

唯一能"读当前浏览器 youtube cookie 并自动同步"的合法机制是**浏览器扩展**（`chrome.cookies` 可跨域读指定域、含 HttpOnly）。本变更据此引入扩展 + 后端接收端点。

## Goals / Non-Goals

### Goals
- 装一次扩展即可自动、持续、保持新鲜地把当前浏览器 `youtube.com` 登录 cookie 同步到该用户的内容分析 cookie 存储。
- 配对鉴权稳健、可吊销、作用域最小（只能写本人 cookie）。
- 与「粘贴 cookies」共存，共用同一 per-user 落点。

### Non-Goals
- 不取代「粘贴 cookies」兜底（未装扩展 / 非 Chrome 用户仍走粘贴）。
- 先不抓 `.google.com`（只 `youtube.com`）。
- 先只支持 Chrome（`chrome.cookies`）；Firefox/Safari 暂不做。
- 开发期 load-unpacked 分发即可，不上 Chrome Web Store。
- 不在本变更实现代码（规格捕获）。

## Decisions（探索拍板）

### 1. 绑定方式 = 设备令牌 / 配对码（路 B）
设置页签发**长期、可吊销、作用域仅"写本人 cookie"**的设备令牌；用户复制粘进扩展 popup 一次；扩展用该令牌作为鉴权调同步端点。

- **为何不用"扩展读前端 localStorage 的 JWT"（路 A）**：JWT 是短期会话令牌、登出即失效、过脆；扩展无法稳定长期复用，且把会话 token 暴露给扩展存储面更大。设备令牌专为长期机器对机器同步设计、独立于用户登录会话、可单独吊销。
- 令牌存储：后端只存哈希（如 sha256），明文仅签发时返回一次。

### 2. cookie 抓取范围 = 先只 `youtube.com`
扩展 host 权限只要 `*://*.youtube.com/*`，只读 `youtube.com` 域 cookie。**先不抓 `.google.com`**（会读到含 Gmail 的整个 Google 会话，爆炸半径过大）。

### 3. 刷新策略
扩展用 `chrome.alarms` 定时（如每 6h）+ `chrome.cookies.onChanged`（youtube 域变化即推），始终保持后端 cookie 新鲜；YouTube 登出（cookie 消失）时推空 / 通知，后端 `live_probe` 兜底判未登录。

### 4. 分发与平台
开发期 load-unpacked（开发者模式加载）即可，个位数用户够用；以后再考虑上 Chrome Web Store。先只支持 Chrome。

### 5. 与粘贴 cookie 共存
扩展是体验升级，不取代粘贴兜底；两者共用同一 per-user cookie 落点（`base_dir()/cookies/<user_id>.txt`）。同步端点与粘贴端点都经 `cookies.py` 的校验+落盘逻辑，行为一致。

### 6. 同步端点的 cookie 落盘
扩展推送 JSON cookie 数组（name/value/domain/path/expires/secure/httpOnly 等）→ 后端序列化为 Netscape 格式 → 复用 `save_text_cookies` 同款校验+原子落盘到 `cookie_file(user_id)`。推空（登出）时清除该用户 cookie 文件（等价 `clear_cookies(user_id)`）。

## 依赖

- **强依赖 harden-content-analysis-runtime**：同步端点写入目标 `base_dir()/cookies/<user_id>.txt` 由 harden 的「内容分析 cookie 的多用户隔离」Requirement 引入。harden 先实现，本变更后续。在该 per-user 落点就绪前，本变更无法实现。

## Risks / Trade-offs

- **活会话长期外泄面**：扩展持续同步活 cookie 到服务器并落盘，比一次性粘贴暴露更久；服务器被攻破即泄露活会话。缓解：只 youtube.com、令牌可吊销、强鉴权（只能写自己）、HTTPS、落盘加密 / 短保留。
- **令牌泄露**：设备令牌泄露等于他人可写该用户 cookie。缓解：令牌可吊销、只存哈希、可命名多设备分别吊销。
- **扩展平台锁定**：只支持 Chrome；非 Chrome 用户回退粘贴。可接受。

## Open Questions

- 若只 `youtube.com` cookie 不足以下某些受限内容，是否谨慎评估扩到 `google.com`？（默认不扩，需单独评估爆炸半径。）
- cookie 落盘是否启用静态加密 / 设置短保留（如 N 天未刷新即视为过期清除）？本变更将其列为安全要求 / 待定项，具体方案实现期定。
- 设备令牌是否设可选有效期上限（长期但非永久）？默认长期 + 可吊销，是否加 TTL 待定。
