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
- **Trends** — 步数 / 心率 / 睡眠 / 体重的历史趋势
- **Workouts** — 运动记录列表
- **Upload** — 上传 Apple Health `export.zip` 或小米运动健康导出文件
- **Settings** — 数据来源优先级、汇总重算

首次使用请先前往 **Upload** 页面上传一份 Apple Health 导出数据。
"""
)
