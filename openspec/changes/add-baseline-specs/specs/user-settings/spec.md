## ADDED Requirements

### Requirement: 读取用户飞书设置
系统 SHALL 提供 `GET /api/settings/feishu` 接口，返回当前用户的飞书设置（feishu_webhook_url）；若用户尚无设置记录则自动创建默认记录后返回。

#### Scenario: 已有设置记录
- **WHEN** 已登录用户调用读取设置接口
- **THEN** 系统返回该用户的飞书设置

#### Scenario: 尚无设置记录
- **WHEN** 用户首次调用读取设置接口且无设置记录
- **THEN** 系统自动创建一条默认 UserSettings 后返回

### Requirement: 更新用户飞书设置
系统 SHALL 提供 `PUT /api/settings/feishu` 接口，更新当前用户的 feishu_webhook_url。

#### Scenario: 更新 webhook 地址
- **WHEN** 用户提交新的 feishu_webhook_url
- **THEN** 系统保存该地址并返回更新后的设置

### Requirement: 用户设置维度的飞书测试
系统 SHALL 提供 `POST /api/settings/feishu/test` 接口，使用用户设置中保存的 webhook 地址发送测试卡片。

#### Scenario: 已配置地址
- **WHEN** 用户设置中已保存 webhook 地址并调用测试接口
- **THEN** 系统向该地址发送测试卡片并返回成功状态

#### Scenario: 未配置地址
- **WHEN** 用户设置中未保存 webhook 地址即调用测试接口
- **THEN** 系统返回错误状态并提示未配置 webhook 地址
