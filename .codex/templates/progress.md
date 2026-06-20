# Codex Progress

## Codebase Patterns

- 后端路由保持薄入口，核心逻辑放 `backend/app/services/`。
- 前端 API 调用统一放 `frontend/src/api/`，页面只消费 API 方法和类型。
- 有逻辑变更时由 RD 补测试，QA 只验证不补业务测试。

## Log

暂无运行记录。
