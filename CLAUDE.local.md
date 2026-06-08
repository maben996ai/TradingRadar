# CLAUDE.local.md — 开发进度记录

## 当前状态（2026-04-19）

### 已完成
- Feed 页 CSS 5 列网格（`.video-grid-sm`）Vite 缓存问题已修复（`docker compose restart frontend`）
- 前端导航与文案调整：
  - 标题：「投资信号驾驶舱」→「金融资讯」
  - 导航「动态」→「最新内容动态」
  - 导航「创作者」→「信源管理」
  - 「抓取日志」+「设置」合并为「控制中心」（`/control-center`，`ControlCenterView.vue`）
  - 新增「内容分析」导航入口（`/content-analysis`，`ContentAnalysisView.vue`，占位页面）
  - Feed 每页从 20 改为 15（5×3 网格，便于翻页验证）

### 已修改文件
| 文件 | 改动 |
|---|---|
| `frontend/src/i18n.ts` | nav.title/feed/creators 文案；新增 nav.controlCenter/contentAnalysis key；新增 contentAnalysis.* 消息块；更新 MessageKey 类型 |
| `frontend/src/views/FeedView.vue` | PAGE_SIZE 20→15 |
| `frontend/src/components/layout/AppShell.vue` | 导航链接调整为 /content-analysis 和 /control-center |
| `frontend/src/router/index.ts` | 路由替换：settings+crawl-logs → control-center+content-analysis |
| `frontend/src/views/ControlCenterView.vue` | 新建，合并 settings+crawlLogs 内容 |
| `frontend/src/views/ContentAnalysisView.vue` | 新建，占位页面 |

### 待验证
- 刷新浏览器确认 5 列网格正常（上次 Vite 已重启）
- 确认新导航路由均可访问（/content-analysis, /control-center）
- 确认翻页功能（15 条/页）

### 下一步主线
1. 打通飞书 Webhook 通知（控制中心配置表单）
2. 内容分析页接入大模型（视频摘要/投研洞察）
3. 控制中心展示真实抓取日志

## 开发环境注意事项

### 前端重启用 `up -d`，不要用 `restart`
- macOS Docker Desktop 上 `docker compose restart frontend` 偶发 bind-mount（`./frontend:/app`）未正确重挂，容器内 `/app/package.json` 瞬时不可见，`npm run dev` 立即 ENOENT 退出（退出码 254），表现为 `http://localhost:3000` 无法访问。
- 正确做法：`docker compose up -d frontend`（复用未变更镜像，仅重建容器，重新建立挂载）。
- 同理，删除/新增前端文件（如 `videos.ts`→`content.ts`）后，Vite 缓存偶尔不干净，也优先用 `up -d` 重建而非 `restart`。

## 进度（2026-06-08）：video → content_item 通用化改名

将「视频」专用模型泛化为通用内容模型（X 推文等非视频内容不再借用 video 字段）。后端 167 测试全过、ruff 通过；前端 type-check 通过。

- 模型：`Video`→`ContentItem`，表 `videos`→`content_items`，列 `platform_video_id`→`platform_id`、`video_url`→`content_url`，`CrawlLog.videos_found`→`items_found`
- 采集层：`CrawledVideo`→`CrawledItem`，方法 `fetch_latest_videos`→`fetch_latest_items`
- 对外契约：路由 `/api/videos`→`/api/content-items`，`app/api/videos.py`→`content_items.py`；schema `VideoResponse/VideoListResponse`→`ContentItemResponse/ContentItemListResponse`
- 前端：`api/videos.ts`→`content.ts`（`contentApi`，endpoint `/content-items`）、`types` 接口与字段、store/views 引用对齐；局部变量/CSS 类名/i18n 文案未改
- 迁移：`a7c3f1e29b84`（表/列/约束/索引/`items_found`）+ `b8d4e2f6a1c0`（主键 `videos_pkey`→`content_items_pkey`），均已 `alembic upgrade head` 应用到本地 PG，数据保留
- content_type 仍由用户在添加信源时通过 payload 选择（payload 驱动，未改）

## 进度（2026-06-08）：导航重构 + 社交媒体内容流

后端 168 测试通过、ruff 通过；前端 type-check 通过。

