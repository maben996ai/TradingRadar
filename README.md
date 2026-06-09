# TradingRader

TradingRader 是一个面向港美股投资者的金融内容聚合工具，用于把金十数据金融时讯、X/Twitter、YouTube 等信源的更新集中到统一的信息流里，并围绕订阅管理、内容抓取、通知和后续投研分析能力持续迭代。

当前仓库包含一个 FastAPI 后端、一个 Vue 3 前端，以及用于本地和生产部署的 Docker Compose / Nginx 配置。

## 功能概览

- 用户注册、登录、JWT 鉴权和路由守卫
- 信源管理：添加、更新、收藏、删除和分类管理
- 当前可抓取的真实信源：金十数据金融时讯、X/Twitter、YouTube
- 内容流：按平台和单个信源查看内容，支持游标分页
- 金十数据金融时讯：市场快讯每 5 分钟同步，财经资讯每小时同步，财经日历每日同步
- X/Twitter 文本流展示：正文、头像、时间、原文链接和图片预览
- YouTube 视频内容展示：封面、标题、时长和来源信息
- 抓取调度、抓取日志和首次抓取失败记录
- 飞书 Webhook 配置、测试通知和多 Webhook 管理
- 中英文界面切换
- 内容类型与信源类型模型已预留文章、新闻、市场数据、RSS、PDF 等扩展方向

## 技术栈

- 后端：Python 3.12、FastAPI、SQLAlchemy Async、Alembic、PostgreSQL、Redis、APScheduler
- 前端：Vue 3、TypeScript、Vite、Pinia、Vue Router、Element Plus、Axios
- 基础设施：Docker Compose、Nginx
- 测试与质量：pytest、pytest-asyncio、respx、ruff、vue-tsc

## 目录结构

```text
.
├── backend/              # FastAPI API、模型、采集器、调度器和测试
├── frontend/             # Vue 3 前端应用
├── nginx/                # Nginx 网关配置
├── docker-compose.yml    # 本地开发环境
├── docker-compose.prod.yml
├── Makefile              # 常用 Compose 命令
└── README.md
```

## 快速启动

先准备环境变量：

```bash
cp .env.example .env
```

本地 Docker 开发环境：

```bash
make dev-build
```

启动后访问：

- 前端：http://localhost:3000
- 后端健康检查：http://localhost:8000/api/health
- 后端 OpenAPI：http://localhost:8000/docs

后续常用命令：

```bash
make dev       # docker compose up
make logs      # 查看所有服务日志
make ps        # 查看服务状态
make down      # 停止服务
make down-v    # 停止并删除数据卷
```

## 环境变量

`.env.example` 默认适配 Docker Compose 容器网络。关键变量如下：

- `DATABASE_URL`：数据库连接。Compose 默认使用 `postgres:5432`
- `REDIS_URL`：Redis 连接。Compose 默认使用 `redis:6379`
- `SECRET_KEY`：JWT 签名密钥，生产环境必须替换
- `ACCESS_TOKEN_EXPIRE_MINUTES`：访问令牌有效期
- `DEV_ACCOUNT_EMAIL` / `DEV_ACCOUNT_DISPLAY_NAME` / `DEV_ACCOUNT_PASSWORD`：本地开发默认账号
- `YOUTUBE_API_KEY`：YouTube Data API v3 Key
- `TWITTERAPI_IO_API_KEY`：TwitterAPI.io Key，用于 X/Twitter 信源解析和抓取
- `JIN10_MCP_SERVER_URL` / `JIN10_MCP_BEARER_TOKEN` / `JIN10_MCP_PROTOCOL_VERSION`：金十数据 MCP 服务配置，用于金融时讯快讯同步
- `FEISHU_APP_ID` / `FEISHU_APP_SECRET`：飞书图片上传能力，可选
- `NGINX_CONF_FILE`：生产网关使用的 Nginx 配置文件

如果不使用 Docker、直接在本机启动后端，请把 `DATABASE_URL` 和 `REDIS_URL` 的主机改成 `localhost`，或移除 `DATABASE_URL` 并使用后端默认的本地 SQLite 配置。SQLite 需要安装开发依赖中的 `aiosqlite`。

## 本地开发

后端：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

前端开发服务默认监听 `3000`，并通过 Vite 代理把 `/api` 请求转发到后端。

## 测试与检查

后端：

```bash
cd backend
pytest
ruff check .
ruff format . --check
```

前端：

```bash
cd frontend
npm run type-check
npm run build
```

## API 模块

后端 API 均挂载在 `/api` 下：

- `/api/auth`：注册、登录、当前用户
- `/api/data-sources`：信源管理
- `/api/content-items`：内容列表与分页
- `/api/crawl-logs`：抓取日志
- `/api/settings/feishu`：兼容的飞书设置入口
- `/api/webhooks/feishu`：飞书 Webhook 管理与测试
- `/api/health`：健康检查

## 部署说明

生产部署入口为 `docker-compose.prod.yml`，并通过 `nginx/` 下的配置提供网关能力。默认 `NGINX_CONF_FILE=nginx.http.conf`，准备好证书后可切换到 HTTPS 配置。

生产环境至少需要替换：

- `SECRET_KEY`
- `POSTGRES_PASSWORD`
- `YOUTUBE_API_KEY`
- `TWITTERAPI_IO_API_KEY`
- 飞书相关密钥和 Webhook 配置

## 当前限制

- 当前真实采集器注册了金十数据金融时讯、X/Twitter 和 YouTube
- 市场宏观、财经日历和内容分析页面仍有占位能力，后续需要接入更多真实数据源或分析服务
- 前端和后端仍处于快速迭代阶段，发布前建议同时运行后端测试和前端类型检查
