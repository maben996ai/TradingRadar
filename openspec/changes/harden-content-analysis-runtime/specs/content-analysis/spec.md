## MODIFIED Requirements

### Requirement: 音视频转写为文本
系统 SHALL 提供 `POST /api/content-analysis/artifacts/{aid}/transcribe` 接口，从指定的音/视频产物用 Whisper 转写出 text 产物，text 产物记录其来源产物（血缘）。转写为后台任务。

转写不单独抽取音频：Whisper 后端 SHALL 经系统 ffmpeg 直接从音/视频文件解码音轨进行转写（视频也无需先转码为音频文件）。

转写成功后系统 SHALL 默认删除其源音/视频产物（记录与磁盘文件），仅保留 text 产物以节省磁盘；该行为 SHALL 可通过配置（`content_analysis_delete_source_after_transcribe`）关闭，关闭时保留源产物。

转写取消为**软取消**：模型推理过程无法中途终止，系统 SHALL 在推理结束后丢弃其结果（不写出 text 产物文件、不置 finished），且取消时 SHALL **不删除源音/视频产物**。

中文转写结果 SHALL 默认转换为简体：Whisper（openai/mlx）对中文普遍输出繁体，系统 SHALL 在转写产出文本后、写出 text 产物文件前，对**中文**文本用 opencc（繁→简）做后处理转为简体；该行为 SHALL 可通过配置（`transcribe_to_simplified`，默认开启）关闭。非中文（如英文）文本 SHALL **不被破坏**。

#### Scenario: 从媒体产物转写
- **WHEN** 用户对一个已完成的 audio/video 产物发起转写
- **THEN** 系统创建一个 stage=transcribe、status=queued 的 text 产物，记录 source_artifact 血缘，并在后台转写，完成后置 finished 并保存文本文件

#### Scenario: 经 ffmpeg 从视频直接解码音轨
- **WHEN** 源产物为 video 且发起转写
- **THEN** 系统不单独生成音频文件，Whisper 经系统 ffmpeg 从该视频解码音轨完成转写

#### Scenario: 转写成功后默认删源
- **WHEN** 配置 `content_analysis_delete_source_after_transcribe` 为开启（默认）且转写成功
- **THEN** 系统先断开 text 对 media 的血缘外键，删除源音/视频产物记录与磁盘文件，仅保留 text 产物，并在 text 产物 meta 记录已删除源信息

#### Scenario: 配置关闭时保留源
- **WHEN** 配置 `content_analysis_delete_source_after_transcribe` 为关闭且转写成功
- **THEN** 系统保留源音/视频产物及其磁盘文件，不做删除

#### Scenario: 软取消转写
- **WHEN** 用户在转写进行中取消该 text 任务
- **THEN** 系统在模型推理结束后丢弃结果、将该 text 产物置为已终止，且不删除源音/视频产物（源保留可重试）

#### Scenario: 中文转写默认输出简体
- **WHEN** 配置 `transcribe_to_simplified` 为开启（默认）且转写出的中文文本含繁体
- **THEN** 系统在写出 text 产物文件前用 opencc 将其转为简体，落盘文本与下载的 text 产物均为简体

#### Scenario: 非中文转写不被破坏
- **WHEN** 转写结果为英文等非中文文本
- **THEN** 简体转换不改变其内容，文本原样落盘

#### Scenario: 关闭简体转换时保留原始结果
- **WHEN** 配置 `transcribe_to_simplified` 为关闭
- **THEN** 系统不做繁简转换，按 Whisper 原始输出落盘

#### Scenario: 转写后端不可用
- **WHEN** 当前环境无可用 Whisper 后端时发起转写
- **THEN** 系统返回明确错误，不创建无法完成的任务

#### Scenario: 非法的源产物
- **WHEN** 用户对不存在、非本人或不可转写的产物发起转写
- **THEN** 系统返回 400/404 并附原因

### Requirement: 下载 YouTube 音视频产物
系统 SHALL 提供 `POST /api/content-analysis/download` 接口，接收 YouTube URL 与下载模式（video/audio），为当前用户创建或复用对应来源（Source），并发起下载，产出 video 或 audio 产物（Artifact）。下载为后台任务，接口立即返回处于排队状态的产物。

