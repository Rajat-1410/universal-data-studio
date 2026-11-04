"""
Record Matching & Bulk Updating Studio (Phase 4)
Interactive reconciliation comparing Original and Revised datasets side-by-side.
Identifies identical, modified, new, deleted, and duplicate records.
Executes non-destructive, selective updates with full audit and undo support.
"""
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
from core.record_matching import RecordMatchingEngine
from config import SAMPLES_DIR


def show():
    inject_custom_css()
    SessionManager.init_session()

    render_page_header(
        title="Record Matching & Bulk Updating",
        description="Reconcile Original vs. Revised datasets, inspect side-by-side cell diffs, and perform selective updates.",
        badge="Phase 4 Active",
    )

    render_active_file_banner()

    files = st.session_state.get("files", {})

    # -------------------------------------------------------------
    # STEP 1: SELECT ORIGINAL & REVISED DATASETS
    # -------------------------------------------------------------
    st.markdown("### 1️⃣ Dataset Selection")

    if len(files) < 2:
        st.info("ℹ️ Record matching requires two datasets in memory: an **Original (Baseline)** dataset and a **Revised (Updated)** dataset.")
        load_col1, load_col2 = st.columns(2)
        with load_col1:
            if st.button("📥 Load Sample Reconciliation Datasets (Original & Revised)", use_container_width=True, key="btn_load_match_samples"):
                orig_path = SAMPLES_DIR / "matching_orders_original.xlsx"
                rev_path = SAMPLES_DIR / "matching_orders_revised.xlsx"
                if orig_path.exists() and rev_path.exists():
                    with open(orig_path, "rb") as of:
                        SessionManager.add_uploaded_file("matching_orders_original.xlsx", of.read())
                    with open(rev_path, "rb") as rf:
                        SessionManager.add_uploaded_file("matching_orders_revised.xlsx", rf.read())
                    st.success("Loaded Original and Revised reconciliation sample datasets!")
                    st.rerun()
        with load_col2:
            st.caption("Or upload two files (e.g. your original Excel file and audit revision) in **2. Upload Files**.")
        return

    sel_col1, sel_col2 = st.columns(2)
    file_keys = list(files.keys())

    with sel_col1:
        default_orig = 0
        orig_fid = st.selectbox(
            "Original (Baseline) Dataset:",
            options=file_keys,
            format_func=lambda x: f"{files[x]['filename']} ({files[x]['format'].upper()})",
            index=default_orig,
            key="match_orig_file_select",
        )
        orig_df = files[orig_fid].get("parsed_data", {}).get("active_df")

    with sel_col2:
        default_rev = 1 if len(file_keys) > 1 else 0
        rev_fid = st.selectbox(
            "Revised (Updated) Dataset:",
            options=file_keys,
            format_func=lambda x: f"{files[x]['filename']} ({files[x]['format'].upper()})",
            index=default_rev,
            key="match_rev_file_select",
        )
        rev_df = files[rev_fid].get("parsed_data", {}).get("active_df")

    if orig_df is None or rev_df is None or orig_df.empty or rev_df.empty:
        st.warning("One or both selected datasets contain no tabular rows.")
        return

    st.caption(f"Original: **{files[orig_fid]['filename']}** ({len(orig_df)} rows) | Revised: **{files[rev_fid]['filename']}** ({len(rev_df)} rows)")

    st.markdown("---")

    # -------------------------------------------------------------
    # STEP 2: SELECT MATCHING KEY COLUMNS
    # -------------------------------------------------------------
    st.markdown("### 2️⃣ Matching Key Selection")
    st.caption("Select single or composite columns to establish unique record identity (e.g. ID, Voucher No, Invoice ID).")

    shared_cols = [c for c in orig_df.columns if c in rev_df.columns]
    if not shared_cols:
        st.error("The selected datasets do not share any column names in common.")
        return

    # Default to first column with 'id' or first column
    default_keys = [c for c in shared_cols if "id" in c.lower() or "voucher" in c.lower() or "code" in c.lower()]
    if not default_keys:
        default_keys = [shared_cols[0]]

    key_columns = st.multiselect(
        "Match Records By Key Column(s):",
        options=shared_cols,
        default=default_keys,
        help="Multiple columns create a composite matching key",
        key="match_key_columns_select",
    )

    if not key_columns:
        st.warning("Please select at least one matching key column.")
        return

    # -------------------------------------------------------------
    # STEP 3: RUN COMPARISON
    # -------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 3️⃣ Dataset Comparison & Side-by-Side Diffs")

    try:
        report = RecordMatchingEngine.compare_datasets(orig_df, rev_df, key_columns)
        summary = report["summary"]
        comp_df = report["comparison_df"]
    except Exception as e:
        st.error(f"Comparison Error: {str(e)}")
        return

    # Top KPI Metrics Cards
    k1, k2, k3, k4, k5, k6 = st.columns(6)
    with k1:
        render_metric_card("Original Records", str(summary["total_original"]), "Baseline count", k1)
    with k2:
        render_metric_card("Revised Records", str(summary["total_revised"]), "Revised count", k2)
    with k3:
        render_metric_card("Modified Records", str(summary["modified_count"]), "Values changed", k3)
    with k4:
        render_metric_card("Identical Records", str(summary["unmodified_count"]), "No changes", k4)
    with k5:
        render_metric_card("New Records", str(summary["new_count"]), "To be added", k5)
    with k6:
        render_metric_card("Missing / Deleted", str(summary["missing_count"]), "Omitted in revised", k6)

    # Duplicate Key Warnings
    if summary["orig_duplicate_keys"] > 0 or summary["rev_duplicate_keys"] > 0:
        st.warning(
            f"⚠️ Duplicate Match Alert: Detected {summary['orig_duplicate_keys']} duplicate key occurrences in Original "
            f"and {summary['rev_duplicate_keys']} in Revised. Matching used first occurrence for comparison."
        )

    st.write("")

    # Tabbed Views of Diffs
    diff_tab1, diff_tab2, diff_tab3, diff_tab4 = st.tabs([
        f"📊 All Comparison Rows ({len(comp_df)})",
        f"✏️ Modified Records ({summary['modified_count']})",
        f"✨ New Records ({summary['new_count']})",
        f"🗑️ Missing in Revised ({summary['missing_count']})",
    ])

    with diff_tab1:
        st.markdown("##### Side-by-Side Comparison Grid")
        st.caption("Displays original and revised values side-by-side with match classification.")
        status_filter = st.multiselect(
            "Filter by Match Status:",
            options=["MODIFIED", "NEW_IN_REVISED", "MISSING_IN_REVISED", "IDENTICAL"],
            default=["MODIFIED", "NEW_IN_REVISED", "MISSING_IN_REVISED"],
            key="match_status_filter",
        )
        filtered_comp = comp_df[comp_df["Match_Status"].isin(status_filter)] if status_filter else comp_df
        st.dataframe(filtered_comp, use_container_width=True)

    with diff_tab2:
        st.markdown("##### Modified Records Detailed Changes")
        if report["modified_records"]:
            mod_rows = []
            for mod in report["modified_records"]:
                k = mod["key"]
                for col, chg in mod["changes"].items():
                    mod_rows.append({
                        "Matching Key": k,
                        "Field Changed": col,
                        "Original Value": chg["original"],
                        "Revised Value": chg["revised"],
                    })
            st.dataframe(pd.DataFrame(mod_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No records with modified values detected.")

    with diff_tab3:
        st.markdown("##### New Records to be Inserted")
        new_df = comp_df[comp_df["Match_Status"] == "NEW_IN_REVISED"]
        if not new_df.empty:
            st.dataframe(new_df, use_container_width=True)
        else:
            st.info("No new records found in revised dataset.")

    with diff_tab4:
        st.markdown("##### Records Missing in Revised Dataset")
        missing_df = comp_df[comp_df["Match_Status"] == "MISSING_IN_REVISED"]
        if not missing_df.empty:
            st.dataframe(missing_df, use_container_width=True)
        else:
            st.info("No baseline records were missing in the revised dataset.")

    st.markdown("---")

    # -------------------------------------------------------------
    # STEP 4: RECONCILIATION & UPDATE CONTROLS
    # -------------------------------------------------------------
    st.markdown("### 4️⃣ Selective Reconciliation & Update Execution")
    st.caption("Configure which changes to apply. The original file is never overwritten; a new working dataset is generated.")

    rec_c1, rec_c2, rec_c3 = st.columns(3)

    with rec_c1:
        opt_update_mod = st.checkbox("Update existing modified records", value=True, key="chk_rec_update_mod")
        cols_to_update = summary["shared_columns"]
        if opt_update_mod and cols_to_update:
            selected_update_cols = st.multiselect(
                "Fields to update from revised:",
                options=cols_to_update,
                default=cols_to_update,
                key="rec_selected_cols",
            )
        else:
            selected_update_cols = []

    with rec_c2:
        opt_insert_new = st.checkbox("Insert new records from revised dataset", value=True, key="chk_rec_insert_new")

    with rec_c3:
        opt_remove_del = st.checkbox(
            "Remove records missing in revised dataset",
            value=False,
            help="Unchecked by default to prevent accidental data loss",
            key="chk_rec_remove_del",
        )

    st.write("")
    if st.button("🚀 Apply Reconciliation & Push to Working Dataset", type="primary", key="btn_apply_reconciliation"):
        try:
            reconciled_df, desc, counts = RecordMatchingEngine.reconcile_datasets(
                original_df=orig_df,
                revised_df=rev_df,
                key_columns=key_columns,
                update_modified=opt_update_mod,
                insert_new=opt_insert_new,
                remove_missing=opt_remove_del,
                columns_to_update=selected_update_cols,
            )
            SessionManager.update_working_df(reconciled_df, "Record Reconciliation", desc)
            st.success(desc)
            st.toast("Reconciliation applied! You can view and edit in Data Customisation or Export in Export Centre.", icon="🚀")
            st.rerun()
        except Exception as e:
            st.error(f"Reconciliation failed: {str(e)}")


if __name__ == "__main__":
    show()
