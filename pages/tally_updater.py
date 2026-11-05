"""
TallyPrime Bulk Voucher Updater (Phase 6)
Dedicated enterprise module for high-fidelity Tally XML reconciliation and batch updating.
Preserves GUIDs, GST details, inventory entries, bill allocations, cost centres, bank allocations,
validates double-entry balancing, and generates import-ready Tally XML.
"""
import io
import streamlit as st
import pandas as pd
import numpy as np

from utils.ui_components import (
    inject_custom_css,
    render_page_header,
    render_metric_card,
    render_active_file_banner,
)
from utils.session_manager import SessionManager
from modules.tally import (
    TallyReader,
    VoucherMatcher,
    VoucherUpdater,
    TallyValidator,
    TallyExporter,
)
from config import SAMPLES_DIR


def show():
    inject_custom_css()
    SessionManager.init_session()

    render_page_header(
        title="TallyPrime Bulk Voucher Updater",
        description="Reconcile and batch-update existing TallyPrime vouchers from revised Excel data while strictly preserving GUIDs, GST, inventory, and metadata.",
        badge="Phase 6 Active",
    )

    render_active_file_banner()
    files = st.session_state.get("files", {})

    # Tab navigation for 4-step wizard
    tab_files, tab_match, tab_validate, tab_export = st.tabs([
        "📁 Step 1: Ingest Tally XML & Revised Excel",
        "🔍 Step 2: Voucher Reconciliation & Diff",
        "⚖️ Step 3: Accounting Integrity & Validation",
        "🚀 Step 4: Generate Import-Ready Tally XML",
    ])

    # =============================================================
    # STEP 1: INGEST FILES
    # =============================================================
    with tab_files:
        st.markdown("### 1️⃣ Source Data Ingestion")
        st.caption("Upload your original Tally XML export along with the revised Excel audit/update sheet.")

        f_c1, f_c2 = st.columns(2)

        # File 1: Tally XML
        with f_c1:
            st.markdown("##### 📄 1. Original Tally XML Export")
            xml_candidates = {fid: f for fid, f in files.items() if f["format"] == "xml"}

            selected_xml_fid = None
            if xml_candidates:
                selected_xml_fid = st.selectbox(
                    "Select Tally XML from Studio Session:",
                    options=list(xml_candidates.keys()),
                    format_func=lambda x: f"{xml_candidates[x]['filename']} ({xml_candidates[x]['size_bytes']} bytes)",
                    key="tally_xml_select",
                )

            uploaded_xml = st.file_uploader(
                "Or Upload Tally XML file (.xml):",
                type=["xml"],
                key="tally_xml_uploader",
            )

            if st.button("📥 Load Sample Tally XML (tally_vouchers_original.xml)", key="btn_load_sample_tally_xml"):
                sample_xml_p = SAMPLES_DIR / "tally_vouchers_original.xml"
                if sample_xml_p.exists():
                    with open(sample_xml_p, "rb") as f:
                        fid = SessionManager.add_uploaded_file("tally_vouchers_original.xml", f.read())
                    st.success("Loaded sample Tally XML!")
                    st.rerun()

        # File 2: Revised Excel
        with f_c2:
            st.markdown("##### 📊 2. Revised Excel Spreadsheet")
            tabular_candidates = {fid: f for fid, f in files.items() if f["format"] in ["excel", "csv"]}

            selected_excel_fid = None
            if tabular_candidates:
                selected_excel_fid = st.selectbox(
                    "Select Revised Excel from Studio Session:",
                    options=list(tabular_candidates.keys()),
                    format_func=lambda x: f"{tabular_candidates[x]['filename']} ({tabular_candidates[x]['size_bytes']} bytes)",
                    key="tally_excel_select",
                )

            uploaded_excel = st.file_uploader(
                "Or Upload Revised Excel/CSV file (.xlsx, .csv):",
                type=["xlsx", "xls", "csv"],
                key="tally_excel_uploader",
            )

            if st.button("📥 Load Sample Revised Excel (tally_vouchers_revised.xlsx)", key="btn_load_sample_revised_excel"):
                sample_excel_p = SAMPLES_DIR / "tally_vouchers_revised.xlsx"
                if sample_excel_p.exists():
                    with open(sample_excel_p, "rb") as f:
                        fid = SessionManager.add_uploaded_file("tally_vouchers_revised.xlsx", f.read())
                    st.success("Loaded sample revised Excel!")
                    st.rerun()

        # Resolve XML Content
        raw_xml_bytes = None
        xml_name = ""
        if uploaded_xml:
            raw_xml_bytes = uploaded_xml.read()
            xml_name = uploaded_xml.name
        elif selected_xml_fid and selected_xml_fid in files:
            raw_xml_bytes = files[selected_xml_fid]["raw_bytes"]
            xml_name = files[selected_xml_fid]["filename"]

        # Resolve Excel Content
        revised_df = None
        excel_name = ""
        if uploaded_excel:
            try:
                if uploaded_excel.name.endswith(".csv"):
                    revised_df = pd.read_csv(uploaded_excel)
                else:
                    revised_df = pd.read_excel(uploaded_excel)
                excel_name = uploaded_excel.name
            except Exception as e:
                st.error(f"Error parsing uploaded Excel file: {str(e)}")
        elif selected_excel_fid and selected_excel_fid in files:
            f_entry = files[selected_excel_fid]
            excel_name = f_entry["filename"]
            parsed_meta = f_entry.get("parsed_data", {})
            if "active_df" in parsed_meta and parsed_meta["active_df"] is not None:
                revised_df = parsed_meta["active_df"]
            else:
                try:
                    revised_df = pd.read_excel(io.BytesIO(f_entry["raw_bytes"]))
                except Exception:
                    revised_df = pd.read_csv(io.BytesIO(f_entry["raw_bytes"]))

        st.markdown("---")

        # Parse and display overview if XML is available
        if raw_xml_bytes:
            try:
                parsed_tally = TallyReader.parse_tally_xml(raw_xml_bytes)
                st.session_state["parsed_tally"] = parsed_tally

                st.markdown("#### 🏢 Tally XML Metadata Overview")
                m1, m2, m3, m4 = st.columns(4)
                render_metric_card("Company", parsed_tally["company_name"], "Tally target", col=m1, color="#60A5FA")
                render_metric_card("Total Vouchers", str(parsed_tally["total_vouchers"]), "Voucher count", col=m2, color="#34D399")
                render_metric_card("Ledger Rows", str(parsed_tally["summary"]["total_ledger_rows"]), "Line items", col=m3, color="#F59E0B")
                render_metric_card("GUID Verified", str(parsed_tally["summary"]["has_guids"]), "Unique IDs", col=m4, color="#818CF8")

                with st.expander("👁️ View Original Tally Vouchers & Ledgers Table", expanded=False):
                    st.dataframe(parsed_tally["vouchers_df"], use_container_width=True)

            except Exception as pe:
                st.error(f"Failed to parse Tally XML: {str(pe)}")

        if revised_df is not None and not revised_df.empty:
            st.session_state["tally_revised_df"] = revised_df
            with st.expander(f"👁️ View Revised Excel Sheet ({excel_name})", expanded=False):
                st.dataframe(revised_df, use_container_width=True)

    # =============================================================
    # STEP 2: RECONCILIATION & MATCHING
    # =============================================================
    with tab_match:
        st.markdown("### 2️⃣ Voucher Reconciliation & Diff Inspection")

        parsed_tally = st.session_state.get("parsed_tally")
        revised_df = st.session_state.get("tally_revised_df")

        if not parsed_tally or revised_df is None or revised_df.empty:
            st.warning("⚠️ Please provide both a Tally XML export and a Revised Excel sheet in **Step 1** to proceed.")
        else:
            m_c1, m_c2 = st.columns(2)
            with m_c1:
                match_strategy = st.selectbox(
                    "Matching Key Strategy:",
                    ["Auto", "GUID", "VoucherNumber", "VoucherNumber + Date", "VoucherType + Date", "Date + Ledger"],
                    help="GUID is the global unique identifier generated by Tally. You can also match by VoucherNumber, VoucherType + Date, or Date + Ledger.",
                    key="tally_match_strat",
                )
            with m_c2:
                st.caption("Auto-detected columns in revised Excel:")
                st.text(f"Available Columns: {', '.join(list(revised_df.columns))}")

            if st.button("⚡ Execute Voucher Reconciliation", type="primary", key="btn_run_tally_match"):
                try:
                    match_res = VoucherMatcher.match_vouchers(
                        tally_vouchers=parsed_tally["vouchers"],
                        revised_df=revised_df,
                        match_by=match_strategy,
                    )
                    st.session_state["tally_match_res"] = match_res
                    st.success("Voucher reconciliation completed successfully!")
                except Exception as me:
                    st.error(f"Matching error: {str(me)}")

            # Display Reconciliation Metrics if completed
            match_res = st.session_state.get("tally_match_res")
            if match_res:
                stats = match_res["stats"]

                st.markdown("##### 📊 Reconciliation Summary")
                k1, k2, k3, k4 = st.columns(4)
                render_metric_card("Matched Vouchers", str(stats["matched_exact"]), "Linked vouchers", col=k1, color="#34D399")
                render_metric_card("Modified Amounts", str(stats["modified"]), "Vouchers to alter", col=k2, color="#F59E0B")
                render_metric_card("Identical / Intact", str(stats["identical"]), "No diffs", col=k3, color="#60A5FA")
                render_metric_card("Unmatched Revised", str(stats["unmatched_revised"]), "Not in Tally XML", col=k4, color="#94A3B8")

                # Safety alerts
                if stats["duplicate_tally_matches"] > 0:
                    st.error(
                        f"🚨 **Safety Stop:** {stats['duplicate_tally_matches']} duplicate key conflicts found in Tally XML! "
                        "To prevent ambiguous overwrites, switch Match Strategy to **GUID**."
                    )
                if stats["missing_ledgers"] > 0:
                    st.warning(
                        f"⚠️ **Notice:** {stats['missing_ledgers']} revised row(s) reference ledgers not found in the original voucher."
                    )

                st.markdown("##### 📋 Side-by-Side Reconciliation Table")
                comp_df = match_res["comparison_df"]

                # Quick status filter
                status_opts = ["All"] + list(comp_df["Status"].unique())
                filter_status = st.selectbox("Filter by Status:", options=status_opts, key="tally_comp_filter")

                filtered_comp = comp_df if filter_status == "All" else comp_df[comp_df["Status"] == filter_status]
                st.dataframe(filtered_comp, use_container_width=True)

    # =============================================================
    # STEP 3: ACCOUNTING INTEGRITY & VALIDATION
    # =============================================================
    with tab_validate:
        st.markdown("### 3️⃣ Accounting Integrity & Double-Entry Balancing")
        st.caption("Verifies that Total Debit equals Total Credit for every voucher before XML generation.")

        match_res = st.session_state.get("tally_match_res")
        if not match_res:
            st.info("Please execute voucher reconciliation in **Step 2** first.")
        else:
            val_res = TallyValidator.validate_reconciliation(match_res)
            st.session_state["tally_val_res"] = val_res

            v_stats = val_res["stats"]
            b1, b2, b3 = st.columns(3)
            render_metric_card("Vouchers Verified", str(v_stats["total_vouchers_checked"]), "Reconciled vouchers", col=b1, color="#60A5FA")
            render_metric_card("Balanced (Debit==Credit)", str(v_stats["balanced_count"]), "100% compliant", col=b2, color="#34D399")
            render_metric_card("Imbalance / Errors", str(v_stats["error_count"]), "Blocking errors", col=b3, color="#EF4444" if v_stats["error_count"] > 0 else "#34D399")

            if val_res["is_valid"]:
                st.success("✅ **Double-Entry Integrity Confirmed:** All matched vouchers are perfectly balanced. Safe to generate updated Tally XML.")
            else:
                st.error("❌ **Accounting Discrepancies Detected:**")
                for err in val_res["errors"]:
                    st.markdown(f"- 🔴 {err}")

            st.markdown("##### 📑 Voucher Accounting Balance Breakdown")
            st.dataframe(val_res["balance_df"], use_container_width=True)

    # =============================================================
    # STEP 4: GENERATE UPDATED TALLY XML
    # =============================================================
    with tab_export:
        st.markdown("### 4️⃣ Generate Import-Ready Tally XML & Audit Report")

        parsed_tally = st.session_state.get("parsed_tally")
        match_res = st.session_state.get("tally_match_res")
        val_res = st.session_state.get("tally_val_res")

        if not parsed_tally or not match_res or not val_res:
            st.info("Please complete **Step 1**, **Step 2**, and **Step 3** before exporting.")
        else:
            if not val_res["can_export"]:
                st.error("⛔ **Export Blocked:** Cannot export Tally XML while accounting imbalances or duplicate matches exist. Please resolve validation errors.")
            else:
                exp_c1, exp_c2 = st.columns([3, 1])
                with exp_c1:
                    st.markdown(
                        """
                        * **Identity Preservation:** Original `<GUID>`, `<REMOTEID>`, `<VCHKEY>`, `<MASTERID>` are strictly preserved.
                        * **Non-Voucher Protection:** GST details, inventory items, cost centres, bank allocations, and UDFs remain 100% intact.
                        * **Import Engine Action:** Modified vouchers will be stamped with `ACTION="Alter"` so TallyPrime updates existing records cleanly.
                        """
                    )
                with exp_c2:
                    set_alter = st.checkbox("Set ACTION='Alter'", value=True, help="Tells Tally XML import engine to alter existing vouchers.", key="chk_set_alter")

                st.write("")

                if st.button("🚀 Apply Updates & Generate Tally XML", type="primary", key="btn_apply_tally_updates"):
                    try:
                        updater_res = VoucherUpdater.apply_updates(parsed_tally, match_res, set_alter_action=set_alter)
                        xml_export = TallyExporter.export_tally_xml(updater_res["updated_xml_str"])
                        audit_excel_bytes = TallyExporter.export_audit_report(
                            company_name=parsed_tally["company_name"],
                            matching_result=match_res,
                            validation_result=val_res,
                            updater_result=updater_res,
                        )

                        st.session_state["tally_updater_res"] = updater_res
                        st.session_state["tally_xml_export"] = xml_export
                        st.session_state["tally_audit_excel_bytes"] = audit_excel_bytes

                        st.success(
                            f"Successfully updated {updater_res['stats']['vouchers_updated']} voucher(s) and "
                            f"{updater_res['stats']['ledgers_updated']} ledger amount(s) in-place!"
                        )

                    except Exception as ue:
                        st.error(f"Error updating XML: {str(ue)}")

                # Render download and session load buttons
                xml_export = st.session_state.get("tally_xml_export")
                audit_bytes = st.session_state.get("tally_audit_excel_bytes")

                if xml_export and audit_bytes:
                    st.markdown("##### 💾 Download Import-Ready Files")
                    d_col1, d_col2, d_col3 = st.columns(3)

                    with d_col1:
                        st.download_button(
                            label="💾 Download Updated Tally XML",
                            data=xml_export["xml_bytes"],
                            file_name=xml_export["filename"],
                            mime="application/xml",
                            key="btn_dl_tally_xml",
                        )

                    with d_col2:
                        st.download_button(
                            label="📊 Download Excel Audit Report",
                            data=audit_bytes,
                            file_name="tally_reconciliation_audit.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            key="btn_dl_tally_audit",
                        )

                    with d_col3:
                        if st.button("📥 Save into Studio Memory", key="btn_save_tally_to_session"):
                            SessionManager.add_uploaded_file(xml_export["filename"], xml_export["xml_bytes"])
                            st.success(f"Added '{xml_export['filename']}' to Studio memory as active file!")
                            st.rerun()

                    updater_res = st.session_state.get("tally_updater_res")
                    if updater_res and updater_res.get("audit_log"):
                        with st.expander("📝 View Detailed Ledger Modification Audit Log", expanded=True):
                            st.dataframe(pd.DataFrame(updater_res["audit_log"]), use_container_width=True)

                    with st.expander("📄 View Generated Tally XML Document Snippet", expanded=False):
                        st.code(xml_export["xml_str"][:6000], language="xml")


if __name__ == "__main__":
    show()
