# TradingRader

TradingRader 是一个面向港美股投资者的内容聚合平台，目标是将 Bilibili、YouTube 等财经创作者的更新集中到统一入口，并逐步补齐订阅管理、视频流、抓取日志和通知能力。后续还会逐步接入金融时讯、财报分析、交易信息等内容，并结合大模型能力提供金融投研分析能力。

当前仓库已经完成一期的主要技术骨架：
- 后端基于 FastAPI，已具备鉴权、核心 API、采集器、解析器、调度器和测试基础
- 前端基于 Vue 3，已完成登录、注册、Token 持久化、路由守卫和基础页面框架
- 项目支持中英文界面切换，并保留后续联调与业务扩展空间

## 技术栈

- 后端：Python 3.12、FastAPI、SQLAlchemy Async、Alembic、PostgreSQL、Redis、APScheduler
- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router、Element Plus、Axios
- 基础设施：Docker Compose、Nginx

## 当前范围

当前版本重点覆盖以下方向：
- 用户注册、登录与访问控制
- Bilibili / YouTube 创作者与视频抓取能力的后端基础设施
- 飞书通知、信息流展示、创作者管理等后续能力的页面和接口预留
- 面向金融时讯、财报解读、交易数据与大模型辅助投研的后续扩展空间

项目仍处于持续迭代阶段，前端业务闭环和完整联调流程尚在推进中。

## 仓库结构

- `backend/`：FastAPI 后端服务
- `frontend/`：Vue 3 前端应用
- `nginx/`：生产网关配置
- `.context/`：产品与技术文档
- `.claude/`：面向代码代理的协作说明
