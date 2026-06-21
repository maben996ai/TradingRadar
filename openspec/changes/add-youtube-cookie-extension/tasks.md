## 1. 前置依赖

- [ ] 1.1 确认 `harden-content-analysis-runtime` 已实现并归档（per-user cookie `cookie_file(user_id)` + `cookies.py` 各能力带 `user_id`），否则本变更阻塞

## 2. 后端：设备令牌

- [ ] 2.1 新增设备令牌模型（`user_id` / 令牌哈希 / 名称 / `created_at` / `last_used_at` / `revoked_at`），含 alembic 迁移
- [ ] 2.2 在 `schemas.py` 新增设备令牌签发/列出响应与同步请求 schema
- [ ] 2.3 service：签发（生成令牌 + 仅存哈希、明文一次性返回）、校验（按哈希查活跃令牌、更新 `last_used_at`）、列出、吊销
- [ ] 2.4 路由：设备令牌 CRUD（签发 / 列出 / 吊销），用户会话鉴权（`current_user`）
- [ ] 2.5 测试：签发只存哈希、明文仅返回一次、列出不含明文、吊销后校验失败、只能管理本人令牌

## 3. 后端：cookie 同步端点

- [ ] 3.1 实现 `POST /api/content-analysis/cookies/sync`：设备令牌鉴权 → 解析扩展 JSON cookie → 序列化 Netscape → 复用 `cookies.py` 校验+落盘到 `cookie_file(user_id)`
- [ ] 3.2 推空 cookie（登出）时清除该用户 cookie 文件
- [ ] 3.3 同步成功后 `GET /status` 的 `cookies_present` / `youtube_logged_in` 正确反映
- [ ] 3.4 鉴权失败（无效/吊销/缺失令牌）返回 401/403 且不写入；只写本人 cookie
- [ ] 3.5 网络/校验探测不阻塞事件循环（沿用现有 `asyncio.to_thread` 等价方式）
- [ ] 3.6 测试：成功同步、状态变化、无效/吊销令牌被拒、只写自己、推空清除、非法内容拒绝不破坏已有 cookie

## 4. 前端：设备令牌管理与配对引导

- [ ] 4.1 `api` / `types` 新增设备令牌签发/列出/吊销与同步相关类型
- [ ] 4.2 内容分析设置区新增设备令牌管理 UI（生成 / 一次性复制 / 列出 / 吊销）
- [ ] 4.3 扩展安装与配对引导文案 + 知情同意提示（读取并上传 YouTube cookie）
- [ ] 4.4 `i18n` 中英文案 + `MessageKey`
- [ ] 4.5 前端 `npm run type-check` / `npm run build` 通过

## 5. Chrome 扩展（MV3）

- [ ] 5.1 新目录 `extension/`：`manifest.json`（MV3，host 权限仅 `*://*.youtube.com/*`，`cookies`/`alarms` 权限）
- [ ] 5.2 popup：粘贴设备令牌完成配对、显示当前同步状态、知情同意提示
- [ ] 5.3 background service worker：`chrome.alarms` 定时推送 + `chrome.cookies.onChanged` 即时推送，仅读 youtube.com cookie
- [ ] 5.4 YouTube 登出（cookie 消失）时推空并通知
- [ ] 5.5 开发者模式 load-unpacked 手动验证：装扩展 → 配对 → 登录 YouTube → 后端 cookie 同步 → 内容分析下载受限内容成功 → YouTube 登出后状态变未登录

## 6. 安全与收尾

- [ ] 6.1 确认同步经 HTTPS、令牌可吊销、只 youtube.com、知情同意文案到位
- [ ] 6.2 评估并记录 cookie 落盘加密 / 短保留方案（design Open Question 收口）
- [ ] 6.3 `cd backend && python -m pytest -q` 与 `cd backend && ruff check .` 通过
- [ ] 6.4 文档：README / 设置页说明扩展安装与配对步骤
