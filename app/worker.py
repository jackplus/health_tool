from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler

import db
from analysis import generate_report
from config import APP_TIMEZONE
from rollup import compute_daily_rollups


def generate_daily() -> None:
    today = datetime.now(ZoneInfo(APP_TIMEZONE)).date()
    generate_report("daily", today - timedelta(days=1))


def generate_weekly() -> None:
    today = datetime.now(ZoneInfo(APP_TIMEZONE)).date()
    previous_sunday = today - timedelta(days=today.weekday() + 1)
    generate_report("weekly", previous_sunday)


def main() -> None:
    db.apply_migrations()
    scheduler = BlockingScheduler(timezone=APP_TIMEZONE)
    scheduler.add_job(
        compute_daily_rollups,
        "cron",
        hour=7,
        minute=45,
        kwargs={"days_back": 35},
        id="daily_rollups",
        replace_existing=True,
    )
    scheduler.add_job(
        generate_daily,
        "cron",
        hour=8,
        minute=0,
        id="daily_insight",
        replace_existing=True,
    )
    scheduler.add_job(
        generate_weekly,
        "cron",
        day_of_week="mon",
        hour=8,
        minute=10,
        id="weekly_insight",
        replace_existing=True,
    )
    scheduler.start()


if __name__ == "__main__":
    main()