- **首次抓取失败可观测**：`_run_initial_crawl` 失败时除 warning 外，写一条 `CrawlLog(status=FAILED)`，避免信源一直停在「初始化中」（修复 X 限流 429 时的盲区）。
- **信源管理页**：tab 从「内容类型」改为「平台/板块」维度，5 个板块统一为 `金融时讯 / 社交媒体 / 财经视频 / 市场宏观 / 财经日历`；社交媒体(twitter)、财经视频(youtube)可添加，其余为占位。
- **左侧导航**：精简为「信源 / 分析 / 控制中心」三个一级 tab（放大字号，控制中心提升为一级）。信源段做成可展开树：社交媒体/财经视频展开为**真实订阅博主**（来自 `dataSourcesApi.list()`，点博主进 `SourceFeedView`），金融时讯/市场宏观/财经日历展开为静态占位分类。
- **聚合页下线**：删除 `FeedView.vue`（聚合信息流），新增 `PlatformFeedView.vue`（按平台过滤，`/feed/:platform`），`/` 默认重定向 `/feed/twitter`。
- **社交媒体 timeline（folo 风格）**：`SourceFeedView` 按 `source_type` 分流——twitter 用文本流（头像+作者+时间+正文），长推文折叠 6 行 + 「显示更多」；youtube 保持视频网格。
- **完整正文**：`ContentItemResponse` 新增 `content_text`（从 `raw_data.text` 取完整推文，回退 `title`）；前端 timeline 用之。
- **图片 lightbox**：推文配图点击打开全屏大图预览（点背景关闭），不再跳转 X；「查看原文」链接保留。
- 清理：删除多个 unused i18n key 与 `FeedView`；新增板块/静态分类/`showMore` 等 i18n（中英）。

## 进度（2026-06-08）：市场宏观看板模块（全栈，真实 FRED 数据）

后端 192 测试通过、ruff 通过；前端 type-check + build 通过。已在本地真实跑通（Postgres + FRED）。

**数据来源 / 选型**
- 数据源：**FRED 真实 API**（圣路易斯联储，免费）。`FRED_API_KEY` 已写入根 `.env`，并加入 `.env.example` 与 `config.py`（`fred_api_key`）。
- 趋势图：**手写内联 SVG 折线图**，无新依赖。判断：**规则引擎**（确定性，无 LLM）。

**后端**
- 模型：新增 `MacroObservation`（表 `macro_observations`，`indicator_key/date/value`，`UniqueConstraint(indicator_key,date)`）；指标元信息**不入库**，留代码注册表。
- 迁移：`d4a9c1b73e52_add_macro_observations`，已在容器内 `alembic upgrade head`（顺带补上之前未应用的 `c7f0a9d2e4b1`）。
- service：`services/macro/` — `indicators.py`（11 指标注册表 + `judge()`/`zone()`/`reason()`）、`fred_client.py`（httpx，跳过 `"."`，未配 key 抛 `FredApiError`）、`service.py`（`refresh_all` upsert + `build_dashboard` 算最新/前值/变化/判断/理由/zone + 完整 3Y 序列）。
- API：`/api/macro/indicators`（看板）、`/api/macro/refresh`（手动刷新，无 key 返回 502）。schema 在 `schemas.py`。
- 调度：`scheduler.py` 加 `refresh_macro_indicators` 每日 job + 首启空表自动拉取（已在 `_initial_macro_refresh` 用 key 守卫，避免测试触库）。
- 指标集（映射 6 方向）：FEDFUNDS/DGS10（利率）、CPI/核心PCE 同比（通胀）、实际GDP（增长）、失业率/非农（就业）、M2/2s10s（流动性）、VIX/高收益债利差（风险）。

**前端**
- 视图 `MacroMarketView.vue`（`/macro-market`）：**单个面板 + 一个网格**铺全部指标卡（按方向排序，方向用彩色圆点徽标）；卡片含 最新值/前值/变化(红绿箭头)/更新时间/来源/判断徽标/一句话理由/基本解释。
- **每卡独立**时间范围 `3M/6M/1Y/3Y`（默认 1Y，`ranges` 按 key 各存各的；非全局）。
- 图表组件 `components/macro/MacroLineChart.vue`：平滑贝塞尔曲线 + 网格线 + 明亮渐变 + 端点/ hover 圆点 + tooltip + 极值标注 + **阈值虚线(橙高/蓝低)与标签**。
- **预警阈值/极端说明/预测**：注册表加 `high/low/high_note/low_note/zone/forecast/forecast_label/forecast_source` 并贯通 schema→types。卡片图下方显示「预警区间 + 当前档位徽标(高位/正常/低位) + 命中那条极端影响高亮」；联邦基金利率给「预测」块（人工参考值，来源标 **CME FedWatch**，非实时）。
- 导航：`AppShell.vue` 市场宏观**删除所有子项**，改为单一二级入口直达 `/macro-market`（清理 `macroItems`/`openMacro`）。
- i18n：新增 `macro.*` 中英块（区间/判断/zone/预警/预测）+ `MessageKey`。样式集中加在 `styles.css` 末段。

