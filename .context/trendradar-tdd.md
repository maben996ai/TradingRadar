# TradingRader 技术方案文档

> **版本：** v1.0
> **日期：** 2026-04-12
> **作者：** TradingRader 团队
> **对应 PRD：** context/prd.md v1.0

---

## 一、技术选型

### 1.1 后端

| 技术 | 版本 | 用途 | 选型理由 |
|------|------|------|----------|
| Python | 3.12 | 主语言 | 生态丰富，团队熟悉 |
| FastAPI | 0.115 | Web 框架 & API | 原生异步，自动生成 OpenAPI 文档，性能优秀 |
| SQLAlchemy | 2.0（async） | ORM | Python 最成熟的 ORM，支持异步驱动 |
| Alembic | 1.13 | 数据库迁移 | 版本化管理 schema 变更 |
| PostgreSQL | 16 | 主数据库 | 原生 JSONB 支持（存储原始数据供三期 AI 处理），UUID 主键，全文检索能力成熟 |
| Redis | 7 | 缓存 | 通知去重，后续可用于限流 |
| APScheduler | 3.x | 定时任务 | 轻量级，内嵌 FastAPI 进程，一期够用（二期可升级为 Celery） |
| httpx | 0.27 | HTTP 客户端 | 原生异步，用于调用 B 站 / YouTube API |
| python-jose | 3.3 | JWT | 标准实现，一期 Token 有效期 30 天 |
| passlib + bcrypt | — | 密码哈希 | 安全存储密码，防数据库裸泄露 |
| Pydantic | v2 | 数据校验 | FastAPI 原生集成 |

### 1.2 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue 3 | 3.4 | 主框架，渐进式，上手成本低 |
| Vite | 5.x | 构建工具，开发体验好 |
| TypeScript | 5.x | 类型安全 |
| Tailwind CSS | 3.x | 原子化样式，快速布局 |
| Element Plus | 2.x | UI 组件库（表单、弹窗、表格等） |
| Pinia | 2.x | 状态管理 |
| Vue Router | 4.x | 前端路由 |
| Axios | 1.x | HTTP 请求封装 |

### 1.3 基础设施

| 工具 | 用途 |
|------|------|
| Docker + Docker Compose | 本地开发与生产部署保持一致 |
| Nginx | 反向代理，生产环境提供前端静态文件 + API 转发 |
| 阿里云香港 ECS | 生产部署（可直连 YouTube，无需代理） |
| Let's Encrypt + Certbot | HTTPS 证书自动申请与续期 |

---

## 二、架构图与模块划分

### 2.1 系统架构图

```mermaid
graph TB
    subgraph 用户端
        Browser[用户浏览器]
        Feishu[飞书 App / PC]
    end

    subgraph 阿里云香港 ECS
        Nginx[Nginx\n反向代理 80/443]

        subgraph 应用层
            FE[前端\nVue 3 静态文件]
            BE[后端\nFastAPI :8000]
            Scheduler[APScheduler\n定时任务 每30分钟]
        end

        subgraph 数据层
            PG[(PostgreSQL :5432\n主数据库)]
            RD[(Redis :6379\n去重缓存)]
        end
    end

    subgraph 外部服务
        BiliAPI[B站公开 API\napi.bilibili.com]
        YTAPI[YouTube Data API v3\ngoogleapis.com]
        FeishuHook[飞书 Webhook\nopen.feishu.cn]
    end

    Browser -->|HTTPS 请求| Nginx
    Nginx -->|静态文件| FE
    Nginx -->|/api/*| BE
    BE <-->|读写| PG
    BE <-->|去重查询| RD
    BE --- Scheduler
    Scheduler -->|拉取最新视频| BiliAPI
    Scheduler -->|拉取最新视频| YTAPI
    Scheduler -->|新视频推送| FeishuHook
    FeishuHook -->|卡片消息| Feishu
```

### 2.2 模块划分

```mermaid
graph LR
    subgraph Backend
        API[API 路由层\n参数校验 & 响应封装]
        SVC[Service 业务层\n核心逻辑]
        DAL[数据访问层\nSQLAlchemy ORM]

        subgraph SVC
            Resolver[URL 解析器]
            Crawlers[采集器\nBilibili / YouTube]
            Notifiers[通知器\nFeishu]
            Sched[调度器\nAPScheduler]
        end
    end

    subgraph Frontend
        Router[Vue Router]
        Views[页面 Views]
        Components[公共组件]
        Stores[Pinia 状态]
        APILayer[API 封装层]
    end

    API --> SVC --> DAL
    Views --> Stores --> APILayer
```

---

## 三、项目文件结构设计

