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
系统 SHALL 提供 `DELETE /api/content-analysis/artifacts/{aid}` 与 `DELETE /api/content-analysis/sources/{sid}` 接口，删除单个产物或整个来源及其产物，并可选是否同时删除磁盘文件。仅限本人数据。

#### Scenario: 删除单个产物
- **WHEN** 用户删除其某个产物，可带 delete_file 参数
- **THEN** 系统删除该产物记录，并按参数决定是否删除对应磁盘文件

#### Scenario: 删除整个来源
- **WHEN** 用户删除其某个来源，可带 delete_files 参数
- **THEN** 系统删除该来源及其全部产物，并按参数删除磁盘文件

#### Scenario: 删除他人或不存在数据
- **WHEN** 用户删除不存在或不属于自己的产物/来源
- **THEN** 系统返回失败（404/错误状态），不影响他人数据

### Requirement: 转写后端与登录状态查询
系统 SHALL 提供 `GET /api/content-analysis/status` 接口，返回当前 Whisper 转写后端的可用性（及后端标识）与 YouTube 登录态，供前端决定是否可发起转写/受限下载。

#### Scenario: 查询状态
- **WHEN** 已登录用户调用状态接口
- **THEN** 系统返回转写后端是否可用与其标识，以及当前 YouTube 登录态

### Requirement: YouTube Cookies 登录
系统 SHALL 提供 cookies 登录能力（如 `POST /api/content-analysis/login/cookies` 与从本机浏览器导入 `POST /api/content-analysis/login/browser`），以便下载需要登录的受限内容。

#### Scenario: 粘贴 cookies 登录
- **WHEN** 用户提交 Netscape 格式的 youtube.com cookies
- **THEN** 系统保存并启用该 cookies 用于后续下载，返回登录结果

#### Scenario: 从浏览器导入登录
- **WHEN** 用户选择本机浏览器导入 cookies
- **THEN** 系统读取该浏览器 cookies 并启用，返回登录结果与信息

