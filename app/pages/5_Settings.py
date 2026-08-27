from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

from analysis import generate_report
from config import APP_TIMEZONE, DEFAULT_SOURCE_PRIORITY, SOURCE_LABELS
import queries as q
from rollup import compute_daily_rollups

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
st.title("设置")

profile = q.profile()
st.subheader("运动目标与限制")
st.caption("这里只保存你主动填写的信息，供规则报告和 Codex 健康分析工具读取。每行一项。")
goals_text = st.text_area("目标", value="\n".join(profile.get("goals") or []))
constraints_text = st.text_area("限制或偏好", value="\n".join(profile.get("constraints") or []))
if st.button("保存目标与限制"):
    goals = [line.strip() for line in goals_text.splitlines() if line.strip()]
    constraints = [line.strip() for line in constraints_text.splitlines() if line.strip()]
    q.update_profile(goals, constraints)
    st.success("已保存")

st.divider()

st.subheader("立即生成分析报告")
st.caption("历史回填完成后可立即生成；自动任务仍会在每天 08:00 和每周一 08:10 运行。")
if st.button("生成最新每日与每周报告"):
    today = datetime.now(ZoneInfo(APP_TIMEZONE)).date()
    daily_end = today - timedelta(days=1)
    weekly_end = today - timedelta(days=today.weekday() + 1)
    with st.spinner("正在分析…"):
        daily = generate_report("daily", daily_end)
        weekly = generate_report("weekly", weekly_end)
    q.insight_reports_df.clear()
    st.success(f"已生成：每日 {daily['status']}；每周 {weekly['status']}")

st.divider()

st.subheader("默认来源优先级")
st.caption(
    "当 Overview / Trends 的来源筛选设为「全部」时，各指标默认展示哪个来源的数据"
    "（另一来源的数据始终保留在数据库中，只是不作为该指标的默认展示对象）。"
    "如需修改，编辑 `app/config.py` 里的 `DEFAULT_SOURCE_PRIORITY` 后重启服务。"
)
st.table(
    {
        "指标": list(DEFAULT_SOURCE_PRIORITY.keys()),
        "默认来源": [SOURCE_LABELS.get(v, v) for v in DEFAULT_SOURCE_PRIORITY.values()],
    }
)

st.divider()
st.subheader("汇总重算（可选）")
st.caption(
    "v1 的看板直接查询原始数据，个人数据量级下通常足够快，无需汇总表。"
    "如果未来数据量变大导致查询变慢，可以在这里手动重算 `daily_rollups` 汇总表。"
)
days_back = st.number_input("重算最近 N 天（留空/0 表示全部历史）", min_value=0, value=30)
if st.button("立即重算"):
    with st.spinner("正在重算…"):
        result = compute_daily_rollups(days_back=days_back or None)
    st.success(f"完成：sum {result['sum']} 行，avg {result['avg']} 行")
