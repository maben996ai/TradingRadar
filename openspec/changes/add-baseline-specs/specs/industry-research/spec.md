## ADDED Requirements

### Requirement: 列出研报信源
系统 SHALL 提供 `GET /api/research/sources` 接口，返回可用的研报信源列表（key 与展示信息）。

#### Scenario: 列出信源
- **WHEN** 已登录用户调用该接口
- **THEN** 系统返回全部研报信源定义

### Requirement: 解析股票代码为公司名
系统 SHALL 提供 `GET /api/research/resolve` 接口，将股票代码解析为公司名称，并返回检索回溯天数（lookback_days）。

#### Scenario: 代码可解析
- **WHEN** 用户提交有效股票代码
- **THEN** 系统返回规范化代码（大写）、公司名称与回溯天数

#### Scenario: 代码无法解析
- **WHEN** 提交的股票代码无法解析为公司
- **THEN** 系统返回 404

### Requirement: 按信源检索研报
系统 SHALL 提供 `GET /api/research/search` 接口，针对给定股票代码与单个信源 key 检索研报条目，按源返回结果以支持前端逐源展示进度。

#### Scenario: 在指定信源检索
- **WHEN** 用户提交有效 ticker 与已知 source_key
- **THEN** 系统返回该信源下检索到的研报条目，并在出错时返回 error 字段

#### Scenario: 未知信源
- **WHEN** 提交的 source_key 不在已知信源集合中
- **THEN** 系统返回 404

#### Scenario: 代码无法解析
- **WHEN** 检索时所提供的股票代码无法解析为公司
- **THEN** 系统返回 404
