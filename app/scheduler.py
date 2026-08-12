"""Optional v2: nightly automatic rollup recompute.

Not started by default -- v1 relies on the manual "Recompute rollups"
button on the Settings page. Only wire this in if query performance
actually warrants automatic nightly refresh.

Streamlit reruns the whole script on every interaction, so the scheduler
must be created exactly once per process; st.cache_resource is the
standard guard against spawning duplicate background schedulers.
"""

import streamlit as st
from apscheduler.schedulers.background import BackgroundScheduler

from rollup import compute_daily_rollups


@st.cache_resource
def start_nightly_rollup_scheduler(hour: int = 3, minute: int = 0) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(
        lambda: compute_daily_rollups(days_back=7),
        trigger="cron",
        hour=hour,
        minute=minute,
        id="nightly_rollup",
        replace_existing=True,
    )
    scheduler.start()
    return scheduler
