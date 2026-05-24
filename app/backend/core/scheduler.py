from __future__ import annotations
from typing import List
"""APScheduler定时任务调度封装"""
import logging
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import yaml

from config.settings import settings

logger = logging.getLogger(__name__)


class TaskScheduler:
    """定时任务调度器"""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._task_funcs = {}  # task_id -> job_id 映射

    def start(self):
        """启动调度器"""
        self.scheduler.start()
        logger.info("任务调度器已启动")

    def shutdown(self):
        """停止调度器"""
        self.scheduler.shutdown()
        logger.info("任务调度器已停止")

    def load_tasks(self):
        """从tasks/目录加载所有任务配置"""
        tasks_dir = settings.TASKS_DIR
        if not tasks_dir.exists():
            return

        for task_file in tasks_dir.glob("*.yaml"):
            try:
                with open(task_file, "r", encoding="utf-8") as f:
                    config = yaml.safe_load(f)
                if config.get("enabled", True):
                    self._add_task(config)
                    logger.info(f"加载任务: {config.get('name', task_file.name)}")
            except Exception as e:
                logger.error(f"加载任务文件失败 {task_file}: {e}")

    def _add_task(self, config: dict):
        """添加定时任务"""
        task_id = config.get("name", "unknown")
        schedule = config.get("schedule", {})

        # 确定触发器
        if "cron" in schedule:
            trigger = CronTrigger.from_crontab(schedule["cron"])
        elif "interval" in schedule:
            trigger = IntervalTrigger(seconds=schedule["interval"])
        else:
            logger.warning(f"任务 {task_id} 无有效调度配置，跳过")
            return

        # 添加任务（实际执行函数后续注入）
        job = self.scheduler.add_job(
            self._execute_task,
            trigger=trigger,
            id=task_id,
            kwargs={"config": config},
            replace_existing=True,
        )
        self._task_funcs[task_id] = job.id

    async def _execute_task(self, config: dict):
        """执行任务（由分析引擎实际实现）"""
        # 延迟导入避免循环依赖
        from engines.analysis_engine import analysis_engine
        await analysis_engine.run_task(config)

    def add_task(self, config: dict):
        """动态添加任务"""
        self._add_task(config)

    def remove_task(self, task_id: str):
        """移除任务"""
        if task_id in self._task_funcs:
            self.scheduler.remove_job(task_id)
            del self._task_funcs[task_id]

    def get_tasks(self) -> List[dict]:
        """获取所有已注册任务"""
        jobs = self.scheduler.get_jobs()
        return [
            {
                "id": job.id,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
            }
            for job in jobs
        ]


# 全局单例
task_scheduler = TaskScheduler()
