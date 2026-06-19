## Context

TradingRadar 一期已落地 10 个 API 路由组、对应 service 与 13 张数据模型，但仓库无任何 OpenSpec 规格。本变更是一次 **baseline backfill**：把现有行为逆向沉淀为规格，不改代码。难点不在实现，而在"如何切分能力边界"与"规格忠实于现状而非理想态"。

现状（已核对 `app/main.py` 路由注册 + `app/services/` + `app/models/models.py`）：

```
/api/auth            → authentication
/api/data-sources    → source-management
/api/content-items   ┐
/api/crawl-logs      ┘→ content-collection (+ crawlers/ + scheduler)
/api/webhooks        → feishu-notification
/api/settings        → user-settings (+ 飞书测试，与 notification 重叠)
/api/macro           → macro-dashboard
/api/calendar        → economic-calendar
/api/fundamentals    → stock-fundamentals
/api/research        → industry-research
```

## Goals / Non-Goals

**Goals:**
- 为 9 个能力各产出一份忠实于现有代码的 `spec.md`（ADDED Requirements）。
- 规格可作为后续变更的差异基线，并能映射到现有测试用例。
- 能力边界稳定、互不重叠，命名 kebab-case。

**Non-Goals:**
- 不修改任何后端/前端源码、迁移、依赖、配置。
- 不补全或纠正现有行为中的瑕疵（如 settings 与 webhooks 的飞书配置重叠）——只如实记录。
- 不为尚未实现的功能（如内容分析/大模型）写规格。

## Decisions

**决策 1：按"路由组 + service + 模型"三方对齐切 9 个能力，而非按前端视图。**
- 理由：后端契约是真相来源，前端视图会复用多个后端能力（如 ControlCenter 同时用 crawl-logs/settings/webhooks）。
- 备选：按前端视图切（11 个 view）→ 否决，边界会随 UI 重构漂移。

**决策 2：source-management 与 content-collection 拆开。**
- 理由：前者是用户对信源的 CRUD + resolver 校验（同步、面向用户）；后者是采集器/调度/抓取日志/内容流（后台管线 + 展示）。职责与触发方式不同。
- 备选：合并为 content-pipeline → 否决，规格会过大且混杂。

**决策 3：feishu-notification 与 user-settings 各自独立，如实记录其重叠。**
- 现状中飞书配置同时存在于 `/api/settings/feishu`（UserSettings.feishu_webhook_url）与 `/api/webhooks/feishu`（FeishuWebhook 多条）。两套并存是既成事实。
- 规格分别描述各自端点，不在 baseline 阶段做归并。重叠记入下方风险与 Open Questions。

**决策 4：规格粒度到"端点行为 + 关键校验/去重/排序规则"，不下沉到字段级 schema。**
- 理由：baseline 要可读、可演进；字段细节随 schema 演化，写进规格会高频失配。
- 每个 Requirement 至少一个 Scenario，用 WHEN/THEN，尽量对应一个可测断言。

## Risks / Trade-offs

- [逆向偏差] 规格基于阅读代码归纳，可能与边缘行为不符 → tasks 阶段逐能力对照路由 + 现有 pytest 用例核验。
- [现状含重叠/瑕疵] 如实记录可能让规格看起来"不优雅" → 接受；baseline 反映现状，优化留给后续独立变更。
- [外部依赖耦合] macro/calendar/fundamentals/research 依赖 FRED/FMP/finnhub 等外部 API → 规格描述"行为契约"，把"未配 key/外部失败"作为显式 Scenario，不绑定具体 provider 实现。
- [能力边界后续微调] 9 个划分一旦 archive 进 `openspec/specs/` 即成基线，后续调整需走变更 → 通过本设计先锁定边界，降低返工。

## Migration Plan

1. 本变更仅新增 `openspec/changes/add-baseline-specs/` 下文档，无部署、无回滚风险。
2. `/opsx:apply` 阶段逐 capability 核对规格与代码/测试一致。
3. `openspec validate add-baseline-specs --strict` 通过后，`/opsx:archive` 将 9 份 delta 合并进 `openspec/specs/`。
4. 回滚：删除变更目录即可，对运行系统无影响。

## Open Questions

- 飞书通知的两套配置（settings vs webhooks）是否在后续变更中归并为单一来源？（baseline 不处理）
- content-collection 中的调度策略、去重键、通知触发是否需要进一步拆为独立能力？（当前合为一个，待用量验证）
- `industry-research` 与 `stock-fundamentals` 均围绕"个股投研"，未来是否合并为投研域？（暂保持独立）
