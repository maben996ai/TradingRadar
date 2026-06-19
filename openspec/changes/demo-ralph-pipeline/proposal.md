## Why

用于演示 Ralph + OpenSpec 流水线的端到端链路（规格 → prd.json → 循环实现 → 验收）。选一个**极小且无害**的真实功能作为载体：暴露应用版本信息端点。本变更仅为流水线演示，不承载实际业务价值。

## What Changes

- 新增 `GET /api/version` 端点，返回应用名称与版本号（取自 `app.main` 的 FastAPI title/version）。
- 仅后端，零外部依赖、零迁移、零前端改动。

## Capabilities

### New Capabilities
- `app-version`: 提供应用版本信息查询端点（演示用）。

### Modified Capabilities
<!-- 无 -->

## Impact

- 新增：`app/api/version.py` 或在现有 `main.py` 健康检查旁增一个路由；新增对应 pytest。
- 不影响任何现有能力。
