## ADDED Requirements

### Requirement: 列出基本面数据源
系统 SHALL 提供 `GET /api/fundamentals/sources` 接口，返回已注册的基本面数据源名称（如 finnhub、fmp、quartr、sec_edgar）。

#### Scenario: 列出可用数据源
- **WHEN** 已登录用户调用该接口
- **THEN** 系统返回基本面 registry 中已注册的所有数据源名称

### Requirement: 下载个股基本面资料
系统 SHALL 提供 `POST /api/fundamentals/download` 接口，针对给定股票代码从一个或多个数据源聚合下载基本面资料，按源返回结果（含是否跳过、消息、产出文件列表）。

#### Scenario: 成功下载
- **WHEN** 用户提交有效 ticker 与（可选）数据源列表
- **THEN** 系统对每个数据源执行下载并返回各源的产出结果（代码统一去空格转大写）

#### Scenario: 空代码
- **WHEN** 用户提交空白 ticker
- **THEN** 系统返回 400

#### Scenario: 未知数据源
- **WHEN** 用户指定的数据源不在已注册集合中
- **THEN** 系统返回 400 并列出未知数据源

### Requirement: 下载产物文件读取
系统 SHALL 提供 `GET /api/fundamentals/files` 接口，按路径返回基本面下载目录内的文件，且禁止访问该目录之外的路径。

#### Scenario: 读取目录内文件
- **WHEN** 用户请求位于基本面目录内的有效文件路径
- **THEN** 系统以文件形式返回该文件

#### Scenario: 越权路径
- **WHEN** 请求路径解析后位于基本面目录之外
- **THEN** 系统返回 403

#### Scenario: 文件不存在
- **WHEN** 请求的目录内路径不指向已存在文件
- **THEN** 系统返回 404
