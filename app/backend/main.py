from __future__ import annotations
"""AI Assistant - FastAPI主入口

支持新版目录结构：代码(app/)、配置(config/)、数据(data/)、用户(user/)分离
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config.settings import settings
from core.scheduler import task_scheduler
from routers import doc, task, chat, oa, tool, knowledge, query, template, agent, settings_router

# 配置日志
log_dir = settings.LOGS_DIR
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动
    logger.info(f"{'='*50}")
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} 启动中...")
    logger.info(f"项目根目录: {settings.ROOT_DIR}")
    logger.info(f"数据目录: {settings.DATA_DIR}")
    logger.info(f"用户目录: {settings.USER_DIR}")
    logger.info(f"LLM Provider: {settings.LLM_PROVIDER}")
    logger.info(f"LLM地址: {settings.LLM_BASE_URL}")
    logger.info(f"模型: {settings.LLM_MODEL}")

    # 显示配置来源信息
    config_info = settings.get_merged_config_summary()
    if config_info["user_env_exists"]:
        overridden = config_info["user_overridden_keys"]
        if overridden:
            logger.info(f"用户自定义配置项: {overridden}")
    logger.info(f"{'='*50}")

    # 加载定时任务
    task_scheduler.load_tasks()
    task_scheduler.start()

    yield

    # 关闭
    task_scheduler.shutdown()
    logger.info("应用已关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# CORS - 允许前端访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(doc.router)
app.include_router(task.router)
app.include_router(chat.router)
app.include_router(oa.router)
app.include_router(tool.router)
app.include_router(knowledge.router)
app.include_router(query.router)
app.include_router(template.router)
app.include_router(agent.router)
app.include_router(settings_router.router)


@app.get("/api/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "version": settings.APP_VERSION,
        "llm_provider": settings.LLM_PROVIDER,
        "llm_base_url": settings.LLM_BASE_URL,
        "model": settings.LLM_MODEL,
        "root_dir": str(settings.ROOT_DIR),
        "data_dir": str(settings.DATA_DIR),
    }


@app.get("/api/config/info")
async def config_info():
    """配置来源信息（诊断用）"""
    return settings.get_merged_config_summary()


@app.get("/api/upgrade/check")
async def check_upgrade():
    """检查是否有新版本"""
    from core.upgrade import UpgradeClient
    client = UpgradeClient(str(settings.ROOT_DIR))
    update = client.check_update()
    if update:
        return {"has_update": True, "update": update, "current_version": client.get_current_version()}
    return {"has_update": False, "current_version": client.get_current_version()}


@app.get("/api/upgrade/status")
async def upgrade_status():
    """升级系统状态"""
    from core.upgrade import UpgradeClient
    client = UpgradeClient(str(settings.ROOT_DIR))
    return client.get_status()


@app.post("/api/migrations/run")
async def run_migrations():
    """执行待执行的数据库迁移"""
    from core.migrations import MigrationRunner
    runner = MigrationRunner(str(settings.ROOT_DIR))
    result = runner.run_pending()
    return result


# 静态文件（前端构建后放置，必须放最后）
from pathlib import Path
from starlette.responses import FileResponse

_static_dir = Path(__file__).parent / "static"
if _static_dir.exists():
    # SPA回退路由：非/api路径全部返回index.html，让前端路由处理
    _index_html = _static_dir / "index.html"

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """SPA回退：API路径交给FastAPI，其他路径返回index.html"""
        # 如果是API路径，不处理（由API路由接管）
        if full_path.startswith("api/"):
            return None  # 让后续路由处理
        # 如果静态文件存在，返回静态文件
        file_path = _static_dir / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        # SPA回退：返回index.html
        return FileResponse(_index_html)

    app.mount("/", StaticFiles(directory=str(_static_dir), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )
