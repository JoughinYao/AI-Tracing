from __future__ import annotations

from app.services import scheduler


class FakeScheduler:
    def __init__(self, timezone=None):
        self.timezone = timezone
        self.jobs = []
        self.running = False
        self.started = False

    def add_job(self, func, trigger, **kwargs):
        self.jobs.append({"func": func, "trigger": trigger, **kwargs})

    def start(self):
        self.running = True
        self.started = True


def test_start_scheduler_registers_three_daily_runs(monkeypatch):
    created = []

    def fake_background_scheduler(*, timezone):
        instance = FakeScheduler(timezone=timezone)
        created.append(instance)
        return instance

    def fake_cron_trigger(*, hour, minute, timezone):
        return {"hour": hour, "minute": minute, "timezone": timezone}

    monkeypatch.setattr(scheduler, "BackgroundScheduler", fake_background_scheduler)
    monkeypatch.setattr(scheduler, "CronTrigger", fake_cron_trigger)
    monkeypatch.setattr(scheduler, "_scheduler", None)

    scheduler.start_scheduler()

    assert len(created) == 1
    jobs = created[0].jobs
    assert [job["id"] for job in jobs] == ["daily-crawl-batch-0800", "daily-crawl-batch-1200", "daily-crawl-batch-1830"]
    assert [(job["trigger"]["hour"], job["trigger"]["minute"]) for job in jobs] == [(8, 0), (12, 0), (18, 30)]
    assert created[0].started is True