```
trendradar/
├── context/                         # 项目文档
│   ├── prd.md
│   └── tech-spec.md                 # 本文档
│
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 入口：注册路由、挂载 Scheduler、lifespan
│   │   │
│   │   ├── api/                     # 路由层（薄层：参数校验 + 响应封装）
│   │   │   ├── __init__.py
│   │   │   ├── deps.py              # 公共依赖：get_current_user、get_db
│   │   │   ├── auth.py              # POST /auth/register  POST /auth/login
│   │   │   ├── creators.py          # CRUD /creators
│   │   │   ├── videos.py            # GET /videos  PATCH /videos/{id}/status
│   │   │   ├── settings.py          # GET/PUT /settings/feishu
│   │   │   └── crawl_logs.py        # GET /crawl-logs  POST /creators/{id}/crawl
│   │   │
│   │   ├── services/                # 业务逻辑层
│   │   │   ├── crawlers/            # 采集器（适配器模式，核心扩展点）
│   │   │   │   ├── base.py          # BaseCrawler 抽象基类 + 数据类定义
│   │   │   │   ├── registry.py      # CrawlerRegistry：platform → crawler 映射
│   │   │   │   ├── bilibili.py      # B 站实现
│   │   │   │   └── youtube.py       # YouTube 实现
│   │   │   │
│   │   │   ├── notifiers/           # 通知器（适配器模式，核心扩展点）
│   │   │   │   ├── base.py          # BaseNotifier 抽象基类
│   │   │   │   └── feishu.py        # 飞书实现
│   │   │   │
│   │   │   ├── resolver.py          # URL 解析：识别平台 + 路由到对应 Crawler
│   │   │   └── scheduler.py         # APScheduler 任务定义：crawl_all_creators()
│   │   │
│   │   ├── models/
│   │   │   └── models.py            # SQLAlchemy ORM 模型（所有表定义）
│   │   │
│   │   ├── schemas/
│   │   │   └── schemas.py           # Pydantic 请求/响应模型
│   │   │
│   │   └── core/
│   │       ├── config.py            # Settings：环境变量读取（pydantic-settings）
│   │       ├── database.py          # 异步 engine + session 工厂
│   │       └── security.py          # JWT 签发/验证 + bcrypt 密码工具
│   │
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/                # 迁移脚本目录
│   │
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── main.ts                  # Vue 入口
│   │   ├── App.vue
│   │   │
│   │   ├── router/
│   │   │   └── index.ts             # 路由定义 + 导航守卫
│   │   │
│   │   ├── api/
│   │   │   ├── client.ts            # Axios 实例（baseURL、Token 拦截器）
│   │   │   ├── auth.ts
│   │   │   ├── creators.ts
│   │   │   ├── videos.ts
│   │   │   ├── settings.ts
│   │   │   └── crawlLogs.ts
│   │   │
│   │   ├── stores/
│   │   │   ├── auth.ts              # 用户状态 + Token 持久化
│   │   │   └── feed.ts              # 视频列表 + 筛选状态
│   │   │
│   │   ├── views/
│   │   │   ├── LoginView.vue
│   │   │   ├── RegisterView.vue
│   │   │   ├── FeedView.vue         # 主信息流
│   │   │   ├── CreatorsView.vue     # 博主管理
│   │   │   ├── SettingsView.vue     # 设置（飞书 Webhook）
│   │   │   └── CrawlLogsView.vue    # 抓取日志
│   │   │
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   └── NavBar.vue       # 顶部导航栏
│   │   │   ├── feed/
│   │   │   │   ├── VideoCard.vue    # 视频卡片
│   │   │   │   └── FeedFilter.vue   # 平台筛选条
│   │   │   └── creators/
│   │   │       └── CreatorItem.vue  # 博主列表项
│   │   │
│   │   └── types/
│   │       └── index.ts             # 全局 TypeScript 类型定义
│   │
│   ├── index.html
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── Dockerfile
│
├── nginx/
│   ├── nginx.conf                   # 生产配置
│   └── nginx.dev.conf               # 本地开发配置（可选）
│
├── docker-compose.yml               # 本地开发
├── docker-compose.prod.yml          # 生产部署
└── .env.example                     # 环境变量模板
```

---

## 四、数据流程图

### 4.1 视频采集与通知流程

