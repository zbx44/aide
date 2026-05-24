from __future__ import annotations
from typing import List
"""分析任务API路由"""
import logging

from fastapi import APIRouter, HTTPException

from models.schemas import TaskCreateRequest, TaskRunRequest, TaskResponse
from engines.analysis_engine import analysis_engine
from core.scheduler import task_scheduler

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/task", tags=["分析任务"])


@router.get("/list", response_model=List[TaskResponse])
async def list_tasks():
    """任务列表"""
    tasks = await analysis_engine.list_tasks()
    return [TaskResponse(**t) for t in tasks]


@router.post("/create")
async def create_task(req: TaskCreateRequest):
    """创建任务"""
    try:
        result = await analysis_engine.create_task(req.config_yaml)
        # 动态添加到调度器
        import yaml
        config = yaml.safe_load(req.config_yaml)
        if config.get("enabled", True):
            task_scheduler.add_task(config)
        return result
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run")
async def run_task(req: TaskRunRequest):
    """手动执行一次任务"""
    import yaml
    from config.settings import settings

    task_file = settings.TASKS_DIR / f"{req.task_name}.yaml"
    if not task_file.exists():
        raise HTTPException(status_code=404, detail=f"任务不存在: {req.task_name}")

    with open(task_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    try:
        result = await analysis_engine.run_manual(config)
        return result
    except Exception as e:
        logger.error(f"执行任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{task_name}")
async def delete_task(task_name: str):
    """删除任务"""
    from config.settings import settings
    task_file = settings.TASKS_DIR / f"{task_name}.yaml"
    if task_file.exists():
        task_file.unlink()
        task_scheduler.remove_task(task_name)
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail=f"任务不存在: {task_name}")
