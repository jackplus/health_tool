import streamlit as st

from config import DEFAULT_SOURCE_PRIORITY, SOURCE_LABELS
from rollup import compute_daily_rollups

st.set_page_config(page_title="Settings", page_icon="⚙️", layout="wide")
st.title("设置")

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
