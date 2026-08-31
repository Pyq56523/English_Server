# English_Leaner 架构设计文档

> 本文档对应当前代码的真实结构。核心约定：`server` 下不分 `app`，无 `services`/`routers` 目录；业务逻辑统一放 `server/handle/`；路由由 JSON 动态注册；数据库层为「模型 + 操作」双文件。模块范围：用户 / 单词书 / 单词 / 学习(SM-2) / 常用短语 / 统计。

---

## 1. 整体架构

### 1.1 架构风格

```
前后端分离 + 分层架构 (Layered Architecture)
┌────────────────────────────────────────────────┐
│  浏览器 (Vue3 SPA + Element Plus + Pinia)      │
│  Vue Router 懒加载 + 鉴权守卫 + Token 校验     │
└───────────────────┬────────────────────────────┘
                    │ REST API / JSON (axios, Bearer JWT)
┌───────────────────▼────────────────────────────┐
│  Vite Dev Server                              │
│  - 托管前端静态资源                            │
│  - 代理 /api → 127.0.0.1:8000                 │
└───────────────────┬────────────────────────────┘
                    │
┌───────────────────▼────────────────────────────┐
│  FastAPI (Uvicorn, 0.0.0.0:8000)               │
│  main.py ── 入口：读配置/建路由/CORS/启动建表    │
│  ├── config/router.json → 动态注册 API 路径     │
│  ├── handle/*.py  → 端点函数（业务逻辑）        │
│  │   ├── security.py  (JWT + bcrypt)           │
│  │   ├── user / word_book / word / learning    │
│  │   └── phrase / stats                        │
│  ├── utils/       (依赖注入 / 统一响应)        │
│  └── database/    (SQLAlchemy ORM)            │
│      ├── database_item.py   (模型 + 常量)      │
│      └── database_operate.py (DB 交接 + Schema)│
└───────────────────┬────────────────────────────┘
                    │
          ┌─────────▼─────────┐
          │    MySQL 8.x      │
          └───────────────────┘
```

### 1.2 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 前端 | Vue 3 + Vite + Element Plus | Composition API，HMR 热更新 |
| 前端状态 | Pinia | user / learning / wordBook 三个 store |
| 前端路由 | Vue Router 4 | 懒加载 + beforeEach 鉴权守卫 |
| HTTP | Axios | 拦截器带 JWT、统一处理 `{code,data,message}` 与 401 |
| 后端 | FastAPI + Uvicorn | 动态注册路由，dev 自动重载 |
| ORM | SQLAlchemy 2.x | 同步 Session + `create_engine` |
| 数据库 | MySQL 8 + PyMySQL | 同步驱动 |
| 校验 | Pydantic v2 | Schema 定义 `model_config = {"from_attributes": True}` |
| 认证 | python-jose + bcrypt | JWT Token + 密码哈希 |
| 构建 | Vite 5 | 前端构建；Sass 现代 API |

---

## 2. 后端结构

### 2.1 目录与职责

```
server/
├── main.py                       # ★ 应用入口：main() 启动 Uvicorn
│                                 #   读 main_leaner.json / router.json
│                                 #   register_routes() 动态挂载路由
│                                 #   startup 事件自动建表（env=dev）
├── requirements.txt
│
├── config/                       # ★ 配置（JSON）
│   ├── main_leaner.json          # app_name / env / host / port / jwt
│   ├── database.json             # host / port / user / password / database / charset / pool
│   └── router.json               # 路由注册表：{name, file, fun, method}
│
├── database/                     # ★ 数据库层（模型 + 操作双文件）
│   ├── config.py                 # 读 database.json → DATABASE_URL(quote_plus 编码)
│   │                             #   → engine / SessionLocal / create_all_tables()
│   ├── database_item.py          #   模型(Base 子类):User/WordBook/Word/
│   │                             #   UserWordRecord/Phrase
│   │                             #   常量:STATUS_*/DEFAULT_*/MIN_EASE_FACTOR
│   └── database_operate.py       #   DB 交接函数(_get…_commit、User_*、Word_*、
│                                 #   WordBook_*、Record_*、Phrase_*、
│                                 #   DB_Commit、UserMastered_Count)
│                                 #   + Pydantic Schema(LoginRequest…HeatmapData)
│
├── handle/                       # ★ 业务层（端点函数，作为 API handler）
│   ├── security.py               # hash/verify 密码、create/decode JWT
│   ├── user.py                   # register / login / refresh / me
│   ├── word_book.py              # list_books / get_book(含进度)
│   ├── word.py                   # list_words(分页搜索) / get_word
│   ├── learning.py               # today_cards / start_learning / review(SM-2) / get_progress
│   ├── phrase.py                 # list_phrases / get_phrase
│   └── stats.py                  # dashboard / heatmap / streak
│
└── utils/
    ├── dependencies.py           # get_db() / get_current_user(JWT) / get_current_user_id
    └── exceptions.py             # ok() 统一成功响应；BusinessException
```

