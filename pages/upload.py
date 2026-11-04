"""
Upload Files Page
Multi-format file uploader with automatic format detection, parsing,
sample dataset loader, and in-memory file catalog manager.
"""
import os
import streamlit as st
import pandas as pd

from config import SUPPORTED_INPUT_EXTENSIONS, SAMPLES_DIR
from utils.ui_components import (
    inject_custom_css,
    render_page_header,
    render_metric_card,
    render_active_file_banner,
)
from utils.helpers import format_bytes
from utils.session_manager import SessionManager


def show():
    inject_custom_css()
    SessionManager.init_session()

    render_page_header(
        title="Upload & Ingestion Hub",
        description="Upload multi-format data files or choose from pre-bundled sample datasets for instant profiling.",
        badge="Phase 1",
    )

    # Active File Banner
    render_active_file_banner()

    tab_upload, tab_samples, tab_manage = st.tabs([
        "📤 Upload New Files",
        "🧪 Bundled Test Datasets",
        "📂 Manage In-Memory Files",
    ])

    # TAB 1: UPLOAD NEW FILES
    with tab_upload:
        st.markdown("#### Select or Drop Files")
        st.caption(
            "Supported formats: Excel (.xlsx, .xls), CSV (.csv, .tsv), XML (.xml), JSON (.json), TXT (.txt), ZIP Archives (.zip)"
        )

        uploaded_files = st.file_uploader(
            "Drag and drop files here",
            type=["xlsx", "xls", "csv", "tsv", "xml", "json", "txt", "zip"],
            accept_multiple_files=True,
            help="Files are processed in memory and never overwritten.",
            key="file_uploader_widget",
        )

        if uploaded_files:
            newly_added = 0
            for uploaded in uploaded_files:
                # Check if already uploaded by filename and size
                already_exists = any(
                    f["filename"] == uploaded.name and f["size_bytes"] == uploaded.size
                    for f in st.session_state.files.values()
                )
                if not already_exists:
                    raw_bytes = uploaded.read()
                    fid = SessionManager.add_uploaded_file(uploaded.name, raw_bytes)
                    newly_added += 1

            if newly_added > 0:
                st.success(f"Successfully ingested {newly_added} file(s)! Switching to File Inspector...")
                st.rerun()

        st.markdown("---")
        st.markdown("##### 📌 Ingestion Guarantees & Extensibility")
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**🛡️ Non-Destructive**")
            st.caption("Your original source files remain completely untouched. All transformations run in isolated memory.")
        with c2:
            st.markdown("**🔍 Automatic Sniffing**")
            st.caption("Delimiters, encodings, worksheets, and XML hierarchies are auto-detected without manual configuration.")
        with c3:
            st.markdown("**🧩 Universal Registry**")
            st.caption("Pluggable architecture allows seamless registration of new file formats and schemas at any time.")

    # TAB 2: BUNDLED TEST DATASETS
    with tab_samples:
        st.markdown("#### Test with Bundled Representative Datasets")
        st.caption("Instant 1-click loading of realistic multi-format datasets to test inspection and edge-case handling.")

        s_col1, s_col2 = st.columns(2)

        samples_meta = [
            {
                "file": "sample_sales.xlsx",
                "format": "EXCEL",
                "title": "Corporate Sales Workbook (.xlsx)",
                "desc": "3 distinct worksheets (Orders, Customers, Inventory), mixed column types, dates, and order amounts.",
            },
            {
                "file": "sample_customers.csv",
                "format": "CSV",
                "title": "Customer CRM Records (.csv)",
                "desc": "Realistic data quality challenges: missing balances, duplicate records, mixed date formats, and an outlier.",
            },
            {
                "file": "sample_data.xml",
                "format": "XML",
                "title": "ERP Transaction Document (.xml)",
                "desc": "Hierarchical structure with repeated RECORD elements, nested LINEITEMS, attributes, and header metadata.",
            },
            {
                "file": "sample_inventory.json",
                "format": "JSON",
                "title": "Hardware Catalog (.json)",
                "desc": "Nested catalog with array of items, tags, costs, stock levels, and root export metadata.",
            },
            {
                "file": "sample_log.txt",
                "format": "TXT",
                "title": "System Event Log (.txt)",
                "desc": "Pipe-delimited (|) service transaction logs with timestamps, log levels, and response latencies.",
            },
            {
                "file": "sample_archive.zip",
                "format": "ZIP",
                "title": "Multi-Format Archive (.zip)",
                "desc": "Compressed archive containing all 5 formats inside; tests zip inspection and inner file selection.",
            },
        ]

        for i, s in enumerate(samples_meta):
            target_col = s_col1 if (i % 2 == 0) else s_col2
            with target_col:
                with st.container(border=True):
                    st.markdown(f"**{s['title']}**")
                    st.caption(s["desc"])
                    badge_style = f"badge-{s['format'].lower()}"
                    st.markdown(f"<span class='badge {badge_style}'>{s['format']}</span>", unsafe_allow_html=True)
                    st.write("")

                    sample_file_path = SAMPLES_DIR / s["file"]
                    if sample_file_path.exists():
                        if st.button(f"Load {s['file']}", key=f"btn_load_{s['file']}"):
                            with open(sample_file_path, "rb") as sf:
                                raw_bytes = sf.read()
                                fid = SessionManager.add_uploaded_file(s["file"], raw_bytes)
                                SessionManager.set_active_file(fid)
                            st.success(f"Loaded '{s['file']}' as active dataset!")
                            st.rerun()
                    else:
                        st.error("Sample file not found. Run sample generator.")

    # TAB 3: MANAGE IN-MEMORY FILES
    with tab_manage:
        st.markdown("#### Currently Loaded Datasets")
        files = st.session_state.get("files", {})

        if not files:
            st.info("No files currently in memory.")
        else:
            table_records = []
            for fid, f in files.items():
                is_active = (fid == st.session_state.active_file_id)
                df = f.get("parsed_data", {}).get("active_df")
                rows = len(df) if (df is not None and isinstance(df, pd.DataFrame)) else "N/A"
                cols = len(df.columns) if (df is not None and isinstance(df, pd.DataFrame)) else "N/A"
                table_records.append({
                    "File ID": fid,
                    "File Name": f["filename"],
                    "Format": f["format"].upper(),
                    "Size": format_bytes(f["size_bytes"]),
                    "Rows": rows,
                    "Columns": cols,
                    "Active": "⭐ Active" if is_active else "",
                })

            st.dataframe(pd.DataFrame(table_records), use_container_width=True, hide_index=True)

            m_col1, m_col2, m_col3 = st.columns([2, 2, 2])
            with m_col1:
                # Switch active file
                select_options = {fid: f["filename"] for fid, f in files.items()}
                new_active = st.selectbox(
                    "Select Active File:",
                    options=list(select_options.keys()),
                    format_func=lambda x: select_options[x],
                    index=list(select_options.keys()).index(st.session_state.active_file_id) if st.session_state.active_file_id in select_options else 0,
                    key="manage_select_active",
                )
                if st.button("Set as Active", key="btn_set_active"):
                    SessionManager.set_active_file(new_active)
                    st.success(f"Active file set to: {select_options[new_active]}")
                    st.rerun()

            with m_col2:
                # Delete active file
                del_target = st.selectbox(
                    "Delete File:",
                    options=list(select_options.keys()),
                    format_func=lambda x: select_options[x],
                    key="manage_select_delete",
                )
                if st.button("🗑️ Remove File", key="btn_remove_file"):
                    SessionManager.remove_file(del_target)
                    st.warning("File removed from in-memory session.")
                    st.rerun()

            with m_col3:
                st.write("")
                st.write("")
                if st.button("⚠️ Clear All In-Memory Datasets", type="primary", key="btn_clear_all"):
                    SessionManager.clear_all()
                    st.rerun()


if __name__ == "__main__":
    show()
