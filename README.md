# English_Leaner 前后端开发架构设计文档

> 一个基于 **间隔重复（SM-2）算法** 的英语背单词应用。
> 后端：FastAPI + SQLAlchemy + MySQL；前端：Vue 3 + Pinia + Vue Router + Element Plus。

---

## 目录

1. [总体架构](#一总体架构)
2. [目录结构](#二目录结构)
3. [后端设计](#三后端设计)
   - 3.1 技术栈与依赖
   - 3.2 启动流程
   - 3.3 配置体系
   - 3.4 路由注册机制
   - 3.5 分层设计（handle / database_item / database_operate）
   - 3.6 统一响应格式与异常
   - 3.7 认证与安全
   - 3.8 数据库设计
   - 3.9 核心算法：SM-2
   - 3.10 数据导入脚本
   - 3.11 API 接口清单
4. [前端设计](#四前端设计)
   - 4.1 技术栈
   - 4.2 目录结构
   - 4.3 路由与导航
   - 4.4 状态管理（Pinia stores）
   - 4.5 API 请求层
   - 4.6 布局与页面
   - 4.7 通用组件
   - 4.8 主题系统
   - 4.9 业务时序（学习/复习/拼写/统计）
5. [数据流与核心业务串讲](#五数据流与核心业务串讲)
6. [联调与本地开发](#六联调与本地开发)
7. [生产部署](#七生产部署)
8. [贡献与编码规范](#八贡献与编码规范)

---

## 一、总体架构

```
┌───────────────────────────────┐
│          浏览器 (运维端)          │
│   Vue 3 SPA  <dist>             │
│   views 页面 + Pinia stores     │
│   api/* 通过 axios 请求 /api/v1 │
└──────────────┬────────────────┘
               │  HTTP (JSON, JWT Bearer)
               ▼
┌───────────────────────────────┐
│       FastAPI  应用            │
│  main.py 启动 uvicorn          │
│  config/router.json 动态注册路由│
│  handle/*  端点业务层          │
│  database/* 数据访问层 + ORM   │
└──────────────┬────────────────┘
               │  SQLAlchemy / PyMySQL
               ▼
        ┌──────────────┐
        │    MySQL     │
        │ english_leaner│
        └──────────────┘
```

- **前后端分离**：开发期前端运行在 5173（Vite），通过代理 `/api`、`/uploads` 到后端 8000；后端起在 8000。
- **统一入口**：所有 HTTP API 一律以 `/api/v1/...` 暴露，由 `config/router.json` 单一配置文件驱动注册。
- **统一响应**：所有接口返回 `{ "code": 0, "data": ..., "message": "ok" }`。
- **静态托管**：头像上传到 `server/uploads/`，后端把 `/uploads` 挂载为静态目录；前端构建产物可放入 `server/static/web` 由后端托管（见[生产部署](#七生产部署)）。

---

## 二、目录结构

```
English_Leaner/
├── server/                    # 后端（本文档所在目录）
│   ├── main.py                # 应用入口：读配置、注册路由、启动 uvicorn
│   ├── requirements.txt       # Python 依赖
│   ├── ARCHITECTURE.md        # 旧架构说明
│   ├── config/                # 运行配置
│   │   ├── main_leaner.json   # 应用名 / env / host / port / jwt
│   │   ├── database.json      # MySQL 连接参数
│   │   └── router.json        # 路由表（唯一对外接口清单）
│   ├── database/
│   │   ├── config.py          # 引擎 / SessionLocal / create_all_tables
│   │   ├── database_item.py   # ORM 模型 + 常量
│   │   └── database_operate.py# 数据访问函数 + Pydantic Schema
│   ├── handle/                # 端点业务层（唯一写业务逻辑的地方）
│   │   ├── security.py        # JWT / bcrypt
│   │   ├── user.py            # 认证、个人、头像
│   │   ├── word.py            # 单词
│   │   ├── word_book.py       # 单词书
│   │   ├── learning.py        # 学习 / SM-2 / 复习
│   │   ├── settings.py        # 用户设置
│   │   └── stats.py           # 仪表盘 / 热力图 / 打卡
│   ├── utils/
│   │   ├── dependencies.py    # get_db / get_current_user
│   │   └── exceptions.py      # ok() / BusinessException
│   └── uploads/               # 上传文件（头像等）
│
└── web/                       # 前端
    ├── index.html
    ├── package.json
    ├── vite.config.js         # dev server + 代理 + 别名 @ → src
    ├── .env.example           # VITE_API_BASE_URL
    └── src/
        ├── main.js            # 创建 app、注册全局组件、挂载主题
        ├── App.vue            # 根组件 <router-view/>
        ├── router/index.js    # 路由表 + 导航守卫 + useNavigate
        ├── api/               # axios 请求封装（分量按资源）
        ├── stores/            # Pinia（user / settings / wordBook / learning）
        ├── composables/       # 已移除，统一并入 router 与 main
        ├── components/
        │   ├── common/        # 全局通用组件
        │   ├── layout/        # AppLayout / AppSidebar / AppHeader
        │   └── word/          # 词卡学习相关组件
        └── views/             # 页面
```

> 注：`services` 目录不使用，业务逻辑一律放 `handle/`；项目不设 `app` 目录，代码直接在 `server/` 下。

---

## 三、后端设计

### 3.1 技术栈与依赖

见 [`requirements.txt`](requirements.txt)，核心：

| 依赖 | 用途 |
| --- | --- |
| fastapi | Web 框架 |
| uvicorn[standard] | ASGI 服务器 |
| SQLAlchemy 2.x | ORM |
| PyMySQL | MySQL 驱动 |
| pydantic / email-validator | 请求/响应校验 |
| python-jose + cryptography | JWT 编解码 |
| passlib[bcrypt] + bcrypt | 密码哈希 |
| python-multipart | 文件上传 |
| alembic | SQL 迁移（当前 dev 用自动建表，未启用迁移） |
| pytest + httpx | 测试 |

### 3.2 启动流程（main.py）

文件 [`server/main.py`](main.py)：

1. 模块级读取 `config/router.json` 与 `config/main_leaner.json`（`_Router` / `_Cfg`）。
2. `app = FastAPI(...)`；添加 `CORSMiddleware`（允许来源 `cors_origins`）。
3. 定义 `register_routes()`：遍历 `_Router["route"]`，`import_module(file)` 取模块、`getattr` 取端点函数，添加到 `app.add_api_route`（路径统一加前缀 `/api/v1/`）。
4. `@app.on_event("startup")`：env == dev 时调用 `create_all_tables()` 自动建表。
5. `@app.get("/")`：健康检查，返回 `{"app": name, "status": "running"}`。
6. 从 `handle.user import mount_uploads` 挂载 `/uploads` 静态目录。
7. 顶层调用 `register_routes()`（在 `if __name__` 之外），保证 import 时即注册。
8. `main()`：`uvicorn.run`，dev 开启 `reload=True`。

> **关键约定**：路由注册发生在 `import main.py` 的模块级，`reload=True` 下代码改动会热重载。

### 3.3 配置体系

| 文件 | 内容 | 读取方 |
| --- | --- | --- |
| `config/main_leaner.json` | app_name / env / host / port / jwt | main.py、handle/security.py |
| `config/database.json` | MySQL host/port/user/password/database/charset/pool | database/config.py |
| `config/router.json` | 路由表 | main.py |

示例（`main_leaner.json`）：

```json
{
  "app_name": "English_Leaner",
  "env": "dev",
  "host": "0.0.0.0",
  "port": 8000,
  "jwt": { "secret_key": "...", "algorithm": "HS256", "expire_days": 30 }
}
```

### 3.4 路由注册机制

`config/router.json` 的每条记录：

```json
{ "name": "auth/login", "label": "用户登录", "categary": "auth",
  "file": "handle.user", "fun": "login", "method": "POST" }
```

- `name` → 拼成 `/api/v1/auth/login`
- `file` + `fun` → `import_module('handle.user').login`
- `method` → 请求方法（默认 POST）
- `label` → FastAPI 的 summary/tags

**新增接口的三步**：写 `handle` 端点函数 → 在 `router.json` 登记一行 → 重启/热重载即生效。前端无需知道后端实现，只按路径调用。

### 3.5 分层设计

#### database_item.py（模型 + 常量，简称 `db_item`）

仅存放 SQLAlchemy ORM 模型与状态/算法常量。通过 `import database.database_item as db_item` 引用。

- 常量：`STATUS_NEW/STATUS_LEARNING/STATUS_MASTERED`、`DEFAULT_EASE_FACTOR`、`MIN_EASE_FACTOR`、`DEFAULT_DAILY_TARGET=20` 等。
- 模型：`Base`、`User`、`WordBook`、`WordBookWord`、`Word`、`UserWordRecord`、`UserSetting`。

#### database_operate.py（数据访问函数 + Schema，简称 `db_operate`）

- 内部通用工具：`_get/_get_by/_list/_count/_add/_add_all/_commit`。
- 按资源划分的数据访问函数（`User_*` / `Word_*` / `WordBook_*` / `Record_*` / `Setting_*` / `DB_Commit` / `UserMastered_Count`）。
- 全部 Pydantic Schema（`LoginRequest`、`UserResponse`、`WordCard`、`TodayCardsResponse`、`DashboardStats`、`SettingsResponse` 等）。

> **约定**：业务层不直接使用 SQLAlchemy 会话操作 ORM；一律经 `db_operate.xxx()` 访问数据，经 `db_item.xxx` 引用模型/常量。

#### handle /（端点业务层）

- 每个文件对应一类资源的端点函数（`user.py`、`word.py`、`word_book.py`、`learning.py`、`settings.py`、`stats.py`）。
- 函数签名：`def func(payload/schema, user=Depends(get_current_user), db=Depends(get_db))`。
- 返回统一由 `utils.exceptions.ok(data=..., message=...)` 包裹。
- 业务逻辑（如 SM-2、统计过滤）写在这里的模块级函数内。

### 3.6 统一响应格式与异常

`utils/exceptions.py`：

- `ok(data, message="ok")` → `{ "code": 0, "data": data, "message": message }`
- `BusinessException`（继承 HTTPException），带自定义 `code`。

业务层错误一般直接 `raise HTTPException(status_code, detail)`；前端 axios 拦截器根据 `code !== 0` 或非 2xx 提示。

### 3.7 认证与安全（handle/security.py + utils/dependencies.py）

- **密码**：`passlib` + bcrypt，`hash_password` / `verify_password`。
- **JWT**：`python-jose`。`create_access_token(sub=user_id, exp=now+30days)`；`decode_token` 校验签名。密钥与算法读自 `main_leaner.json`。
- **依赖注入**：
  - `get_db()`：每个请求新建 Session，finally 关闭。
  - `get_current_user()`：从 `Authorization: Bearer <token>` 解析 `sub`，查库返回 User，无效则抛 401。
  - `get_current_user_id()`：便捷取 id。
- 前端登录后存 `access_token`，axios 请求拦截器自动带 `Authorization` 头。

### 3.8 数据库设计

库：`english_leaner`（utf8mb4）。表由 `Base.metadata.create_all` 建（dev）。

#### users（用户）
| 字段 | 说明 |
| --- | --- |
| id / username / email / password | 唯一（username、email 带索引） |
| avatar / age / gender / bio | 头像 URL、年龄、性别、简介 |
| created_at / updated_at | 时间戳 |

#### word_books（单词书）
| 字段 | 说明 |
| --- | --- |
| id / name / category / description | 名称、分类（CET4/CET6...）、描述 |
| word_count | 冗余计数（加速查询，导入后 SQL 同步） |
| created_at | 时间 |

#### words（单词，一词可属多书）
| 字段 | 说明 |
| --- | --- |
| id / word | 单词，word 带索引 |
| phonetic / meaning / example | 音标、释义、例句 |

#### word_book_words（单词书 ↔ 单词 多对多）
| 字段 | 说明 |
| --- | --- |
| book_id / word_id | 外键 |
| position | 该书内顺序 |
| 唯一约束 | (book_id, word_id) |

#### user_word_records（用户学习记录，SM-2 核心表）
| 字段 | 说明 |
| --- | --- |
| user_id / word_id | 唯一 (user_id, word_id) |
| status | new / learning / mastered |
| ease_factor / interval_days / repetition | SM-2 三参数 |
| next_review_at / last_review_at | 下次复习 / 上次复习 |
| learned_at | 首次学习时间（用于统计"今日新学"） |
| created_at | 时间 |

#### user_settings（用户设置，key-value）
| 字段 | 说明 |
| --- | --- |
| user_id / key / value | 唯一 (user_id, key)，如 daily_target、current_book_id |
| updated_at | 时间 |

### 3.9 核心算法：SM-2（handle/learning.py）

`sm2_update(record, quality)` 纯函数：

```
quality = int(quality)
ease_factor = max(1.3, ease_factor + (0.1 - (5-quality)*(0.08 + (5-quality)*0.02)))
if quality >= 3:
    repetition 0→interval 1天; 1→6天; 之后 interval*ease
    repetition ++ ; repetition>=5 → mastered, else learning
else:
    repetition=0; interval=1天; status=learning
last_review_at=now; next_review_at = now + interval_days
```

- **学习（新词）**：每日新学上限由 `daily_target`（settings）决定。前端读 `today_cards` 中 `new_cards`；达到配额后刷新不再派发（配额逻辑：`learn_count = min(未学总数, daily_target)`）。
- **复习（due）**：`next_review_at <= now` 的都进入复习，不限量，一次清完当天到期。
- **拼写**：前端用 `learned_cards`（今日已学，含 `learned_at` 的记录），不受每日配额影响。

### 3.10 数据导入脚本

> 导入逻辑原先在 `server/import_words.py`，当前仓库未保留该文件。以下是设计说明：

- 读取 Navicat 导出的 `xxx.sql`（模板 `C:/Users/29504/Desktop/{}.sql`），按 `INSERT INTO \`表\` VALUES (` 前缀逐行解析。
- 字段映射：`english→word`、`sent→phonetic`、`chinese→meaning`；并使用 `csv`（`quotechar="'"`, `doublequote=True`, `skipinitialspace=True`）解析以处理引号。
- 清洗：去掉外围字面单引号、合并 meaning 成对重复（`''` 去重）。
- **多对多**：words 全局去重，一本书内按 `seen_word_ids` 去重，通过 `word_book_words` 建关联。
- 幂等：词书/单词存在则复用；`word_count` 用关联表实时统计，并在末尾用 SQL 同步所有书冗余计数。

### 3.11 API 接口清单（全部经 `/api/v1`）

| 方法 | 路径 | 端点函数 | 说明 |
| --- | --- | --- | --- |
| POST | /auth/register | user.register | 注册 |
| POST | /auth/login | user.login | 登录 |
| POST | /auth/refresh | user.refresh | 刷新令牌 |
| GET | /auth/me | user.me | 当前用户 |
| PUT | /auth/update-me | user.update_me | 更新个人信息 |
| POST | /auth/change-password | user.change_password | 修改密码 |
| POST | /auth/upload-avatar | user.upload_avatar | 上传头像 |
| GET | /word-books | word_book.list_books | 单词书列表（可按分类） |
| GET | /word-books/{id} | word_book.get_book | 详情 + 学习进度 |
| GET | /words | word.list_words | 单词列表（可按书/关键词分页） |
| GET | /words/{id} | word.get_word | 单词详情 |
| GET | /learning/today | learning.today_cards | 今日卡片（新词/复习/已学） |
| POST | /learning/start | learning.start_learning | 初始化某书学习记录 |
| POST | /learning/review | learning.review | 提交复习评分（SM-2） |
| GET | /learning/progress/{id} | learning.get_progress | 某书学习进度 |
| GET | /settings | settings.get_settings | 读用户设置 |
| PUT | /settings | settings.update_settings | 写用户设置 |
| GET | /stats/dashboard | stats.dashboard | 仪表盘（按当前词书过滤） |
| GET | /stats/heatmap | stats.heatmap | 365 天热力图 |
| GET | /stats/streak | stats.streak | 连续打卡 |

---

## 四、前端设计

### 4.1 技术栈

Vue 3（`<script setup>`）、Vite 5、Pinia、Vue Router 4（history 模式）、Element Plus、Axios、Dayjs、Sass。

### 4.2 目录结构

```
web/src/
├── main.js               # 入口：Pinia/router/ElementPlus/全局组件/主题
├── App.vue               # <router-view/>
├── router/index.js       # 路由表 + 守卫 + useNavigate + APP_ROUTES
├── api/                  # axios 封装
│   ├── request.js        # 实例 + 拦截器
│   ├── auth.js / learning.js / word.js / wordBook.js / settings.js / stats.js
├── stores/               # Pinia
│   ├── index.js / user.js / settings.js / wordBook.js / learning.js
├── components/
│   ├── common/           # PageHeader / StatCard / SettingItem / BookCard / CurrentBookCard / AuthCard / StreakBadge / Heatmap
│   ├── layout/           # AppLayout / AppSidebar / AppHeader
│   └── word/             # WordCard / ReviewRating / WordProgress / SpellingPractice
└── views/                # Home / WordBooks / Learning / Settings / Profile / Login / Register
```

### 4.3 路由与导航

`router/index.js`：

- `routes`：`/login`、`/register`（public），`/` 下挂 `AppLayout` 与子路由 `''(/)、books、learning、settings、profile`。
- **导航守卫** `beforeEach`：public 放行；无 token 去登录；有 token 首次校验 `/auth/me`（缓存 `validatedToken`，每会话只调一次后端）；校验失败清 token 回登录页。
- **集中导航** `APP_ROUTES` + `useNavigate()`：新增页面只需在 `APP_ROUTES` 登记，业务组件用 `const { toHome, toBooks, toLearning } = useNavigate()` 跳转，不写死路径。

```js
export const APP_ROUTES = {
  home: { path: '/', name: 'Home' },
  books: { path: '/books', name: 'WordBooks' },
  learning: { path: '/learning', name: 'Learning' },
  settings: { path: '/settings', name: 'Settings' },
  profile: { path: '/profile', name: 'Profile' },
  login: { path: '/login', name: 'Login' },
  register: { path: '/register', name: 'Register' }
}
```

> 由于路由用 history 模式，**生产必须配置 SPA fallback**（见部署）。

### 4.4 状态管理（Pinia stores）

| store | 职责 |
| --- | --- |
| `user` | token + user；login/register/fetchMe/logout，操作 localStorage |
| `settings` | dailyTarget、theme、currentBookId；init 从后端加载，setDailyTarget/setCurrentBook 持久化后端，setTheme 应用 `<html.dark>` |
| `wordBook` | books、current、progress；fetchBooks/selectBook/restoreCurrent |
| `learning` | newCards、learnedCards、summary、queue、queueIndex、current；fetchTodayCards/nextCard/rateCard/reset |

### 4.5 API 请求层（api/request.js）

- `baseURL = import.meta.env.VITE_API_BASE_URL || '/api/v1'`。
- 请求拦截器：带 `Authorization: Bearer <token>`。
- 响应拦截器：`code !== 0` 弹错；网络失败统一提示；401 → 登出并跳登录。
- 各 `api/*.js` 按资源导出函数，只调对应路径。

### 4.6 布局与页面

- `AppLayout.vue`：`el-container` = 侧边栏 + 头部 + `el-main`（内含路由过渡 `fade-up`）。
- `AppSidebar.vue`：Logo + el-menu（学习仪表盘 / 选择单词书 / 开始学习 / 学习设置），`router` 模式按 `$route.path` 高亮。
- 页面（views）：
  - `Home.vue` 学习仪表盘：Hero 欢迎区 + 连续打卡、当前词书卡、三张统计卡（已学/目标、今日学习、累计学习天数）、签到周历。
  - `WordBooks.vue` 选择单词书：PageHeader + 分类筛选 + BookCard 网格 + 继续学习。
  - `Learning.vue` 今日学习：PageHeader + 卡片学习/键盘拼写切换。
  - `Settings.vue`：每日目标 + 页面模式。
  - `Profile.vue` 个人中心：展示 / 修改信息 / 修改密码 / 头像上传。
  - `Login.vue`、`Register.vue`：AuthCard 认证外壳。

### 4.7 通用组件

- **全局注册**（`main.js` 直接 `app.component`）：`PageHeader`、`StatCard`、`SettingItem`、`BookCard`、`CurrentBookCard`、`AuthCard`。页面无需 import 即可使用。
- 按需 import：`StreakBadge`、`Heatmap` 及 `components/word/*`。
- 业务组件：`WordCard`（卡片翻面）、`ReviewRating`（0-5 评分）、`WordProgress`（进度）、`SpellingPractice`（键盘拼写）。

### 4.8 主题系统

- `assets/styles/variables.scss`：浅色 + `html.dark` 深色两套 CSS 变量（`--app-*` 与 Element Plus 覆盖变量）。
- `assets/styles/main.scss`：全局 `.page-container`、`.card`、`.card-hover`、`.stat-num`、滚动条、路由过渡。
- `settings.js`：`theme` 状态 + `applyTheme()`（增删 `<html class="dark">`）；登录页遵循系统偏好，用户可在设置切换并持久化。

### 4.9 业务时序

**今日卡片加载（Learning 页面）**

```
Learning.onMounted → learning.fetchTodayCards()
  → GET /learning/today
  → newCards / learnedCards / summary 写入 store
  → queue = newCards（学习新词）；拼写模式用 learnedCards
```

**词卡评分（卡片学习）**

```
ReviewRating @rate(quality) → learning.rateCard(quality)
  → POST /learning/review { record_id, quality }
  → 后端 SM-2 更新, 返回新状态 → nextCard()
```

**界面翻面/发音**：换卡片自动 `speechSynthesis` 朗读单词；点击卡片翻面显示释义。

**统计（Home 页面）**

```
Home.onMounted → settings.init() → wordBook.fetchBooks() → restoreCurrent → loadDashboard()
  → GET /stats/dashboard?start_date&end_date（默认最近一周）
  → today / total / streak / days 渲染首页仪表盘与签到周历
```

---

## 五、数据流与核心业务串讲

1. **选词书**：`WordBooks` 选中某书 → `wordBook.selectBook(id)`（写 current 并 `settings.setCurrentBook` 持久化）→ `startLearning(id)`（为该用户该书所有词建 `status=new` 记录，幂等）。
2. **今日学习量**：`GET /settings` 提供 `daily_target`（默认 20）。`GET /learning/today` 计算 `learn_count = min(未学总数, daily_target)`，达到后刷新不再给新词。
3. **复习队列**：`next_review_at <= now` 的 due 记录全部返回，遵循遗忘曲线，不限量。
4. **评分 → SM-2**：`post /learning/review` 更新 ease/interval/repetition/status，并写 `learned_at`（首次）、`last_review_at`、`next_review_at`。
5. **统计**：仪表盘按 `settings.current_book_id` 关联 `word_book_words` 过滤，保证只统计当前书；未选书时数据为 0，不显历史残留。

---

## 六、联调与本地开发

### 后端启动

```bash
cd server
pip install -r requirements.txt
python main.py
```

- 默认监听 `0.0.0.0:8000`，dev 自动建表、reload。
- 配置数据库：修改 `config/database.json`。
- 健康检查：`GET http://127.0.0.1:8000/`。

### 前端启动

```bash
cd web
npm install
npm run dev
```

- Vite 起在 `:5173`；`/api`、`/uploads` 代理到 `127.0.0.1:8000`（见 `vite.config.js`）。
- 如需覆盖 API 前缀，复制 `.env.example` 为 `.env` 修改 `VITE_API_BASE_URL`。

### 首次体验流程

注册 → 登录 → 设置页设定每日目标 → 选择单词书 → 开始学习（卡片/拼写）→ 回首页看仪表盘。

---

## 七、生产部署

### 方案 A：后端托管前端（单进程，推荐本项目）

1. 构建前端：`cd web && npm run build` → 产物在 `web/dist`。
2. 把 `web/dist/*` 拷贝到 `server/static/web/`。
3. 在 `server/main.py` 增加静态托管与 SPA fallback（示例）：

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.responses import JSONResponse

DIST_DIR = Path(__file__).parent / "static" / "web"

app.mount("/assets", StaticFiles(directory=DIST_DIR / "assets"), name="assets")

@app.get("/{full_path:path}", include_in_schema=False)
def spa_fallback(full_path: str):
    if full_path == "api" or full_path.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})
    return FileResponse(DIST_DIR / "index.html")
```

> `/uploads` 静态目录由 `handle.user.mount_uploads` 已挂载，头像可正常访问。
> SPA fallback 必须放最后（注册顺序），避免吞掉 API/静态路由。

4. 生产关闭 dev 自动建表（`env` 改 `production`），改用 Alembic 迁移管理表结构。

### 方案 B：前端 nginx + 后端分离（更标准）

`web/dist` 交给 nginx，配置：

```nginx
server {
  listen 80;
  root /path/to/web/dist;
  location / { try_files $uri $uri/ /index.html; }   # SPA fallback
  location /api/  { proxy_pass http://127.0.0.1:8000; }
  location /uploads/ { proxy_pass http://127.0.0.1:8000; }
}
```

### 安全与运维注意

- 生产务必替换 `main_leaner.json` 的 `jwt.secret_key`。
- 生产使用 `uvicorn main:app --host 0.0.0.0 --port 8000 --workers N` 或对接 gunicorn。
- MySQL 连接串已做密码 URL 编码（`quote_plus`）。
- `.gitignore` 忽略 `venv` 与所有 `__pycache__`。

---

## 八、贡献与编码规范

- **后端模块引用**：
  - 模型/常量：`import database.database_item as db_item` + `db_item.X`
  - 函数/Schema：`import database.database_operate as db_operate` + `db_operate.X`
- **业务逻辑位置**：只放 `handle/`；不使用 `services`。
- **接口暴露**：一律在 `config/router.json` 登记，前端按路径访问。
- **不设 app 目录**：代码直接在 `server/` 下，入口 `main.py` 的 `main()`。
- **建表**：dev 用 `Base.metadata.create_all` 自动建，勿手写 DDL/seed.py。
- **前端**：新增页面 → views + router 登记录（含 `APP_ROUTES`）；通用 UI 抽到 `components/common` 并在 `main.js` 全局注册；导航用 `useNavigate()`。
- **主题**：颜色一律取 `var(--app-*)`，不硬编码，保证深浅色都清晰。
```