### 2.2 关键设计约定

- **不做 `app/` / `routers/` / `services/` 分层**：业务全部集中在 `handle/*.py` 的端点函数，由 `router.json` 动态挂载。
- **数据库双文件**：
  - `database_item.py` = ORM 模型 + 常量（纯数据定义）。
  - `database_operate.py` = 与数据库交接的函数 + Pydantic Schema；函数内用 `import database.database_item as db_item` + `db_item.X` 引用模型/常量。
- **引用风格（模块别名）**：业务层模型/常量用 `db_item.X`，函数/Schema 用 `db_operate.X`。
- **统一响应**：所有接口经 `ok(data=..., message=...)` 返回 `{"code": 0, "data": ..., "message": "ok"}`；`code != 0` 视为失败。
- **入口**：`server` 目录下 `python main.py` 启动（依赖相对导入，须在 server 目录运行）。

### 2.3 动态路由机制

`main.py` 读取 `config/router.json` 的 `route` 数组，逐条执行：

```python
path = f"/api/v1/{item['name']}"
app.add_api_route(path, getattr(import_module(item["file"]), item["fun"]),
                  methods=[item["method"]], ...)
```

即 `handle.<file>.<fun>` 被映射到 `GET/POST /api/v1/<name>`。

---

## 3. 前端结构

```
web/
├── vite.config.js                # ★ 插件、别名 @→src、代理 /api→127.0.0.1:8000
├── package.json
├── index.html
├── .env.example                  # VITE_API_BASE_URL
└── src/
    ├── main.js                   # ★ 入口：挂载 pinia/router/ElementPlus + 引入全局样式
    ├── App.vue
    ├── router/index.js           # 路由表 + beforeEach 鉴权守卫（校验 token 有效性）
    ├── assets/styles/
    │   ├── main.scss             # @use variables as *（全局基础样式）
    │   └── variables.scss        # 设计变量 + Element Plus 主题覆盖
    ├── api/                      # 接口封装（request 为 axios 实例）
    │   ├── request.js            # ★ 拦截器：带 JWT、解 {code,data}、401 登出
    │   ├── auth.js / user
    │   ├── wordBook.js / word.js / learning.js / phrase.js / stats.js
    ├── stores/                   # Pinia
    │   ├── user.js               # token / user / login / logout
    │   ├── learning.js           # 今日卡片、复习提交状态
    │   └── wordBook.js           # books / current / 选中进度
    ├── views/                    # 页面：Login / Register / Home / WordBooks /
    │   └── Learning / Phrase / Statistics
    └── components/
        ├── layout/               # AppLayout / AppSidebar / AppHeader
        ├── word/                 # WordCard / ReviewRating / WordProgress
        └── common/               # ConfirmDialog / Heatmap / StreakBadge
```

### 3.1 数据流（一次请求）

```
Vue 页面 → api/<模块>.js → request.js(axios)  → /api/v1/... (带 Bearer JWT)
    → Vite 代理 → FastAPI:8000 → router.json 匹配 → handle.<fun>(db)
    → database_operate.<函数>(db, ...) → SQLAlchemy 模型 → MySQL
    → 返回 {"code":0,"data":...} → 拦截器解出 data → 页面渲染
```

---

## 4. Token 认证机制

### 4.1 认证链路

```
登录成功 → 后端生成 JWT(sub=user_id) → 返回 { access_token, user }
    → 前端存 localStorage(el_token / el_user) → Pinia userStore 持有 token
    → 之后每次请求，axios 请求拦截器加 `Authorization: Bearer <token>`
    → 需鉴权接口用 Depends(get_current_user) 解析并校验 token → 返回当前用户
    → token 无效/过期 → 后端返回 401 → 前端响应拦截器清登录态并跳 /login
```

### 4.2 关键实现点

