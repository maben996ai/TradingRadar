## ADDED Requirements

### Requirement: 列出信源
系统 SHALL 提供 `GET /api/data-sources` 接口，返回当前用户的全部信源，按创建时间倒序，并支持按 starred 与 content_type 过滤。

#### Scenario: 默认列出全部信源
- **WHEN** 已登录用户调用该接口且不带过滤参数
- **THEN** 系统返回该用户名下所有信源，按创建时间从新到旧排序

#### Scenario: 按收藏与内容类型过滤
- **WHEN** 用户传入 `starred=true` 或 `content_type=video` 等过滤参数
- **THEN** 系统仅返回匹配该过滤条件的信源

### Requirement: 添加信源
系统 SHALL 提供 `POST /api/data-sources` 接口，接收信源 URL，经 resolver 解析出 source_type 与平台信息后入库，并触发该信源的首次抓取。

#### Scenario: 成功添加可解析的信源
- **WHEN** 用户提交一个 resolver 可识别的 URL
- **THEN** 系统解析出 source_type、platform_id、名称、主页与头像，创建信源并返回 201
- **AND** 在后台异步触发该信源的首次抓取

#### Scenario: URL 无法解析
- **WHEN** 用户提交 resolver 无法识别的 URL
- **THEN** 系统返回 400 并附带解析错误信息，不创建信源

#### Scenario: 信源重复
- **WHEN** 用户提交的信源（同 user + source_type + platform_id）已存在
- **THEN** 系统返回 409 并提示信源已存在

### Requirement: 更新信源
系统 SHALL 提供 `PATCH /api/data-sources/{id}` 接口，允许信源所有者更新备注、分类、收藏状态、内容类型与采集配置。

#### Scenario: 所有者更新信源
- **WHEN** 信源所有者提交可更新字段
- **THEN** 系统更新对应字段并返回更新后的信源

#### Scenario: 信源不存在或非本人所有
- **WHEN** 用户更新一个不存在或不属于自己的信源
- **THEN** 系统返回 404

### Requirement: 删除信源
系统 SHALL 提供 `DELETE /api/data-sources/{id}` 接口，删除信源及其级联的内容项与抓取日志。

#### Scenario: 所有者删除信源
- **WHEN** 信源所有者删除其信源
- **THEN** 系统删除该信源并级联删除关联的内容项与抓取日志，返回 204

#### Scenario: 删除不存在或非本人信源
- **WHEN** 用户删除不存在或不属于自己的信源
- **THEN** 系统返回 404

### Requirement: 信源解析
系统 SHALL 提供 resolver 将用户输入的 URL 解析为统一的 source_type 与平台标识（platform_id、name、profile_url、avatar_url），支持已实现的平台类型（如 twitter、youtube、rss 等）。

#### Scenario: 解析支持的平台 URL
- **WHEN** resolver 收到受支持平台的 URL
- **THEN** 返回对应 source_type 及解析出的平台元信息

#### Scenario: 解析不支持的 URL
- **WHEN** resolver 收到无法识别的 URL
- **THEN** 抛出可被接口转换为 400 的错误
