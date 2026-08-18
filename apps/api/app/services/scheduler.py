from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from ..config import get_settings
from ..db import session_scope
from .batch_runner import run_daily_batch


settings = get_settings()
_scheduler: BackgroundScheduler | None = None
SCHEDULED_CRAWL_TIMES = ((8, 0), (12, 0), (18, 30))


def _run_scheduled_batch() -> None:
    with session_scope() as session:
        run_daily_batch(session)


def start_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        return
    _scheduler = BackgroundScheduler(timezone=settings.scheduler_timezone)
    for hour, minute in SCHEDULED_CRAWL_TIMES:
        _scheduler.add_job(
            _run_scheduled_batch,
            CronTrigger(hour=hour, minute=minute, timezone=settings.scheduler_timezone),
            id=f"daily-crawl-batch-{hour:02d}{minute:02d}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
    _scheduler.start()


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    _scheduler = None
