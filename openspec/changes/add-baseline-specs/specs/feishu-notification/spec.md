## ADDED Requirements

### Requirement: 飞书 Webhook 管理
系统 SHALL 提供 `/api/webhooks/feishu` 接口组，允许用户管理多条飞书 webhook 配置（增、查、改、删），每条含名称、webhook 地址与启用开关，且仅限本人访问。

#### Scenario: 列出本人 webhook
- **WHEN** 已登录用户调用 `GET /api/webhooks/feishu`
- **THEN** 系统返回该用户的全部飞书 webhook 配置

#### Scenario: 创建 webhook
- **WHEN** 用户提交名称与 webhook 地址调用 `POST /api/webhooks/feishu`
- **THEN** 系统创建该配置并返回 201

#### Scenario: 更新 webhook
- **WHEN** 用户调用 `PUT /api/webhooks/feishu/{id}` 更新名称或启用状态
- **THEN** 系统更新对应字段并返回更新后的配置

#### Scenario: 删除 webhook
- **WHEN** 用户调用 `DELETE /api/webhooks/feishu/{id}`
- **THEN** 系统删除该配置并返回 204

#### Scenario: 操作他人或不存在的 webhook
- **WHEN** 用户更新/删除/测试一个不存在或不属于自己的 webhook
- **THEN** 系统返回 404

### Requirement: 飞书推送测试
系统 SHALL 提供 `POST /api/webhooks/feishu/{id}/test` 接口，向指定 webhook 发送一条样例卡片消息以验证连通性。

#### Scenario: 发送测试卡片
- **WHEN** 用户对其有效的 webhook 调用测试接口
- **THEN** 系统向该 webhook 地址发送一条测试卡片消息并返回成功状态

### Requirement: 飞书卡片通知能力
系统 SHALL 提供飞书 notifier，将内容更新组织为卡片消息（含标题、创作者、平台、内容链接、缩略图等）推送至飞书 webhook。

#### Scenario: 发送内容卡片
- **WHEN** notifier 收到一条内容通知请求
- **THEN** 系统构造卡片消息并发送至目标 webhook 地址
