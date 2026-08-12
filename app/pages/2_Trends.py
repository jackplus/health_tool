from datetime import datetime, timedelta, timezone

import plotly.graph_objects as go
import streamlit as st

import queries as q
from style import apply_layout, source_color, source_label

st.set_page_config(page_title="Trends", page_icon="📈", layout="wide")
st.title("趋势")

sources = q.available_sources()
if not sources:
    st.info("还没有数据，请先前往 **Upload** 页面上传数据。")
    st.stop()

METRIC_OPTIONS = {
    "steps": {"label": "步数", "agg": "sum", "chart": "bar"},
    "heart_rate": {"label": "心率（平均）", "agg": "avg", "chart": "line"},
    "resting_heart_rate": {"label": "静息心率", "agg": "avg", "chart": "line"},
    "active_energy": {"label": "活动能量 (kcal)", "agg": "sum", "chart": "bar"},
    "distance": {"label": "步行+跑步距离", "agg": "sum", "chart": "bar"},
    "weight": {"label": "体重 (kg)", "agg": "avg", "chart": "line"},
    "sleep_stage": {
        "label": "睡眠时长",
        "agg": "sum",
        "chart": "bar",
        "sub_keys": q.SLEEP_STAGES,
    },
}

col_a, col_b, col_c = st.columns([2, 2, 2])
with col_a:
    metric_type = st.selectbox(
        "指标", list(METRIC_OPTIONS.keys()), format_func=lambda m: METRIC_OPTIONS[m]["label"]
    )
with col_b:
    today = datetime.now(timezone.utc).date()
    date_range = st.date_input(
        "日期范围", value=(today - timedelta(days=90), today), max_value=today
    )
with col_c:
    source_filter = st.selectbox(
        "数据来源",
        ["all"] + list(q.SOURCES),
        format_func=lambda s: "全部（对比）" if s == "all" else source_label(s),
    )

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = today - timedelta(days=90), today

start_dt = datetime.combine(start_date, datetime.min.time(), tzinfo=timezone.utc)
end_dt = datetime.combine(end_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(days=1)

spec = METRIC_OPTIONS[metric_type]
df = q.trend_df(metric_type, start_dt, end_dt, source_filter, spec.get("sub_keys"))

if df.empty:
    st.caption("该指标在所选时间范围 / 来源下暂无数据")
else:
    value_col = "total" if spec["agg"] == "sum" else "avg_value"
    fig = go.Figure()
    for src in sorted(df["source"].unique()):
        sub = df[df["source"] == src]
        if spec["chart"] == "bar":
            fig.add_bar(
                x=sub["day"], y=sub[value_col], name=source_label(src),
                marker_color=source_color(src),
            )
        else:
            fig.add_scatter(
                x=sub["day"], y=sub[value_col], name=source_label(src), mode="lines+markers",
                line=dict(color=source_color(src), width=2),
                marker=dict(size=8, color=source_color(src)),
            )
    apply_layout(fig)
    fig.update_layout(barmode="group", height=420)
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("查看数据表"):
        st.dataframe(df.assign(source=df["source"].map(source_label)), use_container_width=True)
