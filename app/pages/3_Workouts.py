from datetime import datetime, timedelta, timezone

import streamlit as st

import queries as q
from style import source_label

st.set_page_config(page_title="Workouts", page_icon="🏃", layout="wide")
st.title("运动记录")

col_a, col_b = st.columns([2, 1])
with col_a:
    today = datetime.now(timezone.utc).date()
    date_range = st.date_input(
        "日期范围", value=(today - timedelta(days=90), today), max_value=today
    )
with col_b:
    source_filter = st.selectbox(
        "数据来源",
        ["all"] + list(q.SOURCES),
        format_func=lambda s: "全部" if s == "all" else source_label(s),
    )

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = today - timedelta(days=90), today

start_dt, end_dt = q.local_dates_to_utc(start_date, end_date)

df = q.workouts_df(start_dt, end_dt, source_filter)

if df.empty:
    st.caption("所选时间范围 / 来源下暂无运动记录")
else:
    display = df.copy()
    display["来源"] = display["source"].map(source_label)
    display = display.rename(
        columns={
            "workout_type": "类型",
            "start_timestamp": "开始时间",
            "duration_minutes": "时长(分钟)",
            "distance": "距离",
            "distance_unit": "距离单位",
            "energy_burned": "消耗",
            "energy_unit": "消耗单位",
        }
    )[
        ["来源", "类型", "开始时间", "时长(分钟)", "距离", "距离单位", "消耗", "消耗单位"]
    ]
    st.dataframe(display, use_container_width=True, hide_index=True)
    st.caption(f"共 {len(display)} 条记录")
