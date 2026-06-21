# 设计说明

## 现状与对齐
- 现有分层：`api/content_analysis.py`（仅入口）→ `services/content_analysis/{cookies,store,runner,backends}.py`。本变更严格沿用，路由不写业务逻辑。
- 数据持久化在 Postgres，按 `user_id` 隔离；`AnalysisSource(user, video_id 唯一)` 下挂 `AnalysisArtifact`（video/audio/text，`cascade all, delete-orphan`）。
- 源项目 yt-dlp-x 为单用户 + JSON 文件存储，本项目为多用户 + DB，移植时按本项目模型重写，不照搬其内存锁/JSON 结构。

## 决策一：活体探测（缺口 A）
- 在 `cookies.py` 新增 `live_probe(path=None) -> tuple[bool | None, str]`：用保存的 cookies 请求 `https://www.youtube.com/`，正则读 `"LOGGED_IN":\s*(true|false)`，返回三态：
  - `True` 确认已登录；`False` cookies 格式正确但 YouTube 判定未登录（失效）；`None` 网络不可达 / 页面格式变化，无法判定。
- 与现有 `validate_cookie_file()`（静态）并存：探测先做静态解析，再发网络请求。网络请求需短超时（约 15-20s）且**不阻塞事件循环**（在路由里用 `asyncio.to_thread` 包裹，或保持同步但加超时；优先 `to_thread`）。
- 新增 `POST /api/content-analysis/login/probe`：按需重检，返回 `{state: "logged_in"|"logged_out"|"inconclusive", ok, message}`。
- `login/cookies` 与 `login/browser` 成功保存后追加一次活体探测，把结果并入返回 message（探测失败/不可达不回滚保存，仅提示），对齐源项目语义。
- `GET /status` 的 `youtube_logged_in` 仍以静态校验为准（避免每次状态查询都打网络），活体探测单独走 `login/probe`。

## 决策二：登出（缺口 B）
- `cookies.py` 新增 `clear_cookies() -> bool`：删除当前用户 cookie 文件，存在并删除返回 True。
- 新增 `POST /api/content-analysis/logout`：调用 `clear_cookies()`，返回 `AnalysisLoginResponse`/`AnalysisActionResponse`。
- 注：当前 `cookie_file()` 为全局单文件（移植时为单文件），本变更不改其多用户分离策略（属现状，超出本轮范围）；登出即清该文件。

## 决策三：回收站 / 软删除（缺口 D）
- 模型：`AnalysisSource` 增加 `deleted_at: datetime | None`（NULL = 未删除，非 NULL = 在回收站）。alembic 迁移加列，默认 NULL，向后兼容。
- `list_sources` 默认只返回 `deleted_at IS NULL`。
- `store.soft_delete_source(db, sid, user)`：删除该来源下所有产物的磁盘文件、删除产物记录（清空产物，省磁盘），保留来源记录并置 `deleted_at`。
- `store.restore_source(db, sid, user)`：置 `deleted_at = NULL`（产物已被清空，还原后来源在列表里重新可见，用户可重新下载）。
- `store.purge_source(db, sid, user)`：彻底删除来源记录（等价现有 `remove_source(delete_files=True)`）。
- `store.deleted_sources(db, user)`：返回回收站列表（按 `deleted_at` 倒序）。
- 路由：
  - `DELETE /api/content-analysis/sources/{sid}` 改为**默认软删除**（进回收站）；保留 `?purge=true` 直接彻底删除（兼容旧的 `delete_files` 语义并入 purge）。
  - `GET /api/content-analysis/sources/deleted` 列回收站。
  - `POST /api/content-analysis/sources/{sid}/restore` 还原。
  - `POST /api/content-analysis/sources/{sid}/purge` 彻底清除。
- 产物级删除（`DELETE /artifacts/{aid}`）维持硬删除现状（回收站只针对来源，与源项目一致）。

## 决策四：content_item 打通（第 5 项）
- 复用现有下载链路：信源内容（`content_item`）的 YouTube 视频本质就是一个 `content_url`，发起下载等价于 `download(url=content_item.content_url)`。
- 新增 `POST /api/content-analysis/from-content-item/{content_item_id}`：
  - 校验该 content_item 属于当前用户（经 `data_source.user_id`）、其 `data_source.source_type == youtube`（非 youtube 返回 400）。
  - 取 `content_item.content_url` 走现有 `store.get_or_create_source` + `store.create_artifact` + `runner.run_download`，可带 `mode=video|audio`。
  - 复用现有「下载完成按配置自动转写」逻辑，无需新代码。
  - 返回新建的 `AnalysisArtifactResponse`，前端可跳转 `/content-analysis` 查看进度。
- 前端：`SourceFeedView.vue` 的 YouTube 视频卡片增加「下载/转写」入口，调用上面接口；不改信息流既有展示结构。

## 取舍 / 风险
- 活体探测依赖 YouTube 页面 `LOGGED_IN` 标记，格式若变化则降级为 `inconclusive`，不误判为失效（保守，不自动清 cookies）。
- 软删除后产物文件即删，还原仅恢复来源条目而非已删文件（与源项目一致：回收站省磁盘，还原后需重新下载）。设计如此，避免占着大文件。
- content_item 打通仅支持 YouTube（现有下载链路是 yt-dlp，twitter 等不在范围）。
