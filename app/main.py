import streamlit as st

st.set_page_config(
    page_title="健康数据中心",
    page_icon="🩺",
    layout="wide",
)

st.title("🩺 个人运动健康数据中心")
st.caption("整合 Apple Health 与小米运动健康数据，本地自托管")

st.markdown(
    """
欢迎。使用左侧导航：

- **Overview** — 今日关键指标一览
- **Insights** — 每日状态、每周报告及可解释建议
- **Trends** — 步数 / 心率 / 睡眠 / 体重的历史趋势
- **Workouts** — 运动记录列表
- **Upload** — 上传 Apple Health `export.zip` 或小米运动健康导出文件
- **Settings** — 数据来源优先级、汇总重算

首次使用可在 **Upload** 页面导入历史数据；配置 Health Auto Export 后，后续数据会自动同步。
"""
)