```mermaid
sequenceDiagram
    participant S as APScheduler
    participant DB as PostgreSQL
    participant Bili as B站 API
    participant YT as YouTube API
    participant Feishu as 飞书 Webhook

    loop 每 30 分钟
        S->>DB: 查询所有 Creator
        DB-->>S: Creator 列表

        par 并行抓取（按博主隔离错误）
            S->>Bili: GET /space/arc/search?mid={uid}
            Bili-->>S: 视频列表
        and
            S->>YT: GET /youtube/v3/search?channelId={id}
            YT-->>S: 视频列表
        end

        S->>DB: 比对 platform_video_id，找出新视频
        S->>DB: INSERT 新视频到 Video 表
        S->>DB: INSERT CrawlLog（success/failed）

        loop 每个新视频
            S->>DB: 查询该 Creator 所属 User 的 FeishuConfig
            S->>DB: 检查 NotificationLog（去重）
            alt 未推送过
                S->>Feishu: POST webhook（卡片消息）
                Feishu-->>S: 200 OK
                S->>DB: INSERT NotificationLog
            end
        end
    end
```

### 4.2 用户添加博主流程

```mermaid
sequenceDiagram
    participant U as 用户浏览器
    participant BE as FastAPI
    participant Resolver as URL 解析器
    participant Crawler as 平台 Crawler
    participant DB as PostgreSQL

    U->>BE: POST /api/creators {url: "https://..."}
    BE->>Resolver: resolve_creator_from_url(url)
    Resolver->>Crawler: resolve_creator(url)
    Crawler->>外部API: 获取博主信息
    外部API-->>Crawler: 名称、头像等
    Crawler-->>Resolver: CreatorInfo
    Resolver-->>BE: (platform, CreatorInfo)
    BE->>DB: INSERT Creator
    BE->>Crawler: fetch_latest(platform_id)
    Crawler-->>BE: 视频列表
    BE->>DB: INSERT Videos
    BE-->>U: 201 {creator: {...}}
```

### 4.3 前端信息流加载流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant Vue as 前端
    participant BE as FastAPI
    participant DB as PostgreSQL

    U->>Vue: 打开信息流页面
    Vue->>BE: GET /api/videos?limit=20
    BE->>DB: SELECT videos JOIN creators WHERE creator.user_id = current_user ORDER BY published_at DESC
    DB-->>BE: 视频列表
    BE-->>Vue: [{video}, ...]
    Vue-->>U: 渲染视频卡片

    U->>Vue: 滚动到底部
    Vue->>BE: GET /api/videos?cursor={last_published_at}&limit=20
    BE-->>Vue: 更多视频
    Vue-->>U: 追加渲染
