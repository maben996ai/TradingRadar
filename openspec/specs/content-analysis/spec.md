# content-analysis Specification

## Purpose
TBD - created by archiving change add-content-analysis. Update Purpose after archive.
## Requirements
### Requirement: 下载 YouTube 音视频产物
系统 SHALL 提供 `POST /api/content-analysis/download` 接口，接收 YouTube URL 与下载模式（video/audio），为当前用户创建或复用对应来源（Source），并发起下载，产出 video 或 audio 产物（Artifact）。下载为后台任务，接口立即返回处于排队状态的产物。

#### Scenario: 发起视频下载
- **WHEN** 已登录用户提交有效 YouTube URL 与 mode=video
- **THEN** 系统创建/复用该用户对应来源，创建一个 stage=download、status=queued 的 video 产物并返回
- **AND** 后台执行下载，期间将产物状态推进为 running/processing 并回写进度，完成后置为 finished 并记录文件路径与大小

#### Scenario: 发起音频下载
- **WHEN** 已登录用户提交有效 URL 与 mode=audio
- **THEN** 系统同样创建 audio 产物并在后台下载

#### Scenario: 缺少 URL
- **WHEN** 用户未提供 URL
- **THEN** 系统返回 400 并提示需输入视频 URL

#### Scenario: 未登录
- **WHEN** 未携带有效令牌调用下载接口
- **THEN** 系统返回 401

#### Scenario: 下载失败可观测
- **WHEN** 后台下载因外部原因（受限/风控/网络）失败
- **THEN** 系统将产物状态置为 error 并记录错误信息与完整报错日志

### Requirement: 音视频转写为文本
系统 SHALL 提供 `POST /api/content-analysis/artifacts/{aid}/transcribe` 接口，从指定的音/视频产物用 Whisper 转写出 text 产物，text 产物记录其来源产物（血缘）。转写为后台任务。

#### Scenario: 从媒体产物转写
- **WHEN** 用户对一个已完成的 audio/video 产物发起转写
- **THEN** 系统创建一个 stage=transcribe、status=queued 的 text 产物，记录 source_artifact 血缘，并在后台转写，完成后置 finished 并保存文本文件

#### Scenario: 转写后端不可用
- **WHEN** 当前环境无可用 Whisper 后端时发起转写
- **THEN** 系统返回明确错误，不创建无法完成的任务

#### Scenario: 非法的源产物
- **WHEN** 用户对不存在、非本人或不可转写的产物发起转写
- **THEN** 系统返回 400/404 并附原因

### Requirement: 按来源分组列出产物
系统 SHALL 提供 `GET /api/content-analysis/artifacts` 接口，返回当前用户的产物，按来源（Source）分组，每个来源下含其 video/audio/text 产物及各自状态/进度/血缘，并返回按类型的计数；支持按 type 过滤。

#### Scenario: 列出全部产物
- **WHEN** 已登录用户调用列表接口
- **THEN** 系统返回该用户名下按来源分组的产物及各类型计数

#### Scenario: 按类型过滤
- **WHEN** 用户传入 type=text（或 video/audio）
- **THEN** 系统仅返回该类型的产物分组结果

### Requirement: 获取产物文件
系统 SHALL 提供 `GET /api/content-analysis/artifacts/{aid}/file` 接口返回产物文件：文本以 inline UTF-8 返回，媒体以下载返回；目标路径必须位于下载根目录内。

#### Scenario: 获取文本产物
- **WHEN** 用户请求一个已完成的 text 产物文件
- **THEN** 系统以 inline UTF-8 返回文本内容

#### Scenario: 获取媒体产物
- **WHEN** 用户请求一个已完成的 video/audio 产物文件
- **THEN** 系统以文件下载方式返回

#### Scenario: 文件不存在或越权路径
- **WHEN** 产物文件不存在，或解析路径位于下载根目录之外
- **THEN** 系统分别返回 404 或 403

### Requirement: 取消进行中的任务
系统 SHALL 提供 `POST /api/content-analysis/artifacts/{aid}/cancel` 接口，取消处于排队/进行中的下载或转写任务。对已完成或无法终止的任务返回失败提示。

#### Scenario: 取消排队/进行中的任务
- **WHEN** 用户取消一个 queued/running 的产物任务
- **THEN** 系统标记取消，使其结果被丢弃并反映为不再继续

#### Scenario: 取消无法终止的任务
- **WHEN** 用户取消一个已完成的任务
- **THEN** 系统返回失败并提示该任务无法终止

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