下载链路 SHALL 依赖系统 ffmpeg：合并 bestvideo+bestaudio 为 mp4、提取音频转 mp3 均由 yt-dlp 调用系统 ffmpeg 完成；缺少 ffmpeg 时下载/转码会失败并被作为可观测错误回写。

受限/会员内容的 PO token provider（`bgutil-ytdlp-pot-provider`）为**未来项 / 当前未实现**：当前对受限内容依赖 cookies 登录，PO token 路径暂不提供。

#### Scenario: 发起视频下载
- **WHEN** 已登录用户提交有效 YouTube URL 与 mode=video
- **THEN** 系统创建/复用该用户对应来源，创建一个 stage=download、status=queued 的 video 产物并返回
- **AND** 后台执行下载，期间将产物状态推进为 running/processing 并回写进度，完成后置为 finished 并记录文件路径与大小

#### Scenario: 发起音频下载
- **WHEN** 已登录用户提交有效 URL 与 mode=audio
- **THEN** 系统同样创建 audio 产物并在后台下载，经系统 ffmpeg 提取并转码为 mp3

#### Scenario: 缺少 URL
- **WHEN** 用户未提供 URL
- **THEN** 系统返回 400 并提示需输入视频 URL

#### Scenario: 未登录
- **WHEN** 未携带有效令牌调用下载接口
- **THEN** 系统返回 401

#### Scenario: 下载失败可观测
- **WHEN** 后台下载因外部原因（受限/风控/网络）失败
- **THEN** 系统将产物状态置为 error 并记录错误信息与完整报错日志

### Requirement: 转写后端与登录状态查询
系统 SHALL 提供 `GET /api/content-analysis/status` 接口，返回当前 Whisper 转写后端的可用性（及后端标识）与 YouTube 登录态，以及下载/转码所需运行依赖（yt-dlp、系统 ffmpeg）的可用性，供前端决定是否可发起下载/转写/受限下载、并在缺依赖时禁用相关入口。

status 返回 SHALL 包含 `transcribe_available`、转写后端标识、`youtube_logged_in`、`yt_dlp_available`、`ffmpeg_available`。

#### Scenario: 查询状态
- **WHEN** 已登录用户调用状态接口
- **THEN** 系统返回转写后端是否可用与其标识、当前 YouTube 登录态、以及 `yt_dlp_available` 与 `ffmpeg_available`

#### Scenario: 缺运行依赖时如实上报
- **WHEN** 环境缺少 yt-dlp 或系统 ffmpeg
- **THEN** status 中对应的 `yt_dlp_available` / `ffmpeg_available` 返回 false，供前端禁用下载/转写入口

## ADDED Requirements

### Requirement: 内容分析运行依赖契约
系统 SHALL 要求内容分析的部署环境提供以下运行依赖：pip 包 `yt-dlp`（下载）、系统 `ffmpeg`（合并/转码/转 mp3/Whisper 解码音轨）、pip 包 `opencc`（中文转写结果繁→简后处理）、以及至少一个 Whisper 转写后端（Linux/docker 环境用 `openai-whisper`，macOS 宿主可选用 `mlx-whisper`）。这些依赖 SHALL 在 `backend/requirements.txt` 与镜像构建（`backend/Dockerfile`）中硬声明、不被注释屏蔽。

当任一运行依赖缺失时，系统 SHALL：(1) 通过 `GET /status` 如实上报对应不可用位；(2) 前端 SHALL 在缺依赖时展示告警条并禁用相关下载/转写入口；(3) 依赖接线冒烟测试 SHALL 在测试阶段拦截"requirements 声明了、但运行环境没装"的缺口。

依赖接线冒烟测试 SHALL **故意不打桩**——直接断言 `yt-dlp` 可导入、`ffmpeg` 在 PATH、`opencc` 可导入、且 `GET /status` 暴露 `yt_dlp_available` / `ffmpeg_available`，以确保它真正走到 `import yt_dlp` / 调 ffmpeg / `import opencc`，避免被功能测试的 mock 掩盖环境缺口。

