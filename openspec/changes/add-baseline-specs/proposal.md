## Why

TradingRadar 已完成一期主要功能（鉴权、信源采集、内容流、宏观看板、财经日历、个股基本面、行业研报），但仓库内没有任何 OpenSpec 规格文档。当前"真相"只散落在代码、测试和 `CLAUDE.local.md` 进度记录中，缺少可审查、可演进的能力契约。本次变更为现有代码逆向补齐一套 baseline spec，把已实现的行为沉淀为正式规格，作为后续所有变更的基线。

本变更**只产出规格文档，不修改任何应用代码**。

## What Changes

- 为 9 个已实现的能力各创建一份 `specs/<capability>/spec.md`，逆向梳理现有行为，用 `## Requirements` + `#### Scenario` 描述。
- 规格内容以现有路由（`/api/*`）、service、模型与前端视图的实际行为为准，不引入新功能、不改变现有行为。
- 不修改后端/前端任何源码、迁移或配置；任务以"核对规格与现有代码一致"为目标，而非实现新功能。

## Capabilities

### New Capabilities
- `authentication`: 用户注册、登录、JWT 签发与校验、获取当前用户。
- `source-management`: 信源（DataSource）增删改查与 resolver 解析校验，按平台/板块维度管理订阅。
- `content-collection`: 多平台采集器（twitter/youtube/jin10/rss）+ 调度器 + 抓取日志 + 内容项（ContentItem）入库与信息流展示。
- `feishu-notification`: 飞书 webhook 配置（FeishuWebhook）与内容推送通知。
- `user-settings`: 用户级偏好设置（UserSettings）的读取与更新。
- `macro-dashboard`: 宏观指标（FRED 真实数据）观测入库、判断引擎与趋势序列看板。
- `economic-calendar`: 宏观/财报统一日历（CalendarEvent）、可插拔 provider 刷新与用户关注代码（TrackedTicker）。
- `stock-fundamentals`: 个股基本面多 provider（finnhub/fmp/quartr/sec_edgar）聚合查询。
- `industry-research`: 行业研报 RSS 信源聚合与展示。

### Modified Capabilities
<!-- 无：仓库当前无任何已存在规格，本次全部为新建 baseline -->

## Impact

- 新增文件：`openspec/changes/add-baseline-specs/` 下的 proposal/design/tasks 及 9 份 `specs/<capability>/spec.md` delta。
- 不触及：`backend/`、`frontend/`、`nginx/` 任何源码、Alembic 迁移、`.env` 与依赖。
- 归档后：9 份规格将合并进 `openspec/specs/`，成为后续变更的基线契约。
- 风险：baseline 为逆向描述，可能与代码细节存在偏差；tasks 阶段需逐能力对照代码核验。
