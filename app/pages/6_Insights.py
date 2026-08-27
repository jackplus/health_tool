import streamlit as st

import queries as q

st.set_page_config(page_title="Insights", page_icon="💡", layout="wide")
st.title("每日状态与每周建议")
st.caption("基于个人 28 天基线的透明规则分析，不用于疾病诊断或替代专业医疗意见。")

report_type = st.radio(
    "报告类型", ["daily", "weekly"], horizontal=True,
    format_func=lambda value: "每日状态" if value == "daily" else "每周报告",
)
reports = q.insight_reports_df(report_type)
if reports.empty:
    st.info("暂时没有报告。至少积累 14 个有效日后，scheduler 会在每天 08:00 自动生成。")
    st.stop()

options = list(range(len(reports)))
selected = st.selectbox(
    "报告周期",
    options,
    format_func=lambda index: (
        f"{reports.iloc[index]['period_start']} — {reports.iloc[index]['period_end']}"
    ),
)
report = reports.iloc[selected]

status_labels = {
    "stable": "状态稳定",
    "attention": "建议关注",
    "insufficient_data": "数据不足",
}
st.subheader(status_labels.get(report["status"], report["status"]))
st.write(report["summary"])

coverage = report["data_coverage"] or {}
st.caption(
    f"数据覆盖：{coverage.get('days_with_data', 0)}/{coverage.get('period_days', 0)} 天 · "
    f"时区：{coverage.get('timezone', 'Asia/Shanghai')}"
)

findings = report["findings"] or []
st.divider()
st.subheader("发现与证据")
if not findings:
    st.caption("该周期没有触发明显偏离个人基线的规则。")
for finding in findings:
    evidence = finding.get("evidence", {})
    with st.container(border=True):
        st.markdown(f"**{finding.get('title', '发现')}**")
        st.write(finding.get("interpretation", ""))
        st.caption(
            f"当前 {evidence.get('current')} {evidence.get('unit', '')}；"
            f"基线 {evidence.get('baseline')} {evidence.get('unit', '')}；"
            f"变化 {evidence.get('delta_percent')}%"
        )

st.subheader("行动建议")
recommendations = report["recommendations"] or []
if not recommendations:
    st.caption("当前没有需要特别调整的事项。")
for item in recommendations:
    st.markdown(f"- {item.get('text', '')}")
