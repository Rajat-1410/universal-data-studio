"""
Universal Data Customisation & Automation Studio
Page 10: Multi-Format Export Centre & Session Audit History (Phase 9)
Side-by-side original vs. modified comparison, record delta analytics,
chronological transformation audit trail, undo/redo session controls,
and multi-format export (Excel, CSV, XML, JSON, TXT, and all-in-one ZIP Archive).
"""
import io
import json
import zipfile
from datetime import datetime
import streamlit as st
import pandas as pd
import numpy as np

from config import SAMPLES_DIR
from utils.ui_components import (
    inject_custom_css,
    render_page_header,
    render_metric_card,
    render_active_file_banner,
)
from utils.session_manager import SessionManager
from core.validation_engine import ValidationEngine


def show():
    inject_custom_css()
    SessionManager.init_session()

    render_page_header(
        title="Multi-Format Export Centre & Audit History",
        description="Inspect change logs, compare original vs. working datasets, and export validated data into Excel, CSV, XML, JSON, TXT, or an all-in-one ZIP bundle.",
        badge="Phase 9 Active",
    )

    active_file = render_active_file_banner()
    if not active_file:
        st.warning("⚠️ No active dataset selected in workspace. Please upload a file or select a sample dataset.")
        c_l1, _ = st.columns([1.5, 3])
        with c_l1:
            if st.button("📊 Load Sample Sales Dataset (.xlsx)", key="exp_btn_load_sample"):
                sample_p = SAMPLES_DIR / "sample_sales.xlsx"
                if sample_p.exists():
                    with open(sample_p, "rb") as f:
                        fid = SessionManager.add_uploaded_file("sample_sales.xlsx", f.read())
                        SessionManager.set_active_file(fid)
                        st.rerun()
        return

    working_df = SessionManager.get_active_df()
    original_df = SessionManager.get_original_df()
    history = st.session_state.get("change_history", [])

    if working_df is None or working_df.empty:
        st.warning("The current working dataset is empty.")
        return

    # -------------------------------------------------------------
    # TOP COMPARISON METRICS & SESSION UNDO/REDO CONTROLS
    # -------------------------------------------------------------
    orig_rows = len(original_df) if original_df is not None else 0
    work_rows = len(working_df)
    row_delta = work_rows - orig_rows

    orig_cols = set(original_df.columns) if original_df is not None else set()
    work_cols = set(working_df.columns)
    cols_added = len(work_cols - orig_cols)
    cols_removed = len(orig_cols - work_cols)

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        render_metric_card("Original Rows", f"{orig_rows:,}", "Initial baseline copy", m1, color="#64748B")
    with m2:
        render_metric_card("Working Rows", f"{work_rows:,}", "Current staged copy", m2, color="#3B82F6")
    with m3:
        delta_color = "#10B981" if row_delta >= 0 else "#EF4444"
        render_metric_card("Net Row Delta", f"{row_delta:+d} rows", f"Original: {orig_rows:,}", m3, color=delta_color)
    with m4:
        col_delta_str = f"+{cols_added} / -{cols_removed}"
        render_metric_card("Column Changes", col_delta_str, f"Total now: {len(work_cols)}", m4, color="#8B5CF6")
    with m5:
        render_metric_card("Transformation Steps", str(len(history)), "Session operations", m5, color="#10B981")

    # Session Undo/Redo & Reset Toolbar
    st.write("")
    u_col1, u_col2, u_col3, u_col4 = st.columns([1.5, 1.5, 2, 4])
    with u_col1:
        if st.button("↶ Undo Step", disabled=not SessionManager.can_undo(), use_container_width=True, key="exp_btn_undo"):
            succ, msg = SessionManager.undo()
            if succ:
                st.toast(msg, icon="↶")
                st.rerun()
    with u_col2:
        if st.button("↷ Redo Step", disabled=not SessionManager.can_redo(), use_container_width=True, key="exp_btn_redo"):
            succ, msg = SessionManager.redo()
            if succ:
                st.toast(msg, icon="↷")
                st.rerun()
    with u_col3:
        if st.button("🔄 Reset to Baseline", type="secondary", use_container_width=True, key="exp_btn_reset"):
            SessionManager.reset_working_df()
            st.toast("Dataset reverted to original baseline.", icon="🔄")
            st.rerun()
    with u_col4:
        h_idx = st.session_state.get("history_index", 0)
        curr_act = history[h_idx]["action"] if history and 0 <= h_idx < len(history) else "Initial Baseline"
        st.caption(f"**Current State:** Step {h_idx} of {max(0, len(history)-1)} — `{curr_act}`")

    st.markdown("---")

    # -------------------------------------------------------------
    # SIDE-BY-SIDE DATASET COMPARISON & TRANSFORMATION LOG
    # -------------------------------------------------------------
    st.markdown("### ⚖️ Dataset Comparison & Audit Trail")

    cmp_t1, cmp_t2, cmp_t3, cmp_t4 = st.tabs([
        "🚀 Modified Working Dataset (Staged for Export)",
        "📄 Pristine Original Dataset",
        "🔍 Schema & Column Diffs",
        "📜 Chronological Transformation Log",
    ])

    with cmp_t1:
        st.caption(f"Dimensions: **{len(working_df):,} rows × {len(working_df.columns)} columns**")
        st.dataframe(working_df.head(50), use_container_width=True)
        if len(working_df) > 50:
            st.caption(f"Previewing first 50 of {len(working_df):,} records.")

    with cmp_t2:
        if original_df is not None:
            st.caption(f"Dimensions: **{len(original_df):,} rows × {len(original_df.columns)} columns**")
            st.dataframe(original_df.head(50), use_container_width=True)
        else:
            st.info("No original baseline dataset recorded.")

    with cmp_t3:
        schema_diffs = []
        all_cols_union = sorted(list(orig_cols.union(work_cols)))
        for c in all_cols_union:
            in_orig = c in orig_cols
            in_work = c in work_cols
            orig_type = str(original_df[c].dtype) if in_orig and original_df is not None else "N/A"
            work_type = str(working_df[c].dtype) if in_work else "N/A"

            if in_orig and in_work:
                status_c = "Retained" if orig_type == work_type else f"Type Changed ({orig_type} ➔ {work_type})"
            elif in_work and not in_orig:
                status_c = "Added Column (+)"
            else:
                status_c = "Removed Column (-)"

            schema_diffs.append({
                "Column Name": c,
                "Diff Status": status_c,
                "Original Type": orig_type,
                "Working Type": work_type,
            })
        st.dataframe(pd.DataFrame(schema_diffs), use_container_width=True, hide_index=True)

    with cmp_t4:
        if history:
            st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)
        else:
            st.info("No modifications recorded in the current session baseline.")

    st.markdown("---")

    # -------------------------------------------------------------
    # MULTI-FORMAT EXPORT ENGINE
    # -------------------------------------------------------------
    st.markdown("### 💾 Multi-Format Export Centre")
    st.caption("Configure parameters and export your cleaned, validated dataset into any supported enterprise format.")

    base_name = active_file["filename"].rsplit(".", 1)[0]

    f_tab1, f_tab2, f_tab3, f_tab4, f_tab5, f_tab6 = st.tabs([
        "📗 Excel (.xlsx)",
        "📄 CSV (.csv)",
        "🌲 XML (.xml)",
        "🗄️ JSON (.json)",
        "📝 Plain Text (.txt)",
        "📦 Complete ZIP Package",
    ])

    # 1. Excel Export Tab
    with f_tab1:
        st.markdown("#### 📗 Microsoft Excel Export (.xlsx)")
        ex_c1, ex_c2 = st.columns(2)
        with ex_c1:
            sheet_title = st.text_input("Main Data Sheet Name:", value="Cleaned_Data", key="exp_ex_sheet")
            inc_audit_sheet = st.checkbox("Include Session Audit Log as secondary sheet", value=True, key="exp_ex_inc_audit")
        with ex_c2:
            st.caption("Generates a native OpenXML spreadsheet formatted with proper cell types and frozen headers.")

        # Build in-memory Excel file
        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine="openpyxl") as writer:
            working_df.to_excel(writer, sheet_name=sheet_title, index=False)
            if inc_audit_sheet and history:
                pd.DataFrame(history).to_excel(writer, sheet_name="Audit_Log", index=False)

        st.download_button(
            label="📊 Download Excel Spreadsheet (.xlsx)",
            data=excel_buf.getvalue(),
            file_name=f"{base_name}_cleaned.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            key="exp_dl_btn_xlsx",
        )

    # 2. CSV Export Tab
    with f_tab2:
        st.markdown("#### 📄 Comma-Separated Values (.csv)")
        csv_c1, csv_c2 = st.columns(2)
        with csv_c1:
            csv_delim = st.selectbox("Delimiter:", options=[", (Comma)", "; (Semicolon)", "\\t (Tab)", "| (Pipe)"], key="exp_csv_delim")
            delim_char = {", (Comma)": ",", "; (Semicolon)": ";", "\\t (Tab)": "\t", "| (Pipe)": "|"}[csv_delim]
            csv_enc = st.selectbox("Character Encoding:", options=["utf-8", "utf-8-sig (Excel compatible BOM)", "latin1"], key="exp_csv_enc")
        with csv_c2:
            st.caption("Standard RFC 4180 compliant CSV export compatible with databases, statistical suites, and spreadsheets.")

        csv_str = working_df.to_csv(sep=delim_char, index=False, encoding=csv_enc)
        st.download_button(
            label="📄 Download CSV File (.csv)",
            data=csv_str.encode(csv_enc),
            file_name=f"{base_name}_cleaned.csv",
            mime="text/csv",
            type="primary",
            key="exp_dl_btn_csv",
        )

    # 3. XML Export Tab
    with f_tab3:
        st.markdown("#### 🌲 Universal XML Export (.xml)")
        xml_c1, xml_c2 = st.columns(2)
        with xml_c1:
            xml_root = st.text_input("Root Element Tag:", value="DATASET", key="exp_xml_root")
            xml_record = st.text_input("Record Element Tag:", value="ROW", key="exp_xml_row")
        with xml_c2:
            st.caption("Exports clean hierarchical XML with sanitized tag names and proper character entity escaping.")

        clean_root = re.sub(r"[^\w]", "", xml_root) or "DATASET"
        clean_row = re.sub(r"[^\w]", "", xml_record) or "ROW"

        try:
            # Clean column names to make them valid XML element tags
            xml_export_df = working_df.copy()
            xml_export_df.columns = [re.sub(r"[^\w]", "_", str(c)).strip("_") for c in xml_export_df.columns]
            xml_str = xml_export_df.to_xml(index=False, root_name=clean_root, row_name=clean_row)
        except Exception as e:
            xml_str = f"<?xml version='1.0' encoding='utf-8'?>\n<{clean_root}>\n  <!-- XML Export Error: {e} -->\n</{clean_root}>"

        st.download_button(
            label="🌲 Download XML Document (.xml)",
            data=xml_str.encode("utf-8"),
            file_name=f"{base_name}_exported.xml",
            mime="application/xml",
            type="primary",
            key="exp_dl_btn_xml",
        )

    # 4. JSON Export Tab
    with f_tab4:
        st.markdown("#### 🗄️ JavaScript Object Notation (.json)")
        j_c1, j_c2 = st.columns(2)
        with j_c1:
            json_orient = st.selectbox(
                "JSON Data Format:",
                options=["records (Array of Row Objects)", "split (Columns + Data)", "index (Keyed by Row Index)"],
                key="exp_json_orient",
            )
            orient_code = json_orient.split(" ")[0]
            json_indent = st.slider("Indentation (pretty-print):", min_value=0, max_value=4, value=2, key="exp_json_indent")
        with j_c2:
            st.caption("Standard JSON format for web APIs, document databases, and cloud applications.")

        json_str = working_df.to_json(orient=orient_code, indent=json_indent if json_indent > 0 else None)
        st.download_button(
            label="🗄️ Download JSON File (.json)",
            data=json_str.encode("utf-8"),
            file_name=f"{base_name}_cleaned.json",
            mime="application/json",
            type="primary",
            key="exp_dl_btn_json",
        )

    # 5. Plain Text (.txt)
    with f_tab5:
        st.markdown("#### 📝 Plain Delimited Text (.txt)")
        txt_c1, txt_c2 = st.columns(2)
        with txt_c1:
            txt_delim = st.selectbox("Column Separator:", options=["Tab (\\t)", "Pipe (|)", "Comma (,)", "Semicolon (;)"], key="exp_txt_delim")
            t_sep = {"Tab (\\t)": "\t", "Pipe (|)": "|", "Comma (,)": ",", "Semicolon (;)": ";"}[txt_delim]
        with txt_c2:
            st.caption("Raw plain-text delimited format suitable for legacy batch systems, mainframe ingestion, and log parsing.")

        txt_str = working_df.to_csv(sep=t_sep, index=False)
        st.download_button(
            label="📝 Download Text File (.txt)",
            data=txt_str.encode("utf-8"),
            file_name=f"{base_name}_data.txt",
            mime="text/plain",
            type="primary",
            key="exp_dl_btn_txt",
        )

    # 6. Complete ZIP Archive Package
    with f_tab6:
        st.markdown("#### 📦 Executive Export Bundle (.zip)")
        st.caption(
            "Packages your dataset into all 5 formats (Excel, CSV, XML, JSON, TXT) along with the "
            "5-sheet Quality Audit Workbook and session transformation logs into a single compressed ZIP archive."
        )

        # Build in-memory zip bundle
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Cleaned Excel
            zf.writestr(f"{base_name}_cleaned.xlsx", excel_buf.getvalue())
            # 2. Cleaned CSV
            zf.writestr(f"{base_name}_cleaned.csv", csv_str.encode("utf-8"))
            # 3. Cleaned XML
            zf.writestr(f"{base_name}_exported.xml", xml_str.encode("utf-8"))
            # 4. Cleaned JSON
            zf.writestr(f"{base_name}_cleaned.json", json_str.encode("utf-8"))
            # 5. Cleaned TXT
            zf.writestr(f"{base_name}_data.txt", txt_str.encode("utf-8"))

            # 6. Quality Audit Workbook
            val_rep = ValidationEngine.audit_dataset(working_df, dataset_name=base_name)
            audit_bytes = ValidationEngine.generate_excel_audit_report(val_rep, working_df, history)
            zf.writestr(f"{base_name}_quality_audit_report.xlsx", audit_bytes)

            # 7. Transformation Manifest
            manifest = {
                "dataset_name": base_name,
                "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_rows": len(working_df),
                "total_columns": len(working_df.columns),
                "columns": list(working_df.columns),
                "history_steps_count": len(history),
                "history": history,
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2))

        st.download_button(
            label="📦 Download Complete ZIP Package (.zip)",
            data=zip_buffer.getvalue(),
            file_name=f"{base_name}_Complete_Export_Package.zip",
            mime="application/zip",
            type="primary",
            key="exp_dl_btn_zip_bundle",
        )


if __name__ == "__main__":
    show()
