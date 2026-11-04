"""
Universal File Inspector Page
Performs automated multi-format profiling, schema inference, data health scoring,
anomaly detection (dates, duplicates, outliers, missingness), and XML/JSON structural exploration.
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
from utils.helpers import format_bytes
from utils.session_manager import SessionManager


def show():
    inject_custom_css()
    SessionManager.init_session()

    render_page_header(
        title="Universal File Inspector",
        description="Comprehensive automated schema profiling, data health scoring, anomaly diagnosis, and structural tree inspection.",
        badge="Phase 1",
    )

    # Active File Banner
    active_file = render_active_file_banner()
    if not active_file:
        st.warning("Please upload a file or load a bundled sample in the **Upload Files** page.")
        return

    df = st.session_state.get("working_df")
    inspection = active_file.get("inspection")
    fmt = active_file.get("format", "unknown")
    parsed = active_file.get("parsed_data", {})

    # Top KPI Metrics Row
    kpi_col1, kpi_col2, kpi_col3, kpi_col4, kpi_col5 = st.columns(5)

    rows_val = str(len(df)) if df is not None else "0"
    cols_val = str(len(df.columns)) if df is not None else "0"
    mem_val = format_bytes(inspection.get("memory_usage_bytes", 0)) if inspection else "N/A"
    missing_val = f"{inspection.get('missing_percentage', 0.0)}%" if inspection else "0%"
    dup_val = f"{inspection.get('duplicate_rows', 0)}" if inspection else "0"

    with kpi_col1:
        render_metric_card("Total Rows", rows_val, "Dataset length", kpi_col1)
    with kpi_col2:
        render_metric_card("Total Columns", cols_val, "Dataset width", kpi_col2)
    with kpi_col3:
        render_metric_card("Memory Footprint", mem_val, "In-RAM footprint", kpi_col3)
    with kpi_col4:
        render_metric_card("Missing Cells", missing_val, f"{inspection.get('total_missing_cells', 0):,} cells" if inspection else "", kpi_col4)
    with kpi_col5:
        render_metric_card("Duplicate Rows", dup_val, f"{inspection.get('duplicate_percentage', 0.0)}% duplicate" if inspection else "", kpi_col5)

    st.write("")

    # Tab navigation for inspection
    tab_overview, tab_schema, tab_preview, tab_anomalies, tab_format_specific = st.tabs([
        "📊 Overview & Health",
        "📋 Column Profile & Schema",
        "🔍 Interactive Preview",
        "⚠️ Quality & Anomalies",
        f"🌲 Format Deep Dive ({fmt.upper()})",
    ])

    # -------------------------------------------------------------
    # TAB 1: OVERVIEW & HEALTH
    # -------------------------------------------------------------
    with tab_overview:
        st.markdown("#### Dataset Diagnostics & Health Assessment")
        health = inspection.get("health_score", {}) if inspection else {}

        h_col1, h_col2 = st.columns([1, 2])
        with h_col1:
            with st.container(border=True):
                st.markdown("**Data Health Index**")
                score = health.get("score", 100)
                grade = health.get("grade", "A")
                status = health.get("status", "Good")
                color = health.get("color", "#10B981")

                st.markdown(
                    f"""
                    <div style="text-align: center; padding: 15px 0;">
                        <div style="font-size: 3rem; font-weight: 800; color: {color};">{grade}</div>
                        <div style="font-size: 1.2rem; font-weight: 600; color: #F8FAFC;">{score} / 100</div>
                        <div style="font-size: 0.85rem; color: #94A3B8; margin-top: 4px;">{status}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        with h_col2:
            with st.container(border=True):
                st.markdown("**Health Breakdown & Diagnostics**")
                penalties = health.get("penalties", [])
                if not penalties:
                    st.success("🎉 No significant data quality issues detected! The dataset is clean and consistent.")
                else:
                    for p in penalties:
                        st.warning(f"⚠️ {p}")

                st.caption(
                    f"Format: **{active_file['format_info']['display_name']}** | Encoding: **{active_file['format_info'].get('encoding', 'utf-8')}**"
                )

        st.markdown("##### Column Types Summary")
        if inspection:
            t_col1, t_col2, t_col3, t_col4 = st.columns(4)
            with t_col1:
                st.info(f"🔢 **Numeric:** {len(inspection.get('numeric_columns', []))}")
                if inspection.get("numeric_columns"):
                    st.caption(", ".join(inspection["numeric_columns"][:5]))
            with t_col2:
                st.info(f"🔤 **Categorical/Text:** {len(inspection.get('categorical_columns', []))}")
                if inspection.get("categorical_columns"):
                    st.caption(", ".join(inspection["categorical_columns"][:5]))
            with t_col3:
                st.info(f"📅 **Datetime:** {len(inspection.get('datetime_columns', []))}")
                if inspection.get("datetime_columns"):
                    st.caption(", ".join(inspection["datetime_columns"][:5]))
            with t_col4:
                st.info(f"🔘 **Boolean:** {len(inspection.get('boolean_columns', []))}")
                if inspection.get("boolean_columns"):
                    st.caption(", ".join(inspection["boolean_columns"][:5]))

    # -------------------------------------------------------------
    # TAB 2: COLUMN PROFILE & SCHEMA
    # -------------------------------------------------------------
    with tab_schema:
        st.markdown("#### Column Profile & Inferred Schema")
        st.caption("Detailed breakdown of inferred types, missingness, uniqueness, and statistical boundaries.")

        if inspection and inspection.get("column_profiles"):
            profiles = inspection["column_profiles"]
            profile_table = []
            for p in profiles:
                profile_table.append({
                    "Column Name": p["name"],
                    "Inferred Type": p["dtype"],
                    "Missing Count": p["missing_count"],
                    "Missing %": f"{p['missing_pct']}%",
                    "Unique Values": p["unique_count"],
                    "Sample Distinct": ", ".join(map(str, p["sample_values"][:3])),
                    "Numeric?": "Yes" if p["is_numeric"] else "No",
                    "Outliers": f"{p['outliers']['outlier_count']} ({p['outliers']['outlier_percentage']}%)" if p.get("outliers") else "N/A",
                })

            st.dataframe(pd.DataFrame(profile_table), use_container_width=True, hide_index=True)

            # Detailed column inspection accordion
            st.markdown("##### 🔬 Individual Column Deep Dive")
            selected_col_inspect = st.selectbox("Select column to inspect stats:", options=[p["name"] for p in profiles], key="inspect_col_select")
            col_data = next((p for p in profiles if p["name"] == selected_col_inspect), None)

            if col_data:
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.markdown("**Basic Metrics**")
                    st.write(f"- Data Type: `{col_data['dtype']}`")
                    st.write(f"- Missing: `{col_data['missing_count']} ({col_data['missing_pct']}%)`")
                    st.write(f"- Unique Count: `{col_data['unique_count']}`")

                with c2:
                    st.markdown("**Distribution / Stats**")
                    if col_data.get("numeric_stats"):
                        stats = col_data["numeric_stats"]
                        st.write(f"- Min: `{stats['min']}` | Max: `{stats['max']}`")
                        st.write(f"- Mean: `{stats['mean']}` | Median: `{stats['median']}`")
                        st.write(f"- Std Deviation: `{stats['std']}`")
                    else:
                        st.caption("Non-numeric column: summary statistics not applicable.")

                with c3:
                    st.markdown("**Quality Flags**")
                    if col_data.get("outliers"):
                        out = col_data["outliers"]
                        st.write(f"- IQR Outliers: `{out['outlier_count']} ({out['outlier_percentage']}%)`")
                        st.write(f"- Lower Bound: `{out['lower_bound']}`")
                        st.write(f"- Upper Bound: `{out['upper_bound']}`")
                    if col_data.get("date_diagnostics"):
                        dd = col_data["date_diagnostics"]
                        st.write(f"- Date Column: `Yes`")
                        st.write(f"- Inconsistent Formats: `{'⚠️ Yes' if dd['is_inconsistent'] else '✅ Consistent'}`")
                        st.write(f"- Patterns: `{list(dd['detected_patterns'].keys())}`")
        else:
            st.info("No column schema profile available for this format or empty dataset.")

    # -------------------------------------------------------------
    # TAB 3: INTERACTIVE PREVIEW
    # -------------------------------------------------------------
    with tab_preview:
        st.markdown("#### Interactive Data Preview")
        if df is None or df.empty:
            st.info("No tabular data available for preview.")
        else:
            p_ctrl1, p_ctrl2, p_ctrl3 = st.columns([2, 2, 2])
            with p_ctrl1:
                preview_mode = st.radio("Preview Mode:", ["First N Rows", "Last N Rows", "Random Sample", "All Records"], horizontal=True, key="prev_mode_rad")
            with p_ctrl2:
                row_limit = st.slider("Number of Rows:", min_value=5, max_value=min(1000, len(df)), value=min(25, len(df)), step=5, key="prev_row_slider")
            with p_ctrl3:
                search_term = st.text_input("🔍 Quick Search / Filter Rows:", placeholder="Type to search...", key="prev_search_input")

            # Slice data
            if preview_mode == "First N Rows":
                slice_df = df.head(row_limit)
            elif preview_mode == "Last N Rows":
                slice_df = df.tail(row_limit)
            elif preview_mode == "Random Sample":
                slice_df = df.sample(min(row_limit, len(df)), random_state=42)
            else:
                slice_df = df

            # Apply search filter
            if search_term.strip():
                mask = slice_df.astype(str).apply(lambda row: row.str.contains(search_term, case=False).any(), axis=1)
                slice_df = slice_df[mask]

            # Column filter
            all_cols = list(df.columns)
            selected_cols = st.multiselect("Display Columns:", options=all_cols, default=all_cols, key="prev_col_multiselect")

            if selected_cols:
                st.dataframe(slice_df[selected_cols], use_container_width=True)
            else:
                st.warning("Please select at least one column to display.")

    # -------------------------------------------------------------
    # TAB 4: QUALITY & ANOMALIES
    # -------------------------------------------------------------
    with tab_anomalies:
        st.markdown("#### Data Quality & Anomaly Diagnostics")

        anom_col1, anom_col2 = st.columns(2)

        with anom_col1:
            with st.container(border=True):
                st.markdown("##### 👥 Duplicate Records")
                dup_count = inspection.get("duplicate_rows", 0) if inspection else 0
                if dup_count == 0:
                    st.success("✅ No exact duplicate rows found in dataset.")
                else:
                    st.warning(f"⚠️ Detected **{dup_count}** duplicate record(s) ({inspection.get('duplicate_percentage')}%).")
                    if df is not None:
                        dup_mask = df.duplicated(keep=False)
                        dup_sample = df[dup_mask].head(20)
                        st.markdown("**Sample Duplicate Rows:**")
                        st.dataframe(dup_sample, use_container_width=True)

        with anom_col2:
            with st.container(border=True):
                st.markdown("##### 📅 Date Format Inconsistencies")
                date_issues = inspection.get("date_inconsistencies", {}) if inspection else {}
                if not date_issues:
                    st.success("✅ No mixed or conflicting date formats detected.")
                else:
                    st.warning(f"⚠️ Found mixed date formats across **{len(date_issues)}** column(s).")
                    for col_name, diag in date_issues.items():
                        st.markdown(f"**Column: `{col_name}`**")
                        st.caption(f"Detected conflicting patterns: {diag['detected_patterns']}")

        st.markdown("##### 🧩 Missing Value Analysis by Column")
        if df is not None:
            missing_series = df.isna().sum()
            missing_cols = missing_series[missing_series > 0]
            if missing_cols.empty:
                st.success("✅ No missing (null) values in any column.")
            else:
                miss_df = pd.DataFrame({
                    "Column": missing_cols.index,
                    "Missing Count": missing_cols.values,
                    "Missing %": [round((c / len(df)) * 100, 2) for c in missing_cols.values],
                }).sort_values("Missing Count", ascending=False)
                st.dataframe(miss_df, use_container_width=True, hide_index=True)

    # -------------------------------------------------------------
    # TAB 5: FORMAT SPECIFIC DEEP DIVE
    # -------------------------------------------------------------
    with tab_format_specific:
        st.markdown(f"#### Format Deep Dive: {fmt.upper()}")

        if fmt == "excel":
            st.markdown("##### 📑 Worksheets & Tables")
            sheets = parsed.get("sheets", [])
            st.write(f"Detected **{len(sheets)}** worksheet(s): `{', '.join(sheets)}`")

            sheets_summary = parsed.get("sheets_summary", {})
            if sheets_summary:
                sheet_rows = []
                for s_name, s_info in sheets_summary.items():
                    sheet_rows.append({
                        "Worksheet Name": s_name,
                        "Column Count": s_info.get("col_count", 0),
                        "Preview Columns": ", ".join(s_info.get("preview_cols", [])[:5]),
                    })
                st.dataframe(pd.DataFrame(sheet_rows), use_container_width=True, hide_index=True)

        elif fmt == "xml":
            st.markdown("##### 🌲 XML Hierarchy & Structural Anatomy")
            struct = parsed.get("xml_structure", {})
            if struct:
                x1, x2, x3 = st.columns(3)
                with x1:
                    render_metric_card("Root Element", struct.get("root_tag", "UNKNOWN"), "Document root", x1)
                with x2:
                    render_metric_card("Tree Depth", str(struct.get("max_tree_depth", 0)), "Nesting levels", x2)
                with x3:
                    render_metric_card("Unique Tags", str(struct.get("unique_tags_count", 0)), "Total distinct tags", x3)

                st.write("")
                st.markdown("##### Repeated Elements (Candidate Record Sets)")
                repeated = struct.get("repeated_elements", [])
                if repeated:
                    st.dataframe(pd.DataFrame(repeated), use_container_width=True, hide_index=True)
                else:
                    st.info("No repeated elements detected in XML.")

                st.markdown("##### Raw XML Preview")
                raw_preview = parsed.get("raw_text_preview", "")
                st.code(raw_preview, language="xml")

        elif fmt == "json":
            st.markdown("##### 🗄️ JSON Document Structure")
            st.write(f"Structure Type: `{parsed.get('structure_type')}`")
            st.write(f"Root Keys: `{parsed.get('keys_at_root')}`")

            st.markdown("##### Raw JSON Preview")
            st.code(parsed.get("raw_text_preview", ""), language="json")

        elif fmt == "txt":
            st.markdown("##### 📄 Text & Delimiter Sniffing")
            st.write(f"Detected Delimiter: `{parsed.get('detected_delimiter')}`")
            st.write(f"Total Lines: `{parsed.get('line_count')}`")
            st.write(f"Encoding: `{parsed.get('encoding_used')}`")

            st.markdown("##### Raw Text Snippet")
            st.code(parsed.get("raw_text_preview", ""))

        elif fmt == "zip":
            st.markdown("##### 🗜️ Contained Files in Archive")
            archive_files = parsed.get("archive_files", [])
            if archive_files:
                st.dataframe(pd.DataFrame(archive_files), use_container_width=True, hide_index=True)
                supported = parsed.get("supported_files", [])
                if supported:
                    selected_inner = st.selectbox("Inspect Contained File:", options=supported, key="inspect_zip_inner_sel")
                    if st.button("Load and Inspect Inner File", key="btn_load_zip_inner"):
                        reader = FileReaderRegistry.get_reader(active_file["filename"], active_file["raw_bytes"])
                        new_parsed = reader.read(active_file["filename"], active_file["raw_bytes"], selected_file=selected_inner)
                        active_file["parsed_data"] = new_parsed
                        inner_df = new_parsed.get("active_df")
                        if inner_df is not None:
                            st.session_state.working_df = inner_df.copy(deep=True)
                            st.session_state.original_df = inner_df.copy(deep=True)
                            active_file["inspection"] = UniversalInspector.inspect_dataframe(
                                inner_df, filename=selected_inner, format_type=new_parsed.get("inner_result", {}).get("format", "csv")
                            )
                        st.success(f"Switched inspection to inner file: {selected_inner}")
                        st.rerun()


if __name__ == "__main__":
    show()
