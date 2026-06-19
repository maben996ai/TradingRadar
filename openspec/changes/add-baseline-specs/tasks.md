## 1. 核验各能力规格与现有代码一致

- [ ] 1.1 authentication：对照 `app/api/auth.py`、`app/core/security.py`、`app/api/deps.py` 核验注册/登录/me/鉴权场景，确认无不符
- [ ] 1.2 source-management：对照 `app/api/data_sources.py`、`app/services/resolver.py` 核验 CRUD、resolver、重复/首抓场景
- [ ] 1.3 content-collection：对照 `app/api/content_items.py`、`app/api/crawl_logs.py`、`app/services/crawlers/`、`app/services/scheduler.py` 核验采集/去重/调度/日志/内容流
- [ ] 1.4 feishu-notification：对照 `app/api/webhooks.py`、`app/services/notifiers/feishu*.py` 核验 webhook CRUD、测试、卡片推送
- [ ] 1.5 user-settings：对照 `app/api/settings.py` 核验读取/更新/测试与自动建记录
- [ ] 1.6 macro-dashboard：对照 `app/api/macro.py`、`app/services/macro/` 核验看板/规则引擎/刷新/定时首启
- [ ] 1.7 economic-calendar：对照 `app/api/calendar.py`、`app/services/calendar/` 核验事件查询/刷新/关注代码/定时首启
- [ ] 1.8 stock-fundamentals：对照 `app/api/fundamentals.py`、`app/services/fundamentals/` 核验 sources/download/files 与越权防护
- [ ] 1.9 industry-research：对照 `app/api/research.py`、`app/services/research/` 核验 sources/resolve/search

## 2. 与现有测试对齐

- [ ] 2.1 浏览 `backend/tests/`，将每条 Scenario 尽量映射到已有 pytest 用例，标注无对应用例的规格点
- [ ] 2.2 对发现的规格与代码不符之处，修正 spec 文本（baseline 以现状为准，不改代码）

## 3. 校验与归档准备

- [ ] 3.1 运行 `openspec validate add-baseline-specs --strict` 并修复所有报错
- [ ] 3.2 运行 `openspec show add-baseline-specs` 复核 9 个 capability 均被识别
- [ ] 3.3 确认未改动任何 `backend/`、`frontend/`、`nginx/` 源码（`git status` 仅含 openspec/ 变更）
