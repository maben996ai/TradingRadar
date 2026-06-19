## ADDED Requirements

### Requirement: 查询财经日历事件
系统 SHALL 提供 `GET /api/calendar/events` 接口，按起止时间窗口返回统一日历事件（宏观 + 财报），支持按分类、最低重要性、事件类型（kind）及"仅看关注"过滤。

#### Scenario: 按时间窗查询
- **WHEN** 用户传入 start 与 end 调用事件接口
- **THEN** 系统返回该 UTC 时间窗内的事件

#### Scenario: 多维过滤
- **WHEN** 用户附加 categories、importance（1-3）、kind 或 tracked_only 参数
- **THEN** 系统仅返回匹配全部过滤条件的事件

#### Scenario: 仅看关注的财报
- **WHEN** 用户设置 `tracked_only=true`
- **THEN** 系统仅返回与该用户关注代码相关的事件

### Requirement: 刷新日历事件
系统 SHALL 提供 `POST /api/calendar/refresh` 接口，通过可插拔 provider 刷新事件：宏观走精选发布日程并以外部源回填历史 actual/previous，财报走外部 provider 拉取真实财报日。刷新以 event_key 唯一去重，并重建窗口内事件以清除占位与改期残留。

#### Scenario: 成功刷新
- **WHEN** 用户调用刷新接口
- **THEN** 系统按配置选择 provider 拉取事件、以 event_key 去重并返回新增条数

#### Scenario: 财报范围限定
- **WHEN** 刷新财报事件
- **THEN** 系统仅对"默认重点公司 ∪ 用户关注代码"的集合拉取，避免被全市场财报淹没

### Requirement: 关注代码管理
系统 SHALL 提供 `/api/calendar/tracked-tickers` 接口组，允许用户增、查、删关注的股票代码，代码统一规范为大写且每用户每代码唯一。

#### Scenario: 列出关注代码
- **WHEN** 用户调用 `GET /api/calendar/tracked-tickers`
- **THEN** 系统返回该用户的全部关注代码

#### Scenario: 新增关注代码
- **WHEN** 用户提交一个代码（自动去空格并转大写）
- **THEN** 系统创建关注记录；若该代码已关注则返回已有记录（不报错）

#### Scenario: 空代码
- **WHEN** 用户提交空白代码
- **THEN** 系统返回 400

#### Scenario: 删除关注代码
- **WHEN** 用户删除其名下某关注代码
- **THEN** 系统删除该记录并返回 204；删除不存在或非本人记录返回 404

### Requirement: 日历定时与首启生成
系统 SHALL 通过调度器每日刷新日历事件，并在事件表为空时于服务首启时自动生成一次。

#### Scenario: 每日定时刷新
- **WHEN** 每日调度时点到达
- **THEN** 系统执行日历事件刷新

#### Scenario: 首启空表自动生成
- **WHEN** 服务启动时事件表为空
- **THEN** 系统自动生成一次日历事件