受限/会员内容的 PO token provider（`bgutil-ytdlp-pot-provider`）为**未来项**，当前不属于强制运行依赖契约。

#### Scenario: 依赖在 requirements 与镜像中硬声明
- **WHEN** 检视 `backend/requirements.txt` 与 `backend/Dockerfile`
- **THEN** `yt-dlp`、`openai-whisper` 在 requirements 中未被注释，系统 `ffmpeg` 在 Dockerfile 中被 apt 安装

#### Scenario: 完整环境下依赖冒烟测试全绿
- **WHEN** 在装齐依赖的环境运行依赖接线冒烟测试
- **THEN** `yt-dlp` 可导入、`ffmpeg` 在 PATH、`opencc` 可导入、`backends.yt_dlp_available()` 与 `backends.ffmpeg_available()` 均为 true、`GET /status` 暴露这两个布尔字段

#### Scenario: 环境漏装依赖被测试拦截
- **WHEN** 镜像/环境漏装 yt-dlp、缺系统 ffmpeg 或漏装 opencc
- **THEN** 依赖接线冒烟测试失败（而非因 mock 掩盖而"符合规格"），暴露环境缺口

#### Scenario: 缺依赖时前端禁用入口
- **WHEN** `GET /status` 返回 `yt_dlp_available` 或 `ffmpeg_available` 为 false
- **THEN** 前端内容分析页与信源页展示依赖缺失告警条（i18n `contentAnalysis.depsMissing`）并禁用对应下载/转写入口

### Requirement: 宿主耦合功能在容器部署下的处理
系统 SHALL 对依赖"后端机器即用户本机"的宿主耦合功能——「在宿主文件管理器中定位文件（reveal）」与「从本机浏览器导入 cookies（login/browser）」——在 docker 等前后端分离/无 GUI 容器部署下做明确降级处理（容器无桌面文件管理器、无本机浏览器，这些功能无法工作）。

系统 SHALL 能判定当前部署是否支持这类宿主功能：以显式配置开关优先、容器环境检测（如存在 `/.dockerenv`）兜底，得出"宿主功能是否可用"的判定。

当宿主功能不可用时，宿主耦合接口（`POST /api/content-analysis/artifacts/{aid}/reveal`、`POST /api/content-analysis/login/browser`）SHALL 返回**明确错误**（如 501，附文案"该功能仅在 macOS/Windows 宿主直跑后端时可用"），SHALL **不静默成功**、**不抛未捕获的 500**、不去调用 `subprocess` 打开文件管理器或读取本机浏览器。

`GET /api/content-analysis/status` SHALL 增加上报宿主功能可用性（如 `host_features_available`），供前端在不可用时**隐藏或禁用**「打开文件夹」「从浏览器导入」入口，避免出现点了没反应的死按钮、避免用户点到注定失败的入口。

前端错误反馈 SHALL 按操作区分：内容分析页各操作（下载 / 转写 / 打开文件夹 reveal / 从浏览器导入 / 删除 / 还原 / 彻底清除 / 登出 / 活体探测）失败时，SHALL 在 catch 分支给出与该操作相符的提示文案，**不得统一复用「下载失败，请稍后重试」**（`contentAnalysis.downloadFailed`）。其中宿主耦合类操作（打开文件夹 / 从浏览器导入）在容器部署下不可用时，提示文案 SHALL 说明「该功能仅在桌面/宿主部署可用」，而非「下载失败」。各操作所需文案 key SHALL 在 `frontend/src/i18n.ts` 中按操作补齐（中英）并更新 `MessageKey`。

#### Scenario: 操作失败提示与操作相符
- **WHEN** 用户在内容分析页执行打开文件夹 / 删除 / 转写等非下载操作且该操作失败
- **THEN** 前端展示与该操作相符的错误文案（如「打开文件夹失败」「删除失败」），不复用「下载失败，请稍后重试」

#### Scenario: 容器下点打开文件夹提示功能不可用
- **WHEN** 容器部署（宿主功能不可用）下用户点击「打开文件夹」reveal 入口未被隐藏而被触发、或后端返回宿主功能不可用错误
- **THEN** 前端展示「该功能仅在桌面/宿主部署可用」类文案，而非「下载失败，请稍后重试」

