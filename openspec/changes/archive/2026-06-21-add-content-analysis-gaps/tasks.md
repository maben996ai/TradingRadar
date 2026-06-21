# Tasks

## 1. 后端 schema 与模型
- [ ] 1.1 `models.py`：`AnalysisSource` 增加 `deleted_at: datetime | None`（默认 NULL）
- [ ] 1.2 新增 alembic 迁移：`analysis_sources` 加 `deleted_at` 列（向后兼容）
- [ ] 1.3 `schemas.py`：新增 `AnalysisProbeResponse`（state/ok/message）、`AnalysisDeletedSourceResponse`、`AnalysisFromContentItemRequest`（mode）；按需扩展 `AnalysisLoginResponse`

## 2. 后端 service / 路由
- [ ] 2.1 `cookies.py`：新增 `live_probe()`（三态）与 `clear_cookies()`
- [ ] 2.2 `cookies.py`：`save_text_cookies` / `import_from_browser` 成功后并入活体探测信息
- [ ] 2.3 `store.py`：`soft_delete_source` / `restore_source` / `purge_source` / `deleted_sources`；`list_sources` 默认排除已软删除
- [ ] 2.4 `content_analysis.py`：新增 `POST /login/probe`、`POST /logout`
- [ ] 2.5 `content_analysis.py`：`DELETE /sources/{sid}` 改默认软删除 + `purge` 参数；新增 `GET /sources/deleted`、`POST /sources/{sid}/restore`、`POST /sources/{sid}/purge`
- [ ] 2.6 `content_analysis.py`：新增 `POST /from-content-item/{content_item_id}`（校验本人 + YouTube，复用 download 链路）

## 3. 后端测试
- [ ] 3.1 活体探测三态、登出（含幂等）、保存 cookies 后并入探测信息
- [ ] 3.2 软删除/还原/彻底清除/回收站列表 + 越权 404
- [ ] 3.3 from-content-item：YouTube 成功、非 YouTube 400、他人/不存在 404

## 4. 前端 api / i18n / types
- [ ] 4.1 `contentAnalysis.ts`：`probe()`、`logout()`、`deletedSources()`、`restoreSource()`、`purgeSource()`、`deleteSource` 支持 purge、`fromContentItem()`
- [ ] 4.2 `types`：探测三态、回收站条目类型
- [ ] 4.3 `i18n.ts`：登出/重检/三态/回收站/还原/彻底清除/一键下载 中英文案 + MessageKey

## 5. 前端 UI
- [ ] 5.1 `ContentAnalysisView.vue`：登录区加「重新检测（活体探测）」与「登出」入口及三态提示
- [ ] 5.2 `ContentAnalysisView.vue`：删除来源走软删除 + 回收站面板（列出/还原/彻底清除）
- [ ] 5.3 `SourceFeedView.vue`：YouTube 视频卡片加「下载/转写」入口，调用 from-content-item
