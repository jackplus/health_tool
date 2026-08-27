import streamlit as st

import queries as q
from ingestion import ingest_apple_health, ingest_xiaomi
from style import source_label

st.set_page_config(page_title="Upload", page_icon="⬆️", layout="wide")
st.title("数据上传")

st.markdown(
    """
这里用于历史回填和自动同步失败时的手动恢复：

- **Apple Health**：在 iPhone「健康」App → 头像 → 导出所有健康数据，上传得到的 `export.zip`（不要解压）。
- **小米运动健康**：在 App 内申请个人数据导出，上传收到的 CSV/JSON（或包含它们的 zip）。

重复上传同一份 Apple 全量导出是安全的——已存在的记录会被自动跳过，不会产生重复数据。

日常数据建议由 Health Auto Export 定时发送到
`POST /api/v1/health-auto-export`，不再需要反复上传全量文件。
"""
)

tab_apple, tab_xiaomi = st.tabs(["Apple Health", "小米运动健康"])

with tab_apple:
    apple_file = st.file_uploader("上传 export.zip", type=["zip"], key="apple_uploader")
    if apple_file is not None and st.button("解析并导入", key="apple_import_btn"):
        with st.spinner("正在解析 export.xml，大文件可能需要几分钟…"):
            try:
                summary = ingest_apple_health(apple_file, apple_file.name)
            except Exception as exc:
                st.error(f"导入失败：{exc}")
            else:
                st.success(
                    f"完成：解析 {summary['parsed']:,} 条，新写入 {summary['inserted']:,} 条"
                    f"（其余为重复数据，已自动跳过）。"
                )
                st.json(summary["type_counts"])
                q.available_sources.clear()

with tab_xiaomi:
    xiaomi_file = st.file_uploader(
        "上传 CSV / JSON / zip", type=["csv", "json", "zip"], key="xiaomi_uploader"
    )
    st.caption(
        "小米没有公开文档化的导出格式，解析器会尽力按常见字段名匹配；"
        "如果结果不理想，请把文件样本反馈给维护者以便调整解析规则。"
    )
    if xiaomi_file is not None and st.button("解析并导入", key="xiaomi_import_btn"):
        with st.spinner("正在解析…"):
            try:
                summary = ingest_xiaomi(xiaomi_file, xiaomi_file.name)
            except Exception as exc:
                st.error(f"导入失败：{exc}")
            else:
                if summary["status"] == "failed":
                    st.warning(f"未能识别任何数据。{summary['notes']}")
                else:
                    st.success(
                        f"完成：解析 {summary['parsed']:,} 条，新写入 {summary['inserted']:,} 条。"
                    )
                    if summary["type_counts"]:
                        st.json(summary["type_counts"])
                    if summary["status"] == "partial":
                        st.info(f"部分内容未能解析：{summary['notes']}")
                q.available_sources.clear()

st.divider()
st.subheader("上传历史")
history = q.upload_history_df()
if history.empty:
    st.caption("暂无上传记录")
else:
    display = history.copy()
    display["source"] = display["source"].map(source_label)
    st.dataframe(display, use_container_width=True, hide_index=True)
