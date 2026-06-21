## ADDED Requirements

### Requirement: 设备令牌签发与管理

系统 SHALL 允许已登录用户在设置页签发用于浏览器扩展同步的**设备令牌**：令牌长期有效、可吊销，作用域 SHALL 仅限"写令牌归属用户自己的 YouTube cookie"，不得读取或写入他人 cookie、不得用于其他 API。系统 SHALL 仅存储令牌的不可逆哈希，明文令牌 SHALL 仅在签发响应中返回一次、不再可取回。系统 SHALL 允许用户列出其令牌（含名称、创建时间、最近使用时间、是否已吊销）并随时吊销任一令牌。

#### Scenario: 签发设备令牌
- **WHEN** 已登录用户在设置页请求签发一个设备令牌（可附名称）
- **THEN** 系统生成令牌、仅存其哈希，并在响应中一次性返回明文令牌供用户复制到扩展

#### Scenario: 列出设备令牌
- **WHEN** 已登录用户请求查看其设备令牌
- **THEN** 系统返回该用户全部令牌的元信息（名称、创建时间、最近使用时间、吊销状态），不返回令牌明文

#### Scenario: 吊销设备令牌后同步被拒
- **WHEN** 用户吊销某设备令牌后，扩展再用该令牌调用同步端点
- **THEN** 系统拒绝同步并返回鉴权失败（如 401/403），不写入任何 cookie

#### Scenario: 设备令牌仅作用于本人 cookie
- **WHEN** 任一有效设备令牌调用同步端点
- **THEN** 系统仅将 cookie 写入该令牌归属用户的 cookie 产物，无法影响其他用户的 cookie

### Requirement: YouTube cookie 同步端点

系统 SHALL 提供 cookie 同步端点 `POST /api/content-analysis/cookies/sync`，接收浏览器扩展推送的 `youtube.com` 域 cookie（JSON 结构）并以**设备令牌**鉴权。系统 SHALL 将收到的 cookie 序列化为 Netscape 格式，经与「粘贴 cookies」一致的校验后，原子写入该令牌归属用户的 per-user cookie 文件（`base_dir()/cookies/<user_id>.txt`，由 harden 变更引入）。同步成功后，该用户 `GET /status` 的 `cookies_present` 与 `youtube_logged_in` SHALL 反映最新 cookie 状态。收到空 cookie（扩展上报 YouTube 已登出）时系统 SHALL 清除该用户的 cookie 文件。本端点 SHALL 仅经设备令牌鉴权，不接受用户会话 JWT。

#### Scenario: 扩展同步 cookie 成功
- **WHEN** 扩展用有效设备令牌 POST 一组 `youtube.com` 登录 cookie 到同步端点
- **THEN** 系统校验通过、序列化为 Netscape 格式并写入该用户的 `cookies/<user_id>.txt`，返回成功

#### Scenario: 同步成功后状态更新
- **WHEN** 用户的 cookie 经扩展同步成功后，该用户调用 `GET /status`
- **THEN** `cookies_present` 为 true，`youtube_logged_in` 反映同步 cookie 的有效登录态

#### Scenario: 无效或吊销令牌被拒
- **WHEN** 调用同步端点的设备令牌无效、已吊销或缺失
- **THEN** 系统返回鉴权失败（401/403），不写入任何 cookie

#### Scenario: 只能写自己的 cookie
- **WHEN** 用户 A 的设备令牌调用同步端点
- **THEN** 系统仅写入 `cookies/<A_id>.txt`，绝不写入或覆盖其他用户的 cookie 文件

#### Scenario: 扩展上报登出推空清除
- **WHEN** 扩展检测到 YouTube 已登出（cookie 消失）并用有效设备令牌推送空 cookie
- **THEN** 系统清除该用户的 cookie 文件，其后 `GET /status` 的 `cookies_present` 为 false

#### Scenario: 拒绝非法 cookie 内容
- **WHEN** 同步端点收到无法构成有效 YouTube 登录 cookie 的内容
- **THEN** 系统拒绝写入并返回校验失败信息，不破坏该用户已有的 cookie 文件

### Requirement: 浏览器扩展行为

系统配套的浏览器扩展 SHALL 为 Chrome MV3 扩展，host 权限 SHALL 仅限 `*://*.youtube.com/*`，只读取 `youtube.com` 域 cookie（不读取 `.google.com` 等其他域）。扩展 SHALL 通过用户粘贴的设备令牌（配对码）完成与 TradingRadar 后端的绑定。扩展 SHALL 用 `chrome.alarms` 定时（如每 6 小时）以及 `chrome.cookies.onChanged`（youtube 域 cookie 变化即触发）持续向同步端点推送最新 cookie，保持后端 cookie 新鲜。当 YouTube 登出（cookie 消失）时扩展 SHALL 推送空 cookie 并通知用户。开发期分发方式 SHALL 为开发者模式 load-unpacked，先只支持 Chrome。

#### Scenario: 配对绑定
- **WHEN** 用户在扩展 popup 粘贴设置页签发的设备令牌并保存
- **THEN** 扩展存储该令牌并以其鉴权后续同步请求，完成与该用户账号的绑定

#### Scenario: 仅读取 youtube.com cookie
- **WHEN** 扩展读取 cookie 以同步
- **THEN** 扩展仅读取 `youtube.com` 域 cookie，不读取 `.google.com` 或其他域的 cookie

#### Scenario: 定时刷新保持新鲜
- **WHEN** `chrome.alarms` 定时触发或 `chrome.cookies.onChanged` 监测到 youtube 域 cookie 变化
- **THEN** 扩展将当前 `youtube.com` cookie 推送到同步端点，使后端 cookie 保持新鲜

#### Scenario: YouTube 登出时推空
- **WHEN** 扩展监测到 YouTube 已登出（鉴权 cookie 消失）
- **THEN** 扩展向同步端点推送空 cookie，并提示用户已登出

### Requirement: cookie 同步的安全要求

系统 SHALL 对扩展持续同步活跃 YouTube 会话 cookie 这一较长暴露面采取最小化与可控措施：同步传输 SHALL 经 HTTPS；扩展抓取范围 SHALL 限于 `youtube.com`，不抓取整个 Google 会话；设备令牌 SHALL 可吊销且仅能写本人 cookie；落盘的 cookie SHALL 在设置页与扩展 popup 向用户明确告知"扩展会读取并上传你的 YouTube 登录 cookie 到 TradingRadar 服务器"。cookie 落盘加密 / 短保留 SHALL 作为安全要求或待评估项跟进（见 design Open Questions）。

#### Scenario: 经 HTTPS 传输
- **WHEN** 扩展向后端推送 cookie
- **THEN** 同步请求经 HTTPS 加密传输，不以明文经不安全通道发送

#### Scenario: 明确知情同意
- **WHEN** 用户在设置页签发设备令牌或在扩展 popup 完成配对
- **THEN** 界面明确告知用户扩展将读取并上传其 YouTube 登录 cookie 到 TradingRadar 服务器

#### Scenario: 抓取范围最小化
- **WHEN** 扩展配置其 host 权限与 cookie 读取范围
- **THEN** 范围仅限 `youtube.com`，不包含 `.google.com` 等会暴露完整 Google 会话（如 Gmail）的域
