"""English_Leaner 应用入口

- 读取 config/router.json 动态注册路由（统一对外暴露）
- 请求统一经 /api/v1/<name> 匹配到 handle 模块中的端点函数
- 运行 `python main.py` 即通过 main() 启动 Uvicorn
"""
import json
import uvicorn
from importlib import import_module
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

ROUTER_CONFIG_PATH = Path(__file__).parent / "config" / "router.json"
APP_CONFIG_PATH = Path(__file__).parent / "config" / "main_leaner.json"

API_V1_PREFIX = "/api/v1"


def load_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

_Cfg = load_json(APP_CONFIG_PATH)
_Router = load_json(ROUTER_CONFIG_PATH)

app = FastAPI(title=_Cfg["app_name"], version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=_Cfg.get("cors_origins", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def register_routes() -> None:
    """根据 router.json 动态加载并挂载全部接口。

    每条 route：name(路径) + file(模块，如 handle.user) + fun(端点函数) + method。
    """
    for item in _Router.get("route", []):
        handler = getattr(import_module(item["file"]), item["fun"])
        path = f"{API_V1_PREFIX}/{item['name']}"
        app.add_api_route(
            path,
            handler,
            methods=[item.get("method", "POST")],
            tags=[item.get("categary", item.get("label"))],
            summary=item.get("label"),
            name=f"{item['file']}.{item['fun']}",
        )


@app.on_event("startup")
def on_startup() -> None:
    # dev 环境自动建表，方便快速迭代（生产请用 Alembic）
    if _Cfg.get("env") == "dev":
        from database.config import create_all_tables

        create_all_tables()


@app.get("/")
def root():
    return {"app": _Cfg["app_name"], "status": "running"}


register_routes()

# 头像等图片静态目录挂载：由 user.py 的 mount_uploads 统一处理，保持入口文件简洁
from handle.user import mount_uploads

mount_uploads(app)


def main() -> None:
    uvicorn.run(
        app,
        host=_Cfg["host"],
        port=_Cfg["port"],
        reload=(_Cfg["env"] == "dev"),
        log_level="info",
    )


if __name__ == "__main__":
    main()