**待办 / 备注**
- FedWatch 预测目前是注册表人工参考值；FRED 不含该数据，后续要实时需单独接 CME / 利率期货隐含概率。
- 各 series 频率不一（日/月/季），趋势图按实际点绘制不插值；日频指标「前值」为上一交易日，短期噪声较大。
- 临时验证账号：`macrocheck@example.com` / `password123`。

## 进度（2026-06-09）：财经日历模块（全栈，可插拔 provider；财报接 FMP 真实）

后端 208 测试通过、ruff 通过；前端 type-check + build 通过。已在本地真实跑通（Postgres + FRED + FMP）。

**数据选型（已确认）**
- 可插拔 provider：宏观 **精选发布日程 + FRED 回填**（过去 actual/previous 为 FRED 真实值；预期值需 TE 付费层，暂空）；财报 **FMP 真实**。
- 实测 FMP key 仅 `stable/earnings`(-calendar) 可用，`economic-calendar` 付费受限 → 宏观不走 FMP。`.env` 加 `FMP_API_KEY`（已填）、`TRADING_ECONOMICS_API_KEY`（留空）；同步 `config.py` + `.env.example`。

**后端**
- 模型：`CalendarEvent`（宏观+财报统一，`event_key` 唯一去重，kind/category/scheduled_at(UTC)/importance/previous/forecast/actual/ticker/source 等）+ 用户级 `TrackedTicker`（`UniqueConstraint(user_id,ticker)`，镜像 `FeishuWebhook`）。
- 迁移：`e5b7c3a91f24_add_calendar_events_and_tracked_tickers`，容器内已 `alembic upgrade head`。
- `services/calendar/`：`events.py`（精选事件定义 17 项 + FOMC 2026 日程 + 默认重点公司）、`provider.py`（`CalendarProvider` 抽象；`SeedProvider` 按节奏生成 + FRED 回填；`TradingEconomicsProvider`；`FmpProvider` 用 `stable/earnings` 逐代码拉真实财报日+EPS）、`service.py`（`refresh_all` 按 key 选源、汇总「默认公司∪用户关注」symbols 传财报 provider、**删窗口内旧事件+重建**避免占位/改期残留；`list_events` 支持 分类/重要性/范围/kind/tracked_only 筛选）。
- API `/api/calendar`：`/events`（多维筛选）、`/refresh`、`/tracked-tickers` CRUD。`main.py` 注册；`scheduler.py` 加 `refresh_calendar_events` 每日 job + 首启空表自动生成。

**前端**
- 视图 `CalendarView.vue`（`/calendar`，jin10 风格）：事件按所选**时区分组到日期**，列 时间/重要性★/事件/前值/预期/实际/影响资产/来源；财报行带「关注/已关注」切换。
- 筛选：分类多选 chips、重要性、**北京↔美东切换**（前端按时区重排分组，查询用 UTC 边界+1天缓冲）、日期范围（今天/未来7天/未来30天 + 自定义）。`fmtValue` 字母单位(EPS)加空格。
- 关注：`tracked-tickers` 增删 + 「仅看关注」过滤；关注代码全局汇总进刷新，下次该代码真实财报日由 FMP 拉入。
- 导航：`AppShell.vue` 财经日历**删除 3 个子项**，改为单一入口 `/calendar`（清理 `calendarItems`）。
- `api/calendar.ts`、`types`（`CalendarEvent`/`TrackedTicker`）、`i18n` `calendar.*` 中英 + `MessageKey`、`styles.css` 末段日历样式。

**真实验证**：63 事件 = 54 宏观（通胀/就业/利率/增长，历史值 FRED 真实）+ 9 财报（FMP：NVDA 5/20 实际 EPS 1.87 vs 预期 1.76、AAPL 7/30 等真实日期+预期，来源 FMP）。

**待办 / 备注**
- 宏观「预期值」仍需 TE 付费层；`TradingEconomicsProvider` 已就位，配 `TRADING_ECONOMICS_API_KEY` 即切。
- 精选发布**日期为待校准**（公开日程近似），actual/previous 为 FRED 真实。
- FMP 仅对「默认公司 ∪ 已关注代码」拉取，避免日历被全市场财报淹没。
