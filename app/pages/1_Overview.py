import plotly.graph_objects as go
import streamlit as st

import queries as q
from style import apply_layout, source_color, source_label

st.set_page_config(page_title="Overview", page_icon="🩺", layout="wide")
st.title("今日概览")

sources = q.available_sources()
if not sources:
    st.info("还没有数据，请先前往 **Upload** 页面上传 Apple Health 或小米运动健康导出文件。")
    st.stop()

source_filter = st.selectbox(
    "数据来源",
    ["all"] + list(q.SOURCES),
    format_func=lambda s: "全部（自动按优先级选择）" if s == "all" else source_label(s),
)

today_start, today_end = q.today_range()
week_start, _ = q.last_n_days_range(7)


def format_minutes(total_minutes: float) -> str:
    hours = int(total_minutes // 60)
    minutes = int(total_minutes % 60)
    return f"{hours}h {minutes}m"


def kpi_column(col, label, metric_type, agg, value_fmt, sub_keys=None, is_sum=True):
    value, _ = q.kpi_value(metric_type, agg, today_start, today_end, source_filter, sub_keys)
    week_total, _ = q.kpi_value(metric_type, agg, week_start, today_end, source_filter, sub_keys)
    baseline = (week_total / 7.0) if (week_total is not None and is_sum) else week_total

    delta = None
    if value is not None and baseline is not None:
        delta = value - baseline

    with col:
        st.metric(
            label,
            value_fmt(value) if value is not None else "—",
            delta=value_fmt(delta) if delta is not None else None,
            delta_color="normal" if delta is not None else "off",
        )


c1, c2, c3, c4, c5 = st.columns(5)

kpi_column(c1, "今日步数", "steps", "sum", lambda v: f"{v:,.0f}")
kpi_column(c2, "静息心率", "resting_heart_rate", "avg", lambda v: f"{v:.0f} bpm", is_sum=False)
kpi_column(c3, "活动能量", "active_energy", "sum", lambda v: f"{v:,.0f} kcal")

sleep_value, _ = q.kpi_value(
    "sleep_stage", "sum", *q.last_n_days_range(1), source_filter, q.SLEEP_STAGES
)
with c4:
    st.metric("昨晚睡眠", format_minutes(sleep_value) if sleep_value is not None else "—")

weight_value, weight_ts, weight_src = q.latest_value("weight", source_filter)
with c5:
    st.metric(
        "最新体重",
        f"{weight_value:.1f} kg" if weight_value is not None else "—",
        help=f"{weight_ts:%Y-%m-%d}（{source_label(weight_src)}）" if weight_ts is not None else None,
    )

st.divider()
st.subheader("近 30 天步数趋势")

start_30, end_30 = q.last_n_days_range(30)
df = q.trend_df("steps", start_30, end_30, source_filter)

if df.empty:
    st.caption("暂无步数数据")
else:
    fig = go.Figure()
    for src in sorted(df["source"].unique()):
        sub = df[df["source"] == src]
        fig.add_bar(
            x=sub["day"], y=sub["total"], name=source_label(src),
            marker_color=source_color(src),
        )
    apply_layout(fig)
    fig.update_layout(barmode="group", height=320)
    st.plotly_chart(fig, use_container_width=True)
