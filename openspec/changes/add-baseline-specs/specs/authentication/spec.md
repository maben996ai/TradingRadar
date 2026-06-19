## ADDED Requirements

### Requirement: 用户注册
系统 SHALL 提供 `POST /api/auth/register` 接口，接收 email、password 与可选 display_name，创建新用户并初始化默认数据。email 全局唯一。

#### Scenario: 成功注册新用户
- **WHEN** 客户端以未注册的 email 与 password 调用注册接口
- **THEN** 系统创建 User（密码以哈希存储），未提供 display_name 时取 email 的 `@` 前缀作为显示名
- **AND** 为该用户创建一条 UserSettings 默认记录
- **AND** 为该用户预置三条金十（finance_news）默认信源：市场快讯、财经资讯、财经日历
- **AND** 返回 201 与用户信息（不含密码哈希）

#### Scenario: 邮箱已被注册
- **WHEN** 客户端以已存在的 email 调用注册接口
- **THEN** 系统返回 409 并提示邮箱已注册，不创建任何记录

### Requirement: 用户登录
系统 SHALL 提供 `POST /api/auth/login` 接口，校验 email 与 password，成功后签发访问令牌（JWT）。

#### Scenario: 凭证正确
- **WHEN** 客户端提交正确的 email 与 password
- **THEN** 系统返回 access_token

#### Scenario: 凭证错误或用户不存在
- **WHEN** 客户端提交不存在的 email 或错误的 password
- **THEN** 系统返回 401 并提示邮箱或密码错误（不区分是哪一项错误）

### Requirement: 获取当前用户
系统 SHALL 提供 `GET /api/auth/me` 接口，依据请求携带的访问令牌返回当前登录用户信息。

#### Scenario: 携带有效令牌
- **WHEN** 客户端携带有效 Bearer 令牌调用该接口
- **THEN** 系统返回当前用户信息

#### Scenario: 缺失或无效令牌
- **WHEN** 客户端未携带令牌或携带无效/过期令牌
- **THEN** 系统返回 401

### Requirement: 受保护接口的统一鉴权
除注册与登录外，系统的业务接口 SHALL 要求有效访问令牌，令牌解析出的用户即请求上下文，数据访问限定在该用户范围内。

#### Scenario: 无令牌访问受保护接口
- **WHEN** 客户端未携带有效令牌访问任一受保护接口
- **THEN** 系统返回 401，不返回任何业务数据
