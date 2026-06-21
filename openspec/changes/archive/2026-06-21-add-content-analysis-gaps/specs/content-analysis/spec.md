## ADDED Requirements

### Requirement: Cookies 登录态活体探测
系统 SHALL 提供 `POST /api/content-analysis/login/probe` 接口，用当前保存的 cookies 实际请求 YouTube 并读取其登录标记，判定 cookies 是否**真正**处于登录态，区分「确认已登录 / 确认未登录（失效）/ 无法判定」三态，供前端按需复查会话有效性。该探测不阻塞事件循环且带网络超时。

#### Scenario: 确认已登录
- **WHEN** 已登录用户在有有效 cookies 时调用活体探测
- **THEN** 系统用该 cookies 请求 YouTube，YouTube 返回已登录标记
- **AND** 接口返回 state=logged_in（ok=true）及说明信息

#### Scenario: 确认已失效
- **WHEN** cookies 文件格式正确但已被 YouTube 注销/失效
- **THEN** 系统探测到未登录标记，返回 state=logged_out（ok=false）并提示需重新导出 cookies
- **AND** 系统不擅自清除 cookies 文件（保守，留待用户处理）

#### Scenario: 无法判定
- **WHEN** 探测请求因网络问题失败或 YouTube 页面格式变化无法读到登录标记
- **THEN** 系统返回 state=inconclusive，提示无法判定，不将其当作失效

#### Scenario: 无 cookies
- **WHEN** 当前用户尚未保存任何 cookies 即发起探测
- **THEN** 系统返回未登录/无 cookies 的明确结果，不报 500

#### Scenario: 未登录
- **WHEN** 未携带有效令牌调用探测接口
- **THEN** 系统返回 401

### Requirement: YouTube 登出
系统 SHALL 提供 `POST /api/content-analysis/logout` 接口，清除当前用户已保存的 YouTube cookies，使后续下载回到未登录状态，便于换账号或排障。

#### Scenario: 清除已保存的 cookies
- **WHEN** 已登录用户在已保存 cookies 时调用登出
- **THEN** 系统删除其 cookies 文件并返回成功

#### Scenario: 无 cookies 时登出
- **WHEN** 当前用户本就没有保存 cookies
- **THEN** 系统返回成功（幂等），不报错

#### Scenario: 未登录
- **WHEN** 未携带有效令牌调用登出接口
- **THEN** 系统返回 401

### Requirement: 来源回收站（软删除 / 还原 / 彻底清除）
系统 SHALL 支持来源（Source）软删除：删除来源默认进回收站（清除其产物的磁盘文件与产物记录、保留来源条目并标记删除时间），并提供列出回收站、还原、彻底清除（purge）能力。所有操作仅限本人数据。

#### Scenario: 软删除进回收站
- **WHEN** 用户删除其某个来源（默认行为，不带 purge）
- **THEN** 系统删除该来源下全部产物记录及其磁盘文件，保留来源记录并标记删除时间
- **AND** 该来源不再出现在正常产物列表中

#### Scenario: 列出回收站
- **WHEN** 用户请求回收站列表
- **THEN** 系统返回其已软删除的来源，按删除时间倒序，含标题/作者/删除时间

#### Scenario: 还原来源
- **WHEN** 用户还原回收站中的某来源
- **THEN** 系统清除其删除标记，该来源重新出现在正常列表中（产物已在软删时清除，用户可重新发起下载）

#### Scenario: 彻底清除
- **WHEN** 用户对某来源执行彻底清除（purge），或删除时显式指定 purge
- **THEN** 系统永久删除该来源记录及其全部产物与磁盘文件，不进回收站

#### Scenario: 操作他人或不存在来源
- **WHEN** 用户软删除/还原/清除不存在或不属于自己的来源
- **THEN** 系统返回失败（404/错误状态），不影响他人数据

### Requirement: 对信源已抓取内容一键发起下载/转写
系统 SHALL 提供 `POST /api/content-analysis/from-content-item/{content_item_id}` 接口，使用户能对信源里已抓取的 YouTube 内容（`content_item`）直接发起下载（可选模式 video/audio），复用既有下载/转写链路，无需手动复制粘贴 URL。仅限本人且仅限 YouTube 类型信源。

