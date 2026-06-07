# CLAUDE.md

本文件用于给 Claude Code、Codex 等代码代理提供 TradingRader 的仓库级工作说明。

## 项目概览

TradingRader 是一个面向港美股投资者的内容聚合平台，目标是将 Bilibili、YouTube 等财经创作者的更新集中到统一入口，并逐步补齐订阅管理、视频流、抓取日志和通知能力。后续还会逐步接入金融时讯、财报分析、交易信息等内容，并结合大模型能力提供金融投研分析能力。

当前仓库已经完成一期的主要技术骨架：
- 后端基于 FastAPI，已具备鉴权、核心 API、采集器、解析器、调度器和测试基础
- 前端基于 Vue 3，已完成登录、注册、Token 持久化、路由守卫和基础页面框架
- 项目支持中英文界面切换，并保留后续联调与业务扩展空间

## 相关文档

- `README.md`

## 技术栈

- 后端：Python 3.12、FastAPI、SQLAlchemy Async、Alembic、PostgreSQL、Redis、APScheduler
- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router、Element Plus、Axios
- 基础设施：Docker Compose、Nginx

## 仓库结构

- `backend/`：后端服务
- `frontend/`：前端应用
- `nginx/`：生产网关配置

## 开发规则

- 开发前确认分支与模块对应，不对应则从 `main` 新建分支。
- 先读相关代码和测试，再动手。
- 遵循 TDD：先写失败测试，再最小实现，测试通过后进入下一轮。
- 每个功能按"上下文确认 → 迭代开发 → 集成测试 → 真实验证 → 收尾提交"推进。
- 不修改无关文件，不做大范围重构。
- 默认使用中文输出。

## 分层约定

- 后端 `api/` 仅放路由和请求入口，业务逻辑优先放在 `services/`。
- 后端 `models/` 放数据模型，`schemas/` 放请求和响应模型，`core/` 放配置、数据库、鉴权等基础能力。
- 前端 `src/api/` 放 API 调用，`src/router/` 放路由，`src/views/` 放页面，`src/components/` 放复用组件，`src/stores/` 放全局状态。
- 采集链路遵循“采集 -> 解析 -> 入库/调度 -> 展示/通知”的既有分层，不混杂职责。

## 当前主线

当前优先打通以下闭环：
1. 创作者接入
2. 内容抓取与解析
3. 视频入库与信息流展示
4. 飞书通知与联调验证

优先打通真实 API 与真实数据流，不优先扩展占位页面。

## 常用命令

```bash
docker compose up
docker compose up --build
docker compose logs -f backend
docker compose logs -f frontend
```

```bash
cd frontend
npm install
npm run dev
npm run build
npm run type-check
```

```bash
cd backend
pip install -r requirements.txt
pip install -r requirements-dev.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pytest
ruff check .
ruff format .
```

## 环境变量

基于 `.env.example` 维护仓库根目录 `.env`。

关键变量：
- `DATABASE_URL`
- `REDIS_URL`
- `SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `YOUTUBE_API_KEY`
- `BILIBILI_SESSDATA`
- `NGINX_CONF_FILE`

注意：
- 当前代码实际使用的是 `SECRET_KEY`，不是 `JWT_SECRET_KEY`
- 从 `backend/` 目录单独启动后端时，也会自动读取仓库根目录 `.env`
- 前端开发时，`/api` 会通过 Vite 代理转发到后端
