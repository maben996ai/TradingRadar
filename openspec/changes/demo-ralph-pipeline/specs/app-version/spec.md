## ADDED Requirements

### Requirement: 应用版本信息端点
系统 SHALL 提供 `GET /api/version` 端点，返回应用名称与版本号，无需鉴权。

#### Scenario: 查询版本
- **WHEN** 客户端请求 `GET /api/version`
- **THEN** 系统返回 200 与 JSON，包含 `name`（应用名）与 `version`（版本号）字段