#### Scenario: 对 YouTube 内容发起下载
- **WHEN** 已登录用户对一条属于自己、来源为 YouTube 的 content_item 发起下载
- **THEN** 系统取该内容的 content_url，创建/复用对应内容分析来源并创建下载产物，后台执行下载（与手动粘贴 URL 同链路）
- **AND** 返回处于排队状态的产物，便于前端跳转查看进度
- **AND** 下载完成后按现有配置可自动转写

#### Scenario: 非 YouTube 内容
- **WHEN** 用户对来源非 YouTube（如 twitter）的 content_item 发起下载
- **THEN** 系统返回 400 并提示仅支持 YouTube 内容

#### Scenario: 他人或不存在的内容
- **WHEN** 用户对不存在或不属于自己的 content_item 发起下载
- **THEN** 系统返回 404

#### Scenario: 未登录
- **WHEN** 未携带有效令牌调用该接口
- **THEN** 系统返回 401

## MODIFIED Requirements

### Requirement: 删除产物与来源
系统 SHALL 提供 `DELETE /api/content-analysis/artifacts/{aid}` 删除单个产物（硬删除，可选同时删除磁盘文件），以及 `DELETE /api/content-analysis/sources/{sid}` 删除整个来源；其中来源删除**默认进回收站（软删除）**，可通过参数（如 `purge=true`）改为彻底删除。仅限本人数据。

#### Scenario: 删除单个产物
- **WHEN** 用户删除其某个产物，可带 delete_file 参数
- **THEN** 系统删除该产物记录，并按参数决定是否删除对应磁盘文件

#### Scenario: 删除整个来源（默认软删除）
- **WHEN** 用户删除其某个来源且未指定 purge
- **THEN** 系统将该来源软删除进回收站（清产物与文件、保留来源条目）

#### Scenario: 删除整个来源（彻底删除）
- **WHEN** 用户删除其某个来源并指定 purge=true
- **THEN** 系统永久删除该来源及其全部产物与磁盘文件，不进回收站

#### Scenario: 删除他人或不存在数据
- **WHEN** 用户删除不存在或不属于自己的产物/来源
- **THEN** 系统返回失败（404/错误状态），不影响他人数据

### Requirement: 转写后端与登录状态查询
系统 SHALL 提供 `GET /api/content-analysis/status` 接口，返回当前 Whisper 转写后端的可用性（及后端标识）、是否已存在 cookies，以及基于静态校验的 YouTube 登录态，供前端决定是否可发起转写/受限下载；活体探测（实际向 YouTube 校验）单独经 `POST /login/probe` 触发，状态接口不每次打网络。

#### Scenario: 查询状态
- **WHEN** 已登录用户调用状态接口
- **THEN** 系统返回转写后端是否可用与其标识、是否已存在 cookies，以及静态校验得到的 YouTube 登录态

### Requirement: YouTube Cookies 登录
系统 SHALL 提供 cookies 登录能力（`POST /api/content-analysis/login/cookies` 与从本机浏览器导入 `POST /api/content-analysis/login/browser`），以便下载需要登录的受限内容；保存成功后系统 SHALL 追加一次活体探测，把探测结果并入返回信息（探测失败或不可达不回滚已保存的 cookies，仅作提示）。

#### Scenario: 粘贴 cookies 登录
- **WHEN** 用户提交 Netscape 格式的 youtube.com cookies
- **THEN** 系统保存并启用该 cookies 用于后续下载，并追加活体探测，返回登录结果与探测信息

#### Scenario: 从浏览器导入登录
- **WHEN** 用户选择本机浏览器导入 cookies
- **THEN** 系统读取该浏览器 cookies 并启用，追加活体探测，返回登录结果与探测信息

#### Scenario: 保存成功但活体探测未通过
- **WHEN** cookies 静态保存成功，但活体探测判定未登录或不可达
- **THEN** 系统保留已保存的 cookies，返回中附带探测的提示信息，不回滚保存
