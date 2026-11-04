"""
Universal Data Customisation & Automation Studio
Page 9: Validation & Quality Centre (Phase 9)
Live dataset quality auditing, customizable business rule checks, drilldown anomaly inspection,
1-click remediation shortcuts, and multi-sheet Excel diagnostic export.
"""
import io
import streamlit as st
import pandas as pd

from config import SAMPLES_DIR
from utils.ui_components import (
    inject_custom_css,
    render_page_header,
    render_metric_card,
    render_active_file_banner,
)
from utils.session_manager import SessionManager
from core.validation_engine import ValidationEngine, ValidationReport, ValidationFinding
from core.data_cleaning import DataCleaningEngine
from core.transformations import RowOperations


def _init_validation_state():
    if "val_report" not in st.session_state:
        st.session_state.val_report = None


def show():
    inject_custom_css()
    SessionManager.init_session()
    _init_validation_state()

    render_page_header(
        title="Validation & Quality Centre",
        description="Comprehensive dataset auditing, business rule enforcement, anomaly inspection, and multi-sheet diagnostic reporting.",
        badge="Phase 9 Active",
    )

    active_file = render_active_file_banner()
    if not active_file:
        st.warning("⚠️ No active dataset loaded in workspace. Please upload a file or select a sample dataset.")
        c_l1, _ = st.columns([1.5, 3])
        with c_l1:
            if st.button("📊 Load Sample Sales Dataset (.xlsx)", key="val_btn_load_sample"):
                sample_p = SAMPLES_DIR / "sample_sales.xlsx"
                if sample_p.exists():
                    with open(sample_p, "rb") as f:
                        fid = SessionManager.add_uploaded_file("sample_sales.xlsx", f.read())
                        SessionManager.set_active_file(fid)
                        st.rerun()
        return

    working_df = SessionManager.get_active_df()
    if working_df is None or working_df.empty:
        st.warning("The active dataset is currently empty.")
        return

    cols = list(working_df.columns)
    num_cols = [c for c in cols if pd.api.types.is_numeric_dtype(working_df[c])]

    # -------------------------------------------------------------
    # CUSTOM BUSINESS RULE CONFIGURATOR ACCORDION
    # -------------------------------------------------------------
    with st.expander("⚙️ Configure Custom Validation & Quality Rules", expanded=False):
        st.caption("Specify business constraints and field integrity rules to evaluate alongside baseline data health.")
        r_c1, r_c2, r_c3 = st.columns(3)

        with r_c1:
            sel_req_cols = st.multiselect(
                "Mandatory Non-Null Columns:",
                options=cols,
                help="Columns that must exist and cannot contain any empty or null values.",
                key="val_sel_req",
            )
        with r_c2:
            sel_key_cols = st.multiselect(
                "Unique Primary Key Column(s):",
                options=cols,
                help="Columns whose combination must form a 100% unique primary identifier.",
                key="val_sel_keys",
            )
        with r_c3:
            sel_non_neg = st.multiselect(
                "Non-Negative Numerical Columns:",
                options=num_cols,
                help="Numerical columns that must be >= 0.",
                key="val_sel_non_neg",
            )

    # Trigger or auto-run audit
    st.write("")
    btn_run_val, btn_remedy, _ = st.columns([1.8, 1.8, 2.4])

    with btn_run_val:
        run_audit = st.button("▶ Run Full Validation Audit", type="primary", use_container_width=True, key="val_btn_run_audit")

    with btn_remedy:
        auto_fix = st.button("🧹 Auto-Remediate Cleanable Issues", use_container_width=True, key="val_btn_auto_fix")

    if auto_fix:
        with st.spinner("Applying automated quality remediation..."):
            fixed_df = working_df.copy()
            fixes_applied = []

            # 1. Deduplicate
            dup_cnt = int(fixed_df.duplicated().sum())
            if dup_cnt > 0:
                fixed_df, msg_d = RowOperations.remove_duplicates(fixed_df)
                fixes_applied.append(f"Removed {dup_cnt} duplicate rows")

            # 2. Impute nulls with mode or 'N/A'
            null_cols = [c for c in fixed_df.columns if fixed_df[c].isna().sum() > 0]
            if null_cols:
                fixed_df, msg_i = DataCleaningEngine.impute_missing(fixed_df, columns=null_cols, strategy="constant", constant_value="N/A")
                fixes_applied.append(f"Filled nulls in [{', '.join(null_cols)}]")

            if fixes_applied:
                SessionManager.update_working_df(
                    fixed_df,
                    action_name="Auto-Remediation",
                    description="; ".join(fixes_applied),
                )
                st.session_state.val_report = None
                st.toast(f"Remediation complete: {'; '.join(fixes_applied)}", icon="✨")
                st.rerun()
            else:
                st.info("No common auto-cleanable issues (duplicates or nulls) detected.")

    # Re-compute report if triggered or not present
    if run_audit or st.session_state.val_report is None:
        st.session_state.val_report = ValidationEngine.audit_dataset(
            df=working_df,
            dataset_name=active_file.get("filename", "Working Dataset"),
            required_columns=sel_req_cols,
            unique_key_columns=sel_key_cols,
            numeric_non_negative=sel_non_neg,
        )

    report: ValidationReport = st.session_state.val_report

    # -------------------------------------------------------------
    # TOP EXECUTIVE QUALITY KPIS
    # -------------------------------------------------------------
    st.write("")
    k1, k2, k3, k4, k5 = st.columns(5)

    with k1:
        st_color = "#10B981" if report.status == "PASSED" else ("#F59E0B" if report.status == "WARNINGS" else "#EF4444")
        render_metric_card("Status", report.status, col=k1, color=st_color)
    with k2:
        render_metric_card("Health Score", f"{report.health_score} / 100", f"Grade: {report.health_grade}", col=k2, color="#3B82F6")
    with k3:
        render_metric_card("Missing Values", f"{report.missing_cells:,}", f"{report.missing_percentage}% cells", col=k3, color="#8B5CF6")
    with k4:
        render_metric_card("Duplicate Records", f"{report.duplicate_rows:,}", f"{report.duplicate_percentage}% rows", col=k4, color="#EC4899")
    with k5:
        render_metric_card("Anomalies & Outliers", f"{report.outlier_values_count + report.date_format_issues_count:,}", "Date & numeric flags", col=k5, color="#F59E0B")

    st.markdown("---")

    # -------------------------------------------------------------
    # AUTOMATED FINDINGS & QUALITY AUDIT BREAKDOWN
    # -------------------------------------------------------------
    st.markdown(f"### 📋 Audit Findings & Rule Checks ({len(report.findings)} issues)")

    if not report.findings and not report.rule_results:
        st.success("🎉 **All validation checks passed!** Dataset contains 0 duplicate records, 0 missing cells, and adheres to all defined constraints.")
    else:
        # Findings Filter by Severity
        f_c1, f_c2 = st.columns([1.5, 3.5])
        with f_c1:
            sev_filter = st.selectbox("Filter Findings by Severity:", options=["All Severities", "CRITICAL", "WARNING", "INFO"], key="val_sev_filter")

        filtered_findings = [
            f for f in report.findings
            if sev_filter == "All Severities" or f.severity == sev_filter
        ]

        if filtered_findings:
            table_rows = []
            for f in filtered_findings:
                sev_badge = (
                    "🔴 CRITICAL" if f.severity == "CRITICAL"
                    else ("🟡 WARNING" if f.severity == "WARNING" else "🔵 INFO")
                )
                table_rows.append({
                    "Severity": sev_badge,
                    "Category": f.category,
                    "Target Column": f.column,
                    "Issue Description": f.issue,
                    "Affected Count": f.affected_rows_count,
                    "Remediation Recommendation": f.recommendation,
                })
            st.dataframe(pd.DataFrame(table_rows), use_container_width=True, hide_index=True)
        else:
            st.info(f"No findings matching severity: {sev_filter}")

        # Business Rule Results (if any)
        if report.rule_results:
            st.markdown("#### 🛡️ Custom Business Constraint Checks")
            st.dataframe(pd.DataFrame(report.rule_results), use_container_width=True, hide_index=True)

    # -------------------------------------------------------------
    # DRILLDOWN: INSPECT PROBLEMATIC RECORD ROWS
    # -------------------------------------------------------------
    st.markdown("### 🔍 Anomaly Drilldown & Problem Rows")

    dt1, dt2, dt3 = st.tabs(["Null / Missing Rows", "Duplicate Rows", "Numerical Outlier Rows"])

    with dt1:
        null_mask = working_df.isna().any(axis=1)
        if null_mask.sum() > 0:
            st.caption(f"Showing sample of {min(50, int(null_mask.sum()))} row(s) containing missing values:")
            st.dataframe(working_df[null_mask].head(50), use_container_width=True)
        else:
            st.success("Zero rows with missing values found.")

    with dt2:
        try:
            h_df = working_df.apply(lambda c: c.astype(str) if c.dtype == object else c)
            dup_mask = h_df.duplicated(keep=False)
        except Exception:
            dup_mask = pd.Series([False] * len(working_df))

        if dup_mask.sum() > 0:
            st.caption(f"Showing sample of {min(50, int(dup_mask.sum()))} duplicate row instance(s):")
            st.dataframe(working_df[dup_mask].head(50), use_container_width=True)
        else:
            st.success("Zero duplicate records found across all columns.")

    with dt3:
        outlier_cols_found = []
        for c in num_cols:
            s = pd.to_numeric(working_df[c], errors="coerce").dropna()
            if len(s) >= 4:
                q25 = s.quantile(0.25)
                q75 = s.quantile(0.75)
                iqr = q75 - q25
                if iqr > 0:
                    lb = q25 - (1.5 * iqr)
                    ub = q75 + (1.5 * iqr)
                    outliers_s = working_df[(working_df[c] < lb) | (working_df[c] > ub)]
                    if not outliers_s.empty:
                        outlier_cols_found.append((c, lb, ub, len(outliers_s)))

        if outlier_cols_found:
            for c, lb, ub, cnt in outlier_cols_found:
                st.markdown(f"**Column `{c}`:** {cnt} outlier values outside `[{lb:.2f}, {ub:.2f}]`")
                st.dataframe(working_df[(working_df[c] < lb) | (working_df[c] > ub)].head(20), use_container_width=True)
        else:
            st.success("No extreme numerical outliers detected in numeric fields.")

    # -------------------------------------------------------------
    # MULTI-SHEET EXCEL DIAGNOSTIC WORKBOOK EXPORT
    # -------------------------------------------------------------
    st.markdown("---")
    st.markdown("### 📥 Download Diagnostic Quality Audit Workbook")
    st.caption("Generate a 5-sheet OpenXML (.xlsx) audit workbook covering executive metrics, categorized findings, business rule results, transformation logs, and sample invalid records.")

    history = st.session_state.get("change_history", [])
    report_bytes = ValidationEngine.generate_excel_audit_report(
        report=report,
        df=working_df,
        transformation_history=history,
    )

    base_fname = active_file.get("filename", "Dataset").rsplit(".", 1)[0]
    st.download_button(
        label="📊 Download 5-Sheet Quality Audit Workbook (.xlsx)",
        data=report_bytes,
        file_name=f"{base_fname}_Quality_Audit_Report.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        type="primary",
        key="val_btn_dl_excel_audit",
    )


if __name__ == "__main__":
    show()
