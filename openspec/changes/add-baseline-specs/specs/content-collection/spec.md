## ADDED Requirements

### Requirement: 多平台内容采集
系统 SHALL 通过可注册的采集器（crawler registry）按信源类型从外部平台抓取最新内容，已支持的采集器包括 twitter、youtube、jin10、rss。每个采集器实现统一的抓取接口，产出标准化内容项。

#### Scenario: 按信源类型选择采集器
- **WHEN** 调度对某信源执行抓取
- **THEN** 系统依据该信源的 source_type 从 registry 选择对应采集器执行

#### Scenario: 不支持的信源类型
- **WHEN** 信源类型无对应采集器
- **THEN** 系统不执行抓取并以失败/跳过方式记录，不抛出未处理异常

### Requirement: 内容项入库与去重
系统 SHALL 将采集到的内容标准化为 ContentItem 入库，并以 (data_source_id, platform_id) 为唯一键去重，重复内容不重复入库。

#### Scenario: 新内容入库
- **WHEN** 采集到该信源下尚不存在的 platform_id 内容
- **THEN** 系统创建 ContentItem（标题、缩略图、内容链接、发布时间、原始数据等）

#### Scenario: 重复内容跳过
- **WHEN** 采集到的内容 platform_id 在该信源下已存在
- **THEN** 系统不重复创建记录

### Requirement: 抓取调度
系统 SHALL 通过调度器周期性地对信源执行抓取，并在用户新增信源时触发一次首次抓取。

#### Scenario: 周期性抓取
- **WHEN** 调度周期到达
- **THEN** 系统对相应信源执行抓取流程

#### Scenario: 首次抓取失败可观测
- **WHEN** 新增信源的首次抓取因外部错误（如限流）失败
- **THEN** 系统写入一条 FAILED 状态的抓取日志记录失败原因，使信源不会一直停留在"初始化中"状态

### Requirement: 抓取日志
系统 SHALL 为每次抓取记录 CrawlLog（状态 success/failed、消息、items_found），并提供 `GET /api/crawl-logs` 供用户查询自己信源的抓取日志，按创建时间倒序，支持按状态过滤与数量上限。

#### Scenario: 查询抓取日志
- **WHEN** 已登录用户调用抓取日志接口
- **THEN** 系统返回其名下信源的抓取日志，按时间从新到旧排序

#### Scenario: 按状态过滤
- **WHEN** 用户传入 `status=failed`
- **THEN** 系统仅返回失败的抓取日志

### Requirement: 内容流展示
系统 SHALL 提供 `GET /api/content-items` 接口，以游标分页返回当前用户名下信源的内容项，按发布时间倒序（同发布时间按 id 倒序），支持按 source_type 过滤。

#### Scenario: 游标分页获取内容流
- **WHEN** 用户调用内容流接口并指定 limit
- **THEN** 系统返回不超过 limit 条内容项，并在还有更多时返回 next_cursor 与 has_more=true

#### Scenario: 非法游标
- **WHEN** 用户传入无法解码的 cursor
- **THEN** 系统返回 400

#### Scenario: 内容项展示字段衍生
- **WHEN** 返回内容项
- **THEN** 系统从 raw_data 衍生展示字段（完整正文 content_text、引用推文 quoted、配图、时长 duration_seconds），并附带所属信源的名称、头像、外部 id 与 source_type