#### Scenario: 容器部署下宿主功能不可用且如实上报
- **WHEN** 后端运行在容器中（检测到容器环境且未显式开启宿主功能）调用 `GET /status`
- **THEN** status 返回 `host_features_available` 为 false

#### Scenario: 容器部署下调用 reveal 返回明确错误
- **WHEN** 宿主功能不可用时调用 `POST /artifacts/{aid}/reveal`
- **THEN** 系统返回明确错误（如 501）并附"仅在 macOS/Windows 宿主直跑后端时可用"文案，不调用 subprocess、不抛未捕获 500

#### Scenario: 容器部署下从浏览器导入返回明确错误
- **WHEN** 宿主功能不可用时调用 `POST /login/browser`
- **THEN** 系统返回明确错误（如 501）并附文案，不读取本机浏览器 cookies、不抛未捕获 500

#### Scenario: 宿主直跑后端时功能可用
- **WHEN** 后端直接跑在 macOS/Windows 宿主（非容器，或显式开启宿主功能）
- **THEN** `GET /status` 的 `host_features_available` 为 true，reveal 与 login/browser 按原有逻辑工作

#### Scenario: 缺宿主功能时前端隐藏入口
- **WHEN** `GET /status` 返回 `host_features_available` 为 false
- **THEN** 前端隐藏或禁用「打开文件夹」「从浏览器导入」入口

### Requirement: 内容分析 cookie 的多用户隔离
系统 SHALL 按用户隔离内容分析的 YouTube cookies：每个用户的 cookies 存储为独立产物，路径为 `base_dir()/cookies/<user_id>.txt`，不再共用全局单文件（旧的全局 `youtube_cookies.txt` **弃用、不迁移**，用户各自重新登录）。

所有读写 cookies 的能力 SHALL 以当前登录用户（`user_id`）为作用域，互不影响：cookies 登录（粘贴 / 从浏览器导入）、登出（清除 cookies）、活体探测、`GET /status` 上报的 `cookies_present` 与 `youtube_logged_in`、以及下载时所用的 cookie，均 SHALL 仅作用于该用户自己的 cookies 产物。下载某产物时所用的 cookie SHALL 取自该产物归属用户的 cookies 文件。

一个用户对其 cookies 的任何操作（登录 / 登出 / 探测）SHALL **不影响**其他用户的 cookies 与登录态。

#### Scenario: cookies 按用户独立存储
- **WHEN** 用户保存（粘贴或导入）其 YouTube cookies
- **THEN** 系统将其写入 `base_dir()/cookies/<user_id>.txt`，与其他用户的 cookies 文件互相独立、互不覆盖

#### Scenario: 用户 A 登录不影响用户 B 的登录态
- **WHEN** 用户 A 保存其 cookies 后，用户 B 调用 `GET /status` 或活体探测
- **THEN** 用户 B 的 `cookies_present` / `youtube_logged_in` 仅反映 B 自己的 cookies 产物，不因 A 登录而变为已登录

#### Scenario: 用户 B 登出不影响用户 A
- **WHEN** 用户 B 调用登出清除其 cookies
- **THEN** 系统仅删除 B 的 `cookies/<B_id>.txt`，用户 A 的 cookies 与登录态保持不变

#### Scenario: 下载使用产物归属用户的 cookie
- **WHEN** 系统为某用户的下载产物执行下载
- **THEN** 系统使用该产物归属用户的 cookies 文件（`cookies/<owner_id>.txt`），不使用全局文件或他人的 cookies

#### Scenario: 活体探测按用户作用域
- **WHEN** 用户对其登录态发起活体探测
- **THEN** 系统用该用户自己的 cookies 请求 YouTube 判定三态，结果不受其他用户 cookies 影响

#### Scenario: 旧全局 cookies 不迁移
- **WHEN** 部署升级后系统检视 cookies 存储
- **THEN** 旧的全局 `youtube_cookies.txt` 不被读取或迁移，用户首次使用按未登录处理，需各自重新登录
