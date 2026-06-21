# 内容分析能力补齐（活体探测 / 登出 / 回收站 / 信源内容打通）

## Why
TradingRadar 已整套移植并增强了 yt-dlp-x 的内容分析能力（YouTube 下载 → Whisper 转写 → 产物管理 → cookies 登录），但相对源项目仍有几处遗漏，且现有「内容分析」与已抓取的信源内容（`content_item`）尚未打通：

- 登录态目前只做**静态校验**（解析 cookies 文件是否含 SID/LOGIN_INFO 且未过期），无法发现「cookies 格式正确但已被 YouTube 注销/失效」的情况，用户会在下载时才撞墙。
- 没有登出能力，换账号或排障时无法清除当前 cookies。
- 删除只有**硬删除**，误删无法挽回；源项目有软删除回收站（soft_delete + 还原 + purge）。
- 用户只能手动粘贴 YouTube URL 发起下载/转写，无法直接对信源里已抓取的 YouTube 内容（`content_item`）一键发起，链路割裂。

## What Changes
在**现有** `backend/app/services/content_analysis/` + `backend/app/api/content_analysis.py` 与前端 `/content-analysis` 页上增强，不新建并行模块：

1. **缺口 A — cookies 活体探测**：新增「活体探测」，用保存的 cookies 实际请求 YouTube 首页并读取其 `"LOGGED_IN":true|false`，区分「确认已登录 / 确认未登录（失效）/ 网络不可达无法判定」三态；并入登录与状态查询，提供按需重检接口。
2. **缺口 B — 登出**：新增清除当前用户 YouTube cookies 的登出接口与前端入口。
3. **缺口 D — 回收站（软删除）**：来源删除默认进回收站（软删除，可选清磁盘文件并保留记录），支持列出回收站、还原、彻底清除（purge）。保留现有硬删除产物的语义。
4. **content_item 打通**：在信源已抓取的 YouTube 内容（`content_item`）上提供一键发起下载/转写，复用现有下载/转写链路（`runner.run_download` 等），不另起一套。

**不做（明确排除）**：缺口 C（PO token provider / Deno，环境重，留作后续独立变更）；不接入任何大模型 / LLM（投研分析另行立项，本轮不实现）。

## Impact
- Affected specs: `content-analysis`（MODIFIED 登录/状态/删除三项 + ADDED 活体探测/登出/回收站/信源内容打通）
- Affected code:
  - 后端：`app/models/models.py`（`AnalysisSource` 加软删除字段）、新增 alembic 迁移、`app/schemas/schemas.py`、`app/services/content_analysis/cookies.py`（live probe / clear）、`store.py`（soft delete / restore / purge / deleted_view）、`app/api/content_analysis.py`（新增路由）
  - 前端：`src/api/contentAnalysis.ts`、`src/api/content.ts`（或新增对接）、`src/i18n.ts`、`src/views/ContentAnalysisView.vue`（登出/重检/回收站 UI）、`src/views/SourceFeedView.vue`（YouTube 内容一键下载入口）
- 数据迁移：`analysis_sources` 增加软删除列（向后兼容，默认未删除）