- **后端签发**（`handle/security.py`）：`create_access_token(sub)` 把 `user_id` 写入 `sub`，密钥/算法/有效期来自 `config/main_leaner.json` 的 `jwt`。
- **后端校验**（`utils/dependencies.py`）：
  ```python
  def get_current_user(token=Depends(oauth2_scheme), db=Depends(get_db)) -> db_item.User:
      payload = security.decode_token(token)      # 解析 JWT
      user_id = int(payload["sub"])               # 取用户 id
      return db_operate.User_Get(db, user_id)     # 查库，不存在则 401
  ```
  需要登录的接口，handler 第一个参数写 `user = Depends(get_current_user)`。
- **前端携带**（`api/request.js` 请求拦截器）：读 `useUserStore().token`，非空则写入 `config.headers.Authorization = "Bearer " + token`。
- **前端揽权/失效处理**：
  - 路由守卫 `beforeEach`：无 token → 直接回 `/login`；有 token 但本会话内未校验 → 调 `/auth/me` 校验一次（结果缓存，避免每次跳转都请求），失败则清登录态回登录页。
  - 响应拦截器：接口返回 401 → `userStore.logout()` + `router.push('/login')`。

### 4.3 为什么表单里看不到密码明文

密码只在注册/登录时经 `bcrypt` 哈希后入库存放；JWT 中只含 `user_id`，不含密码。

---

## 5. 数据库设计

### 5.1 表清单（5 张，由 models 定义）

| 表 | 模型 | 主要字段 |
|----|------|----------|
| `users` | User | id, username, email, password, created_at, updated_at |
| `word_books` | WordBook | id, name, category, description, word_count, created_at |
| `words` | Word | id, word, phonetic, meaning, example, book_id(FK) |
| `user_word_records` | UserWordRecord | ★用户学习记录(SM-2 核心) |
| `phrases` | Phrase | id, phrase, meaning, example, category |

### 5.2 user_word_records（SM-2 核心表）

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | BIGINT | PK | 主键 |
| user_id | BIGINT | FK→users | 用户 |
| word_id | BIGINT | FK→words | 单词 |
| status | ENUM(new,learning,mastered) | DEFAULT new | 学习状态 |
| ease_factor | FLOAT | DEFAULT 2.5 | ★ SM-2 难度因子 |
| interval_days | INT | DEFAULT 0 | ★ 复习间隔(天) |
| repetition | INT | DEFAULT 0 | ★ 已复习次数 |
| next_review_at | DATETIME | INDEX | ★ 下次复习时间 |
| last_review_at | DATETIME | | 上次复习时间 |
| created_at | DATETIME | | 创建时间 |

约束：`UNIQUE(user_id, word_id)`；索引 `(user_id, next_review_at)`、`(user_id, status)`。

### 5.3 建表方式

不用手写 DDL，不依赖迁移脚本依赖：

- `env=dev` 时，后端 `main.py` 的 startup 事件调用 `database/config.py` 的 `create_all_tables()`，它执行 `Base.metadata.create_all(engine)` 自动创建全部表。
- 若要手动建表：在 `server` 目录执行 `python -c "from database.config import create_all_tables; create_all_tables()"`。

---

## 6. 核心业务逻辑过程

### 6.1 认证流程（注册 / 登录 / 刷新）

```
注册 POST /auth/register
  → 校验用户名/邮箱唯一 → bcrypt 哈希 password → 写入 users
  → 返回用户信息

登录 POST /auth/login
  → 按 username 查用户 → verify_password 校验密码
  → 通过 → security.create_access_token(sub=user_id)
  → 返回 { access_token, user }

刷新 POST /auth/refresh
  → 用旧 token 重建新 token（前端 token 快到期时调用）

当前用户 GET /auth/me  （Bearer 鉴权）
  → Depends(get_current_user) → 返回当前用户信息
```

### 6.2 学习流程（单词书 → 学习 → 复习）

```
1. 选择单词书
   前端选 book → POST /learning/start {book_id}
   → 后端取该 book 所有 words，批量初始化 user_word_records(status=new, ease=2.5)

2. 取今日卡片 GET /learning/today   （Bearer 鉴权）
   → new_cards: status='new'（新词，限量）
   → due_cards: status='learning' 且 next_review_at <= 今天（到期复习）
   → summary: total_new / total_due / mastered

3. 翻卡作答（前端）
   展示背面释义+例句 → 用户评分 quality(0-5)

4. 提交评分 POST /learning/review {record_id, quality}   （Bearer 鉴权）
   → 校验 record 属于当前用户（防越权）
   → sm2_update(record, quality)   ★ 纯函数，更新 ease_factor / interval_days / repetition / status / next_review_at
   → 写库，返回新间隔参数

5. 进度 GET /learning/progress/{book_id}   （Bearer 鉴权）
   → 统计该本书 new / learning / mastered / progress_rate
```