```

---

## 五、数据库 / 数据模型设计

### 5.1 ER 图

```mermaid
erDiagram
    User ||--o{ Creator : "关注"
    User ||--o{ UserVideoStatus : "标记状态"
    User ||--o| FeishuConfig : "配置通知"
    User ||--o{ NotificationLog : "接收通知"
    Creator ||--o{ Video : "发布视频"
    Creator ||--o{ CrawlLog : "抓取记录"
    Video ||--o{ UserVideoStatus : "用户状态"
    Video ||--o{ NotificationLog : "通知记录"

    User {
        uuid id PK
        string email UK
        string password_hash
        datetime created_at
    }
    Creator {
        uuid id PK
        uuid user_id FK
        string platform "bilibili|youtube"
        string platform_id "UP主uid / channel_id"
        string name
        string avatar_url
        string profile_url
        string notes "用户自定义备注"
        bool notify_enabled
        datetime created_at
    }
    Video {
        uuid id PK
        uuid creator_id FK
        string platform_video_id "平台原始视频ID"
        string platform
        string title
        string thumbnail_url
        string video_url
        datetime published_at
        jsonb raw_data "平台原始JSON，供三期AI处理"
        datetime created_at
    }
    UserVideoStatus {
        uuid id PK
        uuid user_id FK
        uuid video_id FK
        bool is_read
        bool is_favorited
    }
    FeishuConfig {
        uuid id PK
        uuid user_id FK "UK"
        string webhook_url
        datetime updated_at
    }
    NotificationLog {
        uuid id PK
        uuid user_id FK
        uuid video_id FK
        string channel "feishu|email(二期)"
        datetime sent_at
    }
    CrawlLog {
        uuid id PK
        uuid creator_id FK
        string status "success|failed"
        string error_msg
        int videos_found
        datetime crawled_at
    }
```

### 5.2 关键约束

| 表 | 唯一约束 | 作用 |
|----|----------|------|
| `Creator` | `(user_id, platform, platform_id)` | 同一用户不重复关注同一博主 |
| `Video` | `(creator_id, platform_video_id)` | 视频去重入库 |
| `UserVideoStatus` | `(user_id, video_id)` | 每用户每视频唯一一条状态 |
| `FeishuConfig` | `user_id` | 每用户唯一一个飞书配置 |
| `NotificationLog` | `(user_id, video_id, channel)` | 天然防止重复推送 |

### 5.3 核心数据模型伪代码

```python
class Platform(str, Enum):
    BILIBILI = "bilibili"
    YOUTUBE  = "youtube"
    # 二期扩展：WEIBO = "weibo"

class Creator(Base):
    __tablename__ = "creators"
    __table_args__ = (UniqueConstraint("user_id", "platform", "platform_id"),)
    id: UUID;  user_id: UUID;  platform: Platform
    platform_id: str;  name: str;  avatar_url: str
    profile_url: str;  notes: str | None;  notify_enabled: bool = True

class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (UniqueConstraint("creator_id", "platform_video_id"),)
    id: UUID;  creator_id: UUID;  platform: Platform
    platform_video_id: str;  title: str
    thumbnail_url: str;  video_url: str
    published_at: datetime;  raw_data: dict  # JSONB

class CrawlLog(Base):
    __tablename__ = "crawl_logs"
    id: UUID;  creator_id: UUID
    status: Literal["success", "failed"]
    error_msg: str | None;  videos_found: int;  crawled_at: datetime
```

---

## 六、核心模块设计

### 6.1 采集器（适配器模式）

新增平台只需新增子类并注册到 `CrawlerRegistry`，不改动现有代码。

```python
# services/crawlers/base.py

@dataclass
class CreatorInfo:
    platform_id: str;  name: str;  avatar_url: str;  profile_url: str

@dataclass
class VideoItem:
    platform_video_id: str;  title: str;  thumbnail_url: str
    video_url: str;  published_at: datetime;  raw_data: dict

class BaseCrawler(ABC):
    platform: Platform

    @abstractmethod
    async def resolve_creator(self, url: str) -> CreatorInfo: ...

    @abstractmethod
    async def fetch_latest(self, platform_id: str, limit: int = 20) -> list[VideoItem]: ...
```

**B 站实现要点：**
- 接口：`GET api.bilibili.com/x/space/arc/search?mid={uid}&pn=1&ps=20&order=pubdate`
- 无需登录 Token，公开接口
- 请求间随机延迟 0.5~1.5s，User-Agent 模拟浏览器，防限流

**YouTube 实现要点：**
- 接口：`GET googleapis.com/youtube/v3/search?channelId={id}&order=date&maxResults=20&key={KEY}`
- 需 Google API Key（免费配额每日 10,000 units，每次查询约 100 units）

### 6.2 通知器（适配器模式）

```python
# services/notifiers/base.py

@dataclass
class NotifyPayload:
    creator_name: str;  platform: Platform
    video_title: str;  thumbnail_url: str;  video_url: str

class BaseNotifier(ABC):
    channel: str  # "feishu"，二期扩展 "email"

    @abstractmethod
    async def send(self, config: str, payload: NotifyPayload) -> None: ...
```

**飞书实现：** 发送 Interactive Card 消息（含封面图、标题、跳转按钮）。

### 6.3 URL 解析器

```python
# services/resolver.py
PLATFORM_PATTERNS = {
    Platform.BILIBILI: [
        r"bilibili\.com/space/(\d+)",      # UP主主页
        r"bilibili\.com/video/(BV\w+)",    # 视频页（反推UP主）
    ],
    Platform.YOUTUBE: [
        r"youtube\.com/channel/([\w-]+)",
        r"youtube\.com/@([\w-]+)",
    ],
}

async def resolve_creator_from_url(url: str) -> tuple[Platform, CreatorInfo]:
    # 1. 正则匹配识别平台
    # 2. 路由到对应 Crawler.resolve_creator()
    # 3. 返回 (platform, CreatorInfo)
```

### 6.4 调度器

```python
# services/scheduler.py

@scheduler.scheduled_job("interval", minutes=30, max_instances=1)
async def crawl_all_creators():
    creators = await db.fetch_all_creators()
    for creator in creators:
        try:
            crawler    = CrawlerRegistry.get(creator.platform)
            items      = await crawler.fetch_latest(creator.platform_id)
            new_videos = await db.filter_new_videos(creator.id, items)
            await db.insert_videos(new_videos)
            await db.insert_crawl_log(creator.id, "success", len(new_videos))
            await notify_users(creator, new_videos)
        except Exception as e:
            await db.insert_crawl_log(creator.id, "failed", error_msg=str(e))
            # 继续处理下一个博主，不中断
```

**容错设计：** 单博主失败不影响其他博主；失败写入 `CrawlLog`，前端可查看并手动重试。

---

## 七、接口设计

所有接口统一前缀 `/api`，返回格式：

```json
{ "data": {}, "message": "ok" }    // 成功
{ "detail": "错误描述" }            // 失败（HTTP 4xx/5xx）
```

### 7.1 认证

| 方法 | 路径 | 请求体 | 说明 |
|------|------|--------|------|
| POST | `/api/auth/register` | `{email, password}` | 注册，返回 `{user, token}` |
| POST | `/api/auth/login` | `{email, password}` | 登录，Token 有效期 30 天 |
| GET  | `/api/auth/me` | — | 获取当前用户，需 Bearer Token |

### 7.2 博主管理

| 方法 | 路径 | 请求体 / 参数 | 说明 |
|------|------|--------------|------|
| GET    | `/api/creators` | — | 获取当前用户博主列表 |
| POST   | `/api/creators` | `{url}` | 粘贴主页 URL，后端解析后立即抓取一次 |
| DELETE | `/api/creators/{id}` | — | 删除博主 |
| PATCH  | `/api/creators/{id}` | `{notes?, notify_enabled?}` | 更新备注 / 通知开关 |
| POST   | `/api/creators/{id}/crawl` | — | 手动触发立即抓取 |

### 7.3 视频流

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET   | `/api/videos` | `platform?`, `cursor?`, `limit=20` | 视频流，游标分页 |
| PATCH | `/api/videos/{id}/status` | `{is_read?, is_favorited?}` | 更新已读 / 收藏状态 |

### 7.4 设置

| 方法 | 路径 | 请求体 | 说明 |
|------|------|--------|------|
| GET | `/api/settings/feishu` | — | 获取飞书 Webhook 配置 |
| PUT | `/api/settings/feishu` | `{webhook_url}` | 保存 Webhook URL |

### 7.5 抓取日志

| 方法 | 路径 | 参数 | 说明 |
|------|------|------|------|
| GET | `/api/crawl-logs` | `status?=failed`, `limit=50` | 抓取记录，按时间降序 |

---

## 八、前端页面结构

### 8.1 路由与页面

| 路由 | 组件 | 需要登录 | 核心内容 |
|------|------|----------|----------|
| `/login` | `LoginView` | 否 | 邮箱密码登录表单 |
| `/register` | `RegisterView` | 否 | 邮箱密码注册表单 |
| `/` | `FeedView` | 是 | 主信息流 |
| `/creators` | `CreatorsView` | 是 | 博主列表管理 |
| `/settings` | `SettingsView` | 是 | 飞书 Webhook 配置 |
| `/crawl-logs` | `CrawlLogsView` | 是 | 抓取日志查看 |

### 8.2 主要页面说明

**FeedView（信息流主页）**
- 顶部：`FeedFilter` 平台切换（全部 / B站 / YouTube）
- 主体：`VideoCard` 列表，按 `published_at` 降序排列，无限滚动加载
- `VideoCard` 展示：封面图、标题、博主头像+名称、发布时间、平台标识角标、点击整卡跳转原视频

**CreatorsView（博主管理）**
- 顶部：URL 输入框 + 添加按钮（粘贴链接后自动解析）
- 主体：`CreatorItem` 列表，展示头像、名称、平台、备注、通知开关、删除按钮

**CrawlLogsView（抓取日志）**
- 表格：博主名称、抓取时间、状态、新增视频数、失败原因
- 失败行红色高亮，每行有手动重试按钮

### 8.3 全局布局

```
┌──────────────────────────────────────────────────────┐
│  NavBar：Logo  |  信息流  |  博主  |  设置  |  日志  |  退出  │
├──────────────────────────────────────────────────────┤
│                                                      │
│                    <RouterView />                    │
│                                                      │
└──────────────────────────────────────────────────────┘
```

---

## 九、部署方案

### 9.1 本地开发

```bash
docker-compose up
# 启动：postgres:5432 | redis:6379 | backend:8000（热重载）| frontend:5173（Vite Dev）
```

### 9.2 生产环境（阿里云香港 ECS）

```yaml
# docker-compose.prod.yml
services:
  nginx:      # ports: 80, 443
  backend:    # expose: 8000（仅内网）
  frontend:   # Vite 构建产物，由 Nginx 静态文件服务
  postgres:   # expose: 5432（仅内网，后续可换 RDS）
  redis:      # expose: 6379（仅内网）
```

**部署步骤：**

```
1. 服务器安装 Docker + Docker Compose
2. 克隆代码，cp .env.example .env，填写生产配置
3. docker-compose -f docker-compose.prod.yml up -d --build
4. docker exec backend alembic upgrade head
5. Certbot 申请 HTTPS 证书，挂载到 Nginx
```

**Nginx 路由规则：**
- `/api/*` → 转发到 `backend:8000`
- `/*` → 返回 `index.html`（Vue SPA 路由兜底）

---

## 十、本期交付功能清单

### P0（必须交付）

| # | 功能 | 涉及模块 |
|---|------|----------|
| 1 | 用户注册 / 登录（邮箱+密码，JWT 30天） | `api/auth` |
| 2 | 添加博主（粘贴 URL 自动识别平台和博主信息） | `api/creators` + `resolver` |
| 3 | 博主列表展示（平台、名称、头像） | `api/creators` |
| 4 | 删除博主 | `api/creators` |
| 5 | B 站视频采集（每 30 分钟） | `crawlers/bilibili` + `scheduler` |
| 6 | YouTube 视频采集（每 30 分钟） | `crawlers/youtube` + `scheduler` |
| 7 | 新视频识别与入库 | `scheduler` |
| 8 | 抓取容错（单博主失败不影响其他，写入日志） | `scheduler` + `crawl_logs` |
| 9 | 信息流展示（卡片 + 时间线排序） | `api/videos` + `FeedView` |
| 10 | 平台筛选（全部 / B站 / YouTube） | `FeedView` |
| 11 | 点击跳转原平台视频 | `VideoCard` |
| 12 | 飞书 Webhook 配置 | `api/settings` |
| 13 | 飞书新视频推送（单条 + 去重） | `notifiers/feishu` |

### P1（优先做，可小幅延后）

| # | 功能 |
|---|------|
| 14 | 博主备注名编辑 |
| 15 | 按博主开关飞书通知 |
| 16 | 已读标记 |
| 17 | 收藏功能 |
| 18 | 信息流无限滚动分页 |
| 19 | 抓取日志页（查看失败原因 + 手动重试） |

### P2（有时间再做）

| # | 功能 |
|---|------|
| 20 | 飞书免打扰时段（夜间积压，时段结束后统一推送） |

---

## 十一、实施步骤

### 第一步：基础设施搭建

1. 初始化目录结构
2. 编写 `docker-compose.yml`（postgres、redis、backend、frontend）
3. 编写 `backend/Dockerfile` 和 `frontend/Dockerfile`
4. **验证：** `docker-compose up` 所有容器正常启动

### 第二步：后端核心层

1. `core/config.py`：环境变量读取
2. `core/database.py`：异步 SQLAlchemy engine + session
3. `core/security.py`：JWT + bcrypt
4. `models/models.py`：所有 ORM 模型
5. Alembic 初始化 + 首次迁移
6. **验证：** 数据库表结构正确创建

### 第三步：认证 API

1. `api/auth.py`：register / login / me
2. `api/deps.py`：`get_current_user` 依赖
3. `schemas/schemas.py`：认证 Pydantic 模型
4. **验证：** FastAPI `/docs` 测试注册、登录、获取用户

### 第四步：采集器

1. `crawlers/base.py`：抽象基类 + 数据类
2. `crawlers/registry.py`：CrawlerRegistry
3. `crawlers/bilibili.py`：B 站实现
4. `crawlers/youtube.py`：YouTube 实现
5. `resolver.py`：URL 解析
6. **验证：** 用真实博主链接测试 `resolve_creator` 和 `fetch_latest`

### 第五步：博主管理 API + 调度器

1. `api/creators.py`：CRUD + 手动触发
2. `scheduler.py`：`crawl_all_creators()` 定时任务
3. `api/crawl_logs.py`：日志查询
4. **验证：** 添加博主后自动抓取，日志正常写入

### 第六步：通知模块

1. `notifiers/base.py`：BaseNotifier
2. `notifiers/feishu.py`：飞书 Interactive Card
3. `api/settings.py`：Webhook 配置接口
4. **验证：** 触发抓取后飞书群收到推送

### 第七步：视频流 API

1. `api/videos.py`：游标分页 + 状态更新
2. **验证：** 接口返回正确的视频列表和分页数据

### 第八步：前端基础搭建

1. `npm create vue@latest`，安装 Tailwind、Element Plus
2. `router/index.ts`：路由 + 导航守卫
3. `api/client.ts`：Axios + Token 拦截器
4. `stores/auth.ts`：Token 持久化
5. **验证：** 登录页正常渲染，登录后跳转信息流

### 第九步：前端页面实现

1. `LoginView` / `RegisterView`
2. `CreatorsView` + `CreatorItem`
3. `FeedView` + `VideoCard` + `FeedFilter`
4. `SettingsView`
5. `CrawlLogsView`

### 第十步：生产部署

1. 编写 `docker-compose.prod.yml` + `nginx/nginx.conf`
2. 服务器环境准备（Docker、域名解析）
3. 部署 + 执行数据库迁移
4. Certbot 配置 HTTPS
5. **全流程验证：** 注册 → 添加博主 → 等待采集 → 信息流展示 → 飞书通知

---

## 十二、附录：代码规范与命名习惯

### 12.1 Python（后端）

| 元素 | 命名方式 | 示例 |
|------|----------|------|
| 变量、函数 | `snake_case` | `get_current_user` |
| 类 | `PascalCase` | `BaseCrawler`、`FeishuNotifier` |
| 常量 | `UPPER_SNAKE_CASE` | `ACCESS_TOKEN_EXPIRE_MINUTES` |
| 私有方法 | `_` 前缀 | `_parse_response` |
| 模块文件 | `snake_case.py` | `crawl_logs.py` |
| 类型注解 | 全量标注 | `async def fetch(...) -> list[VideoItem]:` |

**格式：** 遵循 PEP 8，使用 `ruff` 格式化。
**导入顺序：** 标准库 → 三方库 → 本地模块，组间空一行。
**异步：** 所有 I/O（DB、HTTP）使用 `async/await`，路由和 Service 统一声明 `async def`。

### 12.2 TypeScript / Vue（前端）

| 元素 | 命名方式 | 示例 |
|------|----------|------|
| 变量、函数 | `camelCase` | `fetchVideos`、`isLoading` |
| 组件文件 | `PascalCase.vue` | `VideoCard.vue` |
| 组件名（模板） | `PascalCase` | `<VideoCard />` |
| Pinia store | `use` 前缀 | `useAuthStore` |
| API 函数 | `动词 + 名词` | `getCreators`、`deleteCreator` |
| TypeScript 类型 | `PascalCase` | `interface VideoItem` |

**Vue 规范：** 使用 `<script setup>` 语法；Props 用 `defineProps<{...}>()`；模板中不写复杂逻辑，抽为 `computed`。

### 12.3 REST API

| 元素 | 规范 | 示例 |
|------|------|------|
| URL 路径 | `kebab-case`，复数名词 | `/api/crawl-logs` |
| JSON 字段 | `snake_case` | `creator_id`、`published_at` |
| 状态码 | 200 查询/更新，201 创建，204 删除 | — |

### 12.4 Git 提交规范

格式：`<type>(<scope>): <subject>`

| type | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构 |
| `chore` | 构建 / 配置 / 依赖 |
| `docs` | 文档变更 |

示例：
```
feat(crawlers): add YouTube Data API v3 crawler
fix(scheduler): prevent duplicate notification on retry
chore(docker): add redis service to compose
```

### 12.5 环境变量命名

- 全部大写，下划线分隔，按服务分组
- 所有变量必须在 `.env.example` 中有占位说明

```env
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/trendradar
REDIS_URL=redis://redis:6379/0
SECRET_KEY=your-secret-key
ACCESS_TOKEN_EXPIRE_MINUTES=43200
YOUTUBE_API_KEY=your-google-api-key
BILIBILI_SESSDATA=                   # 可选，一期留空
```

---

## 十三、开发步骤

本节为实际上手开发的操作指引，按顺序执行即可从零搭起本地开发环境并完成功能开发。

---

### 第一阶段：本地环境准备

**前置依赖**

确保本机已安装以下工具：
- Docker Desktop（含 Docker Compose）
- Python 3.12（建议用 pyenv 管理版本）
- Node.js 20+（建议用 nvm 管理版本，仅用于前端构建）
- Git

**克隆项目并初始化目录**

```bash
git clone <repo-url> trendradar
cd trendradar

# 创建后端虚拟环境
python -m venv backend/.venv
source backend/.venv/bin/activate       # Windows: backend\.venv\Scripts\activate
pip install -r backend/requirements.txt

# 初始化前端依赖
cd frontend && npm install && cd ..

# 复制环境变量模板
cp .env.example .env
# 编辑 .env，填写 SECRET_KEY 和 YOUTUBE_API_KEY
```

**启动基础服务（数据库 + 缓存）**

```bash
# 仅启动 postgres 和 redis，后端和前端分别独立运行以便热重载
docker-compose up postgres redis -d
```

---

### 第二阶段：后端开发

**执行数据库迁移**

```bash
cd backend
source .venv/bin/activate

# 首次初始化 alembic（已存在则跳过）
alembic init alembic

# 生成迁移脚本（修改 models 后执行）
alembic revision --autogenerate -m "initial tables"

# 应用迁移
alembic upgrade head
```

**启动后端开发服务器**

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问 `http://localhost:8000/docs` 查看自动生成的 API 文档，可直接在页面上测试所有接口。

**后端开发顺序建议**

按以下顺序逐模块开发，每完成一个模块在 `/docs` 页面验证后再进入下一个：

1. `core/` — config、database、security（无业务逻辑，先跑通数据库连接）
2. `models/models.py` + alembic 迁移（建表验证）
3. `api/auth.py` + `schemas/` — 注册、登录接口
4. `services/crawlers/base.py` + `bilibili.py` — 先用脚本手动调用验证采集结果
5. `services/crawlers/youtube.py` — 同上
6. `services/resolver.py` — 测试几个真实链接的解析结果
7. `api/creators.py` — 添加博主接口，联调 resolver + crawler
8. `services/scheduler.py` — 定时任务，手动触发一次验证全链路
9. `services/notifiers/feishu.py` + `api/settings.py` — 配置 Webhook 后触发推送验证
10. `api/videos.py` — 视频流接口
11. `api/crawl_logs.py` — 日志查询接口

**常用后端命令**

```bash
# 格式化代码
ruff format app/

# 检查代码规范
ruff check app/

# 手动触发一次采集任务（调试用）
python -c "import asyncio; from app.services.scheduler import crawl_all_creators; asyncio.run(crawl_all_creators())"

# 查看当前数据库迁移状态
alembic current

# 回滚上一次迁移
alembic downgrade -1
```

---

### 第三阶段：前端开发

**启动前端开发服务器**

```bash
cd frontend
npm run dev
# 访问 http://localhost:5173
```

前端 Vite Dev Server 会将 `/api/*` 请求代理到 `localhost:8000`，因此后端必须同时运行。在 `vite.config.ts` 中配置代理：

```ts
// vite.config.ts
server: {
  proxy: {
    '/api': 'http://localhost:8000'
  }
}
```

**前端开发顺序建议**

1. `api/client.ts` — Axios 实例，配置 baseURL 和 Token 拦截器
2. `stores/auth.ts` — 登录状态管理，Token 存入 localStorage
3. `router/index.ts` — 路由配置，导航守卫（未登录重定向到 `/login`）
4. `views/LoginView.vue` + `views/RegisterView.vue` — 先打通登录流程
5. `api/creators.ts` + `views/CreatorsView.vue` — 博主管理页面
6. `api/videos.ts` + `views/FeedView.vue` + `components/feed/VideoCard.vue` — 核心信息流
7. `views/SettingsView.vue` — 飞书配置页面
8. `views/CrawlLogsView.vue` — 抓取日志页面

**常用前端命令**

```bash
# 启动开发服务器
npm run dev

# 构建生产产物
npm run build

# 预览生产构建
npm run preview

# 类型检查
npm run type-check
```

---

### 第四阶段：联调与验证

**全链路手动验证流程**

按以下步骤端到端验证核心功能是否正常工作：

```
1. 注册账号，登录后获取 Token
2. 在设置页填写飞书群机器人的 Webhook URL
3. 在博主管理页粘贴一个 B 站 UP 主主页链接，点击添加
   → 预期：系统识别出 UP 主名称和头像，并立即触发一次采集
4. 在博主管理页粘贴一个 YouTube 频道链接，点击添加
5. 打开信息流页，检查视频卡片是否正常显示
6. 切换平台筛选（B站 / YouTube），验证筛选是否生效
7. 在抓取日志页查看采集记录，确认无失败项
8. 在飞书群检查是否收到推送消息，点击按钮能否正常跳转
9. 等待 30 分钟后，验证定时任务是否自动执行
```

**验证 API 的快捷方式**

后端启动后可直接访问 `http://localhost:8000/docs`，使用 Swagger UI 界面测试所有接口，无需 Postman。

---

### 第五阶段：生产部署

**构建并部署**

```bash
# 在服务器上
git pull origin main

# 构建并启动所有服务
docker-compose -f docker-compose.prod.yml up -d --build

# 执行数据库迁移
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head

# 查看服务日志
docker-compose -f docker-compose.prod.yml logs -f backend
```

**申请 HTTPS 证书**

```bash
# 确保域名已解析到服务器 IP，80 端口已开放
docker run --rm \
  -v /etc/letsencrypt:/etc/letsencrypt \
  -v /var/www/certbot:/var/www/certbot \
  -p 80:80 \
  certbot/certbot certonly --standalone -d your-domain.com

# 将证书路径配置到 nginx/nginx.conf 后重启 nginx
docker-compose -f docker-compose.prod.yml restart nginx
```

**日常更新部署**

```bash
git pull origin main
docker-compose -f docker-compose.prod.yml up -d --build backend frontend
# 如有数据库变更
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```