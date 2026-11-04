"""
Dashboard Page
Universal Data Customisation & Automation Studio Overview & Active Status
"""
import streamlit as st
import pandas as pd

from config import APP_TITLE, APP_SUBTITLE, APP_VERSION, BASE_DIR
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
        title="Universal Data Studio Dashboard",
        description="Universal multi-format data ingestion, structural inspection, customisation, cleaning, and transformation workspace.",
        badge="v9.0.0 Production Ready",
    )

    # Top Documentation Download Callout
    manual_path = BASE_DIR / "Universal_Data_Studio_User_Manual.pdf"
    if manual_path.exists():
        d_c1, d_c2 = st.columns([3.5, 1.5])
        with d_c1:
            st.info("📖 **Official Documentation Available:** Comprehensive 13-section User Manual & Technical Architecture Guide (PDF).")
        with d_c2:
            with open(manual_path, "rb") as mf:
                pdf_bytes = mf.read()
            st.download_button(
                label="📥 Download Manual (PDF)",
                data=pdf_bytes,
                file_name="Universal_Data_Studio_User_Manual.pdf",
                mime="application/pdf",
                use_container_width=True,
                key="dash_btn_dl_manual",
            )

    # Active File Banner
    active_file = render_active_file_banner()

    # KPI Metrics Row
    files = st.session_state.get("files", {})
    working_df = st.session_state.get("working_df")

    m_col1, m_col2, m_col3, m_col4 = st.columns(4)

    total_files = len(files)
    active_rows = len(working_df) if working_df is not None else 0
    active_cols = len(working_df.columns) if working_df is not None else 0
    health_info = active_file.get("inspection", {}).get("health_score", {}) if active_file else {}
    health_grade = health_info.get("grade", "N/A")
    health_score = health_info.get("score")

    with m_col1:
        render_metric_card("Loaded Datasets", str(total_files), "In-memory workspace", m_col1)
    with m_col2:
        render_metric_card("Active Rows", f"{active_rows:,}", "Current active dataset", m_col2)
    with m_col3:
        render_metric_card("Active Columns", str(active_cols), "Available fields", m_col3)
    with m_col4:
        score_sub = f"{health_score}/100" if health_score is not None else "Awaiting inspection"
        render_metric_card("Data Health Grade", health_grade, score_sub, m_col4)

    st.write("")

    # Two column overview
    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown("### 🚀 Quick Start & Workspace Actions")
        st.markdown(
            """
            This platform is a **general-purpose universal data manipulation platform** designed to ingest,
            profile, clean, transform, match, and automate data across formats without being tied to any single schema.
            """
        )

        q1, q2 = st.columns(2)
        with q1:
            st.markdown(
                """
                <div style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 16px;">
                    <div style="font-size: 1.1rem; font-weight: 600; color: #60A5FA;">📤 1. Ingest Data</div>
                    <p style="font-size: 0.85rem; color: #94A3B8; margin-top: 6px;">
                        Upload Excel, CSV, XML, JSON, TXT, or ZIP files, or explore bundled multi-format test datasets.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with q2:
            st.markdown(
                """
                <div style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 16px;">
                    <div style="font-size: 1.1rem; font-weight: 600; color: #34D399;">🔬 2. Deep Inspection</div>
                    <p style="font-size: 0.85rem; color: #94A3B8; margin-top: 6px;">
                        Review automated data profiling, schema types, missingness, duplicates, date anomalies, and XML hierarchies.
                    </p>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.write("")
        st.markdown("### 📋 Universal Architecture Roadmap")

        roadmap_data = [
            {"Phase": "Phase 1", "Module": "File Upload & Universal Inspection", "Status": "✅ Completed", "Scope": "Excel, CSV, XML, JSON, TXT, ZIP ingestion, schema & anomaly detection"},
            {"Phase": "Phase 2", "Module": "Column & Row Customisation", "Status": "✅ Completed", "Scope": "Rename, add, delete, reorder, merge, split, formulas, row filtering & deduplication"},
            {"Phase": "Phase 3", "Module": "Data Cleaning & Transformation", "Status": "✅ Completed", "Scope": "Missing values, text/date standardisation, outliers, appends, joins, pivot/unpivot"},
            {"Phase": "Phase 4", "Module": "Advanced Record Matching & Updating", "Status": "✅ Completed", "Scope": "Original vs Revised comparison, matching key resolution, side-by-side diffs"},
            {"Phase": "Phase 5", "Module": "XML Studio & File Conversion", "Status": "✅ Completed", "Scope": "Universal XML node editing, Excel-to-XML mapping, multi-format cross conversions"},
            {"Phase": "Phase 6", "Module": "TallyPrime Bulk Voucher Updater", "Status": "✅ Completed", "Scope": "Voucher GUID matching, ledger balancing, preserving non-voucher XML elements"},
            {"Phase": "Phase 7", "Module": "Custom Workflow Builder & Saved Recipes", "Status": "✅ Completed", "Scope": "Build My Workflow sequencing, step previews, workflow JSON save/load, catalog replay"},
            {"Phase": "Phase 8", "Module": "Natural Language Customisation & AI Copilot", "Status": "✅ Completed", "Scope": "AI-assisted instruction parsing, offline heuristic NLP, human confirmation gates"},
            {"Phase": "Phase 9", "Module": "Validation Centre, Multi-Format Export & ZIP Packaging", "Status": "✅ Completed & Active", "Scope": "End-to-end data auditing, 5-sheet Excel error report, 5-format export + ZIP package"},
        ]

        st.dataframe(pd.DataFrame(roadmap_data), use_container_width=True, hide_index=True)

    with col_right:
        st.markdown("### 📦 Loaded Datasets in Memory")
        if files:
            for fid, f in files.items():
                is_active = (fid == st.session_state.active_file_id)
                active_indicator = " ⭐ (Active)" if is_active else ""
                badge_style = f"badge-{f['format'].lower()}"

                # Format-specific detail string
                parsed_meta = f.get('parsed_data', {})
                if f['format'] == 'excel':
                    sheets_count = len(parsed_meta.get('sheets', []))
                    detail_str = f"Size: {format_bytes(f['size_bytes'])} | Sheets: {sheets_count}"
                elif f['format'] == 'zip':
                    inner_count = len(parsed_meta.get('archive_files', []))
                    detail_str = f"Size: {format_bytes(f['size_bytes'])} | Contained Files: {inner_count}"
                elif f['format'] == 'xml':
                    root_elem = parsed_meta.get('root_tag', 'XML')
                    detail_str = f"Size: {format_bytes(f['size_bytes'])} | Root: &lt;{root_elem}&gt;"
                else:
                    df_count = len(parsed_meta.get('active_df', [])) if parsed_meta.get('active_df') is not None else 0
                    detail_str = f"Size: {format_bytes(f['size_bytes'])} | Records: {df_count}"

                st.markdown(
                    f"""
                    <div style="background: rgba(30, 41, 59, 0.4); border-left: 3px solid {'#3B82F6' if is_active else 'rgba(255,255,255,0.2)'}; border-radius: 6px; padding: 10px 14px; margin-bottom: 8px;">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <strong style="color: #F8FAFC; font-size: 0.9rem;">{f['filename']}{active_indicator}</strong>
                            <span class="badge {badge_style}">{f['format'].upper()}</span>
                        </div>
                        <div style="font-size: 0.75rem; color: #94A3B8; margin-top: 4px;">
                            {detail_str}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
        else:
            st.info("No datasets currently uploaded. Switch to **Upload Files** or click below to load demo data.")
            if st.button("✨ Load Sample Sales Excel Dataset", key="dash_load_sample"):
                from config import SAMPLES_DIR
                sample_p = SAMPLES_DIR / "sample_sales.xlsx"
                if sample_p.exists():
                    with open(sample_p, "rb") as sf:
                        SessionManager.add_uploaded_file("sample_sales.xlsx", sf.read())
                    st.success("Sample dataset loaded successfully!")
                    st.rerun()

        st.markdown("### 🛡️ Data Safety Guarantees")
        st.markdown(
            """
            * **Pristine Immutability:** Uploaded files are never modified on disk or overwritten.
            * **Isolated Working Copies:** All operations execute on in-memory deep copies.
            * **Session History:** Every operation is tracked for auditability and step-by-step verification.
            """
        )


if __name__ == "__main__":
    show()