### 6.3 SM-2 算法（`handle/learning.py` 的 `sm2_update`）

```
1) ease_factor = max(MIN 1.3, ease_factor + (0.1 - (5-q) * (0.08 + (5-q)*0.02)))
2) q >= 3 (记得):
     repetition 0 → 1天；1 → 6天；否则 round(interval * ease_factor)
     repetition += 1；repetition>=5 → mastered，否则 learning
   否则(没记住):
     repetition=0, interval=1天, status=learning
3) last_review_at=now；next_review_at=now + interval_days 天
```

### 6.4 统计流程

```
仪表盘 GET /stats/dashboard   （Bearer 鉴权）
  → 今日学习/复习数（按 last_review_at 当日过滤）
  → 总数：已学词数 = Record_Count，掌握数 = UserMastered_Count，短语数 = Phrase_Count
  → 连续打卡 = 按复习日期聚合成 streak

热力图 GET /stats/heatmap    （Bearer 鉴权）
  → 近 365 天每天复习数，拼成 dates + counts 数组

连续打卡 GET /stats/streak    （Bearer 鉴权）
  → 当前连续(含今天/昨天)与历史最大连续天数
```

---

## 7. RESTful API

基础路径 `/api/v1`，认证 `Authorization: Bearer <JWT>`，统一响应 `{code, data, message}`（列表支持 `?page= &page_size=`）。

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/auth/register` | 注册 | ❌ |
| POST | `/auth/login` | 登录(返回 token) | ❌ |
| POST | `/auth/refresh` | 刷新 token | ❌ |
| GET | `/auth/me` | 当前用户 | ✅ |
| GET | `/word-books` | 单词书列表(category 筛选) | ❌ |
| GET | `/word-books/{book_id}` | 详情+进度 | ✅ |
| GET | `/words` | 分页/关键词搜索 | ❌ |
| GET | `/words/{word_id}` | 单词详情 | ❌ |
| GET | `/learning/today` | 今日新卡+到期卡 | ✅ |
| POST | `/learning/start` | 初始化某本书学习记录 | ✅ |
| POST | `/learning/review` | 提交评分(SM-2) | ✅ |
| GET | `/learning/progress/{book_id}` | 某本书进度 | ✅ |
| GET | `/phrases` | 短语列表 | ❌ |
| GET | `/phrases/{phrase_id}` | 短语详情 | ❌ |
| GET | `/stats/dashboard` | 仪表盘 | ✅ |
| GET | `/stats/heatmap` | 热力图(365天) | ✅ |
| GET | `/stats/streak` | 连续打卡 | ✅ |

---

## 8. 配置

三个配置文件都在 `server/config/`：

- **`main_leaner.json`**：`app_name`、`env`、`host`、`port`、`jwt{secret_key,algorithm,expire_days}`。
- **`database.json`**：`host/port/user/password/database/charset/pool_size/max_overflow/echo`。构造 URL 时 user/password 经 `urllib.parse.quote_plus` 编码，避免特殊字符(如密码里的 `@`)破坏连接串。
- **`router.json`**：`route[]` 数组，`{name, label, file, fun, method}` 定义接口与后端函数映射。

**启动方式**（须在 `server` 目录）：

```bash
python main.py          # 后端，端口取 main_leaner.json
```

```bash
cd web && npm run dev    # 前端，proxy /api → 127.0.0.1:8000
```

---

## 9. 关键约定（开发须知）

- 后端业务只写 `handle/*.py`，接口一律由 `router.json` 注册；端点函数签名用依赖注入 `db: Session = Depends(get_db)`。
- 需要登录的接口，其 handler 第一个参数取 `user: User = Depends(get_current_user)`；越权校验（如 record.user_id==user.id）必须自己加。
- `database_item.py` 只放模型与常量；查询函数与 Schema 一律在 `database_operate.py`，并在函数内 `import database.database_item as db_item`。
- 表由后端 dev 启动自动创建；不需要手动写 DDL。
- SM-2 是唯一计算核心，改动需同时更新文档第 6.3 节。
- 代码提交：`.gitignore` 已忽略 `venv` / `__pycache__` / `node_modules` / `dist` / `.env`，只提交源代码与配置。

---

*文档版本：v3.0 · 最后更新：2026-08-30 · 依据当前代码结构编写（已移除语法模块）*