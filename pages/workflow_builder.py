"""
Universal Data Customisation & Automation Studio
Page 8: Custom Workflow Builder ("Build My Workflow")
Sequential pipeline authoring, dynamic step chaining, intermediate step inspection,
and reusable recipe configuration.
"""
import json
import time
import streamlit as st
import pandas as pd
import numpy as np

from config import SAMPLES_DIR, BASE_DIR
from utils.ui_components import (
    inject_custom_css,
    render_page_header,
    render_active_file_banner,
    render_metric_card,
    render_data_preview_table,
)
from utils.session_manager import SessionManager
from core.workflow_engine import (
    WorkflowStep,
    WorkflowDefinition,
    WorkflowEngine,
    StepExecutionLog,
    WorkflowExecutionResult,
)
from core.nlp_engine import NaturalLanguageEngine


def _init_workflow_builder_state():
    """Initializes workflow builder session state variables."""
    if "current_workflow" not in st.session_state:
        # Default empty workflow
        st.session_state.current_workflow = WorkflowDefinition(
            name="Custom Data Pipeline",
            description="Interactive sequential transformation pipeline",
            tags=["custom"],
        )
    if "pipeline_execution_result" not in st.session_state:
        st.session_state.pipeline_execution_result = None
    if "wb_show_add_step" not in st.session_state:
        st.session_state.wb_show_add_step = False
    if "wb_step_preview" not in st.session_state:
        st.session_state.wb_step_preview = None


def show():
    inject_custom_css()
    SessionManager.init_session()
    _init_workflow_builder_state()
    WorkflowEngine.ensure_presets_on_disk()

    render_page_header(
        title="Custom Workflow Builder ('Build My Workflow')",
        description="Author, chain, reorder, test, and save multi-step data pipelines. Execute sequential operations with live intermediate state inspection.",
        badge="Phase 7 Active",
    )

    render_active_file_banner()

    active_df = SessionManager.get_active_df()
    active_meta = SessionManager.get_active_file_metadata()

    # If no active file, prompt user with fallback sample loader
    if active_df is None:
        st.warning("⚠️ No active dataset selected in workspace. Please upload or select a file to author and test workflows.")
        c_load1, c_load2 = st.columns([1, 3])
        with c_load1:
            if st.button("📂 Load Sample Sales Dataset", key="btn_load_sample_sales_wb"):
                sample_path = SAMPLES_DIR / "sample_sales.xlsx"
                if sample_path.exists():
                    with open(sample_path, "rb") as f:
                        fid = SessionManager.add_uploaded_file("sample_sales.xlsx", f.read())
                        SessionManager.set_active_file(fid)
                        st.rerun()
        return

    wf: WorkflowDefinition = st.session_state.current_workflow
    columns_list = list(active_df.columns)

    # -------------------------------------------------------------
    # TOP PIPELINE CONTROLS & METADATA BAR
    # -------------------------------------------------------------
    with st.container(border=True):
        t_col1, t_col2 = st.columns([3, 1])
        with t_col1:
            wf_name = st.text_input("Workflow Pipeline Name:", value=wf.name, key="wb_input_wf_name")
            wf.name = wf_name
            wf_desc = st.text_input("Pipeline Description:", value=wf.description, key="wb_input_wf_desc")
            wf.description = wf_desc

        with t_col2:
            st.markdown(f"**Step Count:** `{len(wf.steps)} steps`")
            st.markdown(f"**Target Dataset:** `{active_meta.get('filename', 'Unknown')}`")
            st.markdown(f"**Dimensions:** `{len(active_df):,} rows × {len(columns_list)} cols`")

        st.markdown("---")
        btn_c1, btn_c2, btn_c3, btn_c4, btn_c5 = st.columns([1.5, 1.2, 1.2, 1.2, 1.2])

        with btn_c1:
            run_btn = st.button("⚡ Run Entire Pipeline", type="primary", use_container_width=True, key="wb_btn_run_pipeline")

        with btn_c2:
            toggle_add = st.button(
                "➕ Add Step" if not st.session_state.wb_show_add_step else "❌ Close Step Builder",
                use_container_width=True,
                key="wb_btn_toggle_add",
            )
            if toggle_add:
                st.session_state.wb_show_add_step = not st.session_state.wb_show_add_step
                st.rerun()

        with btn_c3:
            # Preset Loader dropdown
            presets = WorkflowEngine.get_preset_workflows()
            preset_options = {"-- Load Pre-built Recipe --": None}
            for p in presets:
                preset_options[p.name] = p

            selected_preset_label = st.selectbox(
                "Load Recipe:",
                options=list(preset_options.keys()),
                label_visibility="collapsed",
                key="wb_sel_load_preset",
            )
            if selected_preset_label != "-- Load Pre-built Recipe --":
                chosen_preset = preset_options[selected_preset_label]
                if chosen_preset:
                    st.session_state.current_workflow = WorkflowDefinition.from_dict(chosen_preset.to_dict())
                    st.session_state.pipeline_execution_result = None
                    st.toast(f"Loaded preset: {chosen_preset.name}", icon="✅")
                    st.rerun()

        with btn_c4:
            # Download JSON Recipe
            wf_json = wf.to_json(indent=2)
            st.download_button(
                label="📥 Export Recipe",
                data=wf_json,
                file_name=f"{wf.name.lower().replace(' ', '_')}.json",
                mime="application/json",
                use_container_width=True,
                key="wb_btn_download_json",
            )

        with btn_c5:
            if st.button("🔄 Clear All Steps", use_container_width=True, key="wb_btn_clear_steps"):
                wf.steps.clear()
                st.session_state.pipeline_execution_result = None
                st.toast("Workflow steps cleared.", icon="🧹")
                st.rerun()

    # -------------------------------------------------------------
    # AI NATURAL LANGUAGE STEP ASSISTANT (PHASE 8)
    # -------------------------------------------------------------
    with st.expander("🤖 Add Step via Natural Language Instruction", expanded=False):
        st.caption("Type what you want to do in plain English, and the AI engine will parse it into a verified pipeline step.")
        nl_c1, nl_c2 = st.columns([4, 1])
        with nl_c1:
            nl_step_prompt = st.text_input(
                "Enter instruction:",
                placeholder="e.g. Rename Region to SalesRegion, or Remove duplicate records based on OrderID, or Calculate Tax as [Amount] * 0.18",
                key="wb_nl_step_input",
                label_visibility="collapsed",
            )
        with nl_c2:
            nl_generate_btn = st.button("✨ Generate Step", use_container_width=True, key="wb_btn_gen_nl_step")

        if nl_generate_btn and nl_step_prompt.strip():
            parse_res = NaturalLanguageEngine.parse_instruction_offline(nl_step_prompt.strip(), df=active_df)
            if parse_res.requires_clarification:
                st.warning("⚠️ Ambiguous prompt: " + (parse_res.parsed_operations[0].clarification_question or "Please clarify."))
            elif parse_res.parsed_operations:
                for op in parse_res.parsed_operations:
                    wf_step = op.to_workflow_step()
                    wf.add_step(wf_step)
                st.session_state.pipeline_execution_result = None
                st.toast(f"Generated & appended {len(parse_res.parsed_operations)} step(s) to pipeline!", icon="✨")
                st.rerun()

    # -------------------------------------------------------------
    # STEP AUTHORING ACCORDION / BUILDER MODAL
    # -------------------------------------------------------------
    if st.session_state.wb_show_add_step:
        st.markdown("### 🛠️ Configure New Workflow Step")
        with st.container(border=True):
            f_col1, f_col2, f_col3 = st.columns([1.5, 1.5, 2])

            with f_col1:
                step_title = st.text_input("Step Name / Title:", value=f"Step {len(wf.steps) + 1}", key="wb_new_step_title")

            with f_col2:
                cat_options = {
                    "column_ops": "📊 Column Operations",
                    "row_ops": "📑 Row Operations",
                    "data_cleaning": "🧹 Data Cleaning & Quality",
                    "transformations": "🔄 Structural Transformations",
                    "validation": "🛡️ Validation & Sanity Checks",
                }
                selected_cat = st.selectbox(
                    "Step Category:",
                    options=list(cat_options.keys()),
                    format_func=lambda k: cat_options[k],
                    key="wb_new_step_cat",
                )

            with f_col3:
                # Dynamic operations according to category
                if selected_cat == "column_ops":
                    op_map = {
                        "rename_columns": "Rename Column(s)",
                        "calculate_column": "Calculate New Column (Formula)",
                        "add_column": "Add Column (Constant / Sequence / Copy)",
                        "delete_columns": "Delete Column(s)",
                        "reorder_columns": "Reorder Columns",
                        "cast_column_type": "Change Data Type",
                        "replace_values": "Find & Replace Values",
                        "merge_columns": "Merge Columns",
                        "split_column": "Split Column",
                    }
                elif selected_cat == "row_ops":
                    op_map = {
                        "remove_duplicates": "Remove Duplicate Rows",
                        "filter_rows": "Filter Records (Condition)",
                        "sort_records": "Sort Records",
                        "select_records": "Select Subset (Head / Tail / Sample)",
                    }
                elif selected_cat == "data_cleaning":
                    op_map = {
                        "standardize_text": "Standardize Text (Trim / Case / Clean)",
                        "impute_missing": "Impute Missing / Null Values",
                        "clean_numeric_formatting": "Clean Numeric / Currency Formatting",
                        "standardize_dates": "Standardize Date Formats",
                        "treat_outliers": "Treat Statistical Outliers (IQR / Z-Score)",
                        "validate_required_fields": "Validate Required Non-Null Fields",
                    }
                elif selected_cat == "transformations":
                    op_map = {
                        "group_and_aggregate": "Group By & Aggregate",
                        "pivot_dataset": "Pivot Table",
                        "unpivot_dataset": "Unpivot (Melt) Wide to Long",
                    }
                else:  # validation
                    op_map = {
                        "assert_columns_exist": "Verify Required Columns Exist",
                        "assert_no_nulls": "Verify No Nulls in Key Columns",
                        "assert_unique_key": "Verify 100% Unique Primary Key",
                        "assert_min_rows": "Verify Minimum Row Count",
                    }

                selected_op = st.selectbox(
                    "Select Specific Operation:",
                    options=list(op_map.keys()),
                    format_func=lambda k: op_map[k],
                    key="wb_new_step_op",
                )

            st.markdown("#### Parameter Configuration")
            params = {}

            # --- DYNAMIC PARAMETER FORMS ---
            # 1. Column Operations
            if selected_op == "rename_columns":
                p_col1, p_col2 = st.columns(2)
                with p_col1:
                    src_col = st.selectbox("Column to rename:", options=columns_list, key="wb_param_ren_src")
                with p_col2:
                    new_col_name = st.text_input("New Column Name:", value=f"{src_col}_Renamed", key="wb_param_ren_target")
                params = {"mapping": {src_col: new_col_name}}

            elif selected_op == "calculate_column":
                p_col1, p_col2 = st.columns([1, 2])
                with p_col1:
                    calc_target = st.text_input("Target Column Name:", value="CalculatedCol", key="wb_param_calc_target")
                with p_col2:
                    calc_formula = st.text_input(
                        "Calculation Formula:",
                        value=f"[{columns_list[0]}] * 1.18" if columns_list else "[Col] * 1.18",
                        help="Wrap column names in square brackets, e.g. [Amount] * 1.18 or [Qty] * [Price]",
                        key="wb_param_calc_formula",
                    )
                params = {"target_col": calc_target, "formula": calc_formula}

            elif selected_op == "add_column":
                p_c1, p_c2, p_c3 = st.columns(3)
                with p_c1:
                    add_name = st.text_input("New Column Name:", value="StatusFlag", key="wb_param_add_name")
                with p_c2:
                    add_mode = st.selectbox("Creation Mode:", options=["constant", "sequence", "copy_col"], key="wb_param_add_mode")
                with p_c3:
                    if add_mode == "constant":
                        add_val = st.text_input("Constant Value:", value="ACTIVE", key="wb_param_add_const")
                        params = {"col_name": add_name, "mode": "constant", "constant_val": add_val}
                    elif add_mode == "sequence":
                        seq_start = st.number_input("Start Number:", value=1, step=1, key="wb_param_add_seq")
                        params = {"col_name": add_name, "mode": "sequence", "seq_start": int(seq_start)}
                    else:
                        src_copy = st.selectbox("Source Column to Copy:", options=columns_list, key="wb_param_add_copy")
                        params = {"col_name": add_name, "mode": "copy_col", "source_col": src_copy}

            elif selected_op == "delete_columns":
                del_cols = st.multiselect("Select Column(s) to Delete:", options=columns_list, key="wb_param_del_cols")
                params = {"columns": del_cols}

            elif selected_op == "reorder_columns":
                reorder_cols = st.multiselect("Define Column Sequence:", options=columns_list, default=columns_list, key="wb_param_reorder")
                params = {"columns": reorder_cols}

            elif selected_op == "cast_column_type":
                p_c1, p_c2 = st.columns(2)
                with p_c1:
                    cast_col = st.selectbox("Target Column:", options=columns_list, key="wb_param_cast_col")
                with p_c2:
                    cast_type = st.selectbox("Target Data Type:", options=["string", "integer", "float", "datetime", "boolean"], key="wb_param_cast_type")
                params = {"col_name": cast_col, "target_type": cast_type}

            elif selected_op == "replace_values":
                p_c1, p_c2, p_c3 = st.columns(3)
                with p_c1:
                    rep_col = st.selectbox("Column (or all):", options=["[All Columns]"] + columns_list, key="wb_param_rep_col")
                with p_c2:
                    f_val = st.text_input("Find Value:", key="wb_param_f_val")
                with p_c3:
                    r_val = st.text_input("Replace Value:", key="wb_param_r_val")
                params = {
                    "col_name": None if rep_col == "[All Columns]" else rep_col,
                    "find_val": f_val,
                    "replace_val": r_val,
                    "match_mode": "exact",
                }

            elif selected_op == "merge_columns":
                p_c1, p_c2, p_c3 = st.columns(3)
                with p_c1:
                    m_cols = st.multiselect("Columns to Merge:", options=columns_list, key="wb_param_m_cols")
                with p_c2:
                    m_target = st.text_input("Target Column:", value="Merged_Text", key="wb_param_m_target")
                with p_c3:
                    m_sep = st.text_input("Separator:", value=" - ", key="wb_param_m_sep")
                params = {"cols_to_merge": m_cols, "target_col": m_target, "separator": m_sep, "drop_sources": False}

            elif selected_op == "split_column":
                p_c1, p_c2, p_c3 = st.columns(3)
                with p_c1:
                    sp_src = st.selectbox("Column to Split:", options=columns_list, key="wb_param_sp_src")
                with p_c2:
                    sp_del = st.text_input("Delimiter:", value=",", key="wb_param_sp_del")
                with p_c3:
                    sp_names = st.text_input("New Column Names (comma separated):", value=f"{sp_src}_Part1, {sp_src}_Part2", key="wb_param_sp_names")
                params = {
                    "source_col": sp_src,
                    "delimiter": sp_del,
                    "new_cols": [x.strip() for x in sp_names.split(",") if x.strip()],
                    "drop_source": False,
                }

            # 2. Row Operations
            elif selected_op == "remove_duplicates":
                p_c1, p_c2 = st.columns(2)
                with p_c1:
                    dedup_cols = st.multiselect("Key Column(s) (empty = all columns):", options=columns_list, key="wb_param_dedup_cols")
                with p_c2:
                    dedup_keep = st.selectbox("Keep Mode:", options=["first", "last", "none"], key="wb_param_dedup_keep")
                params = {"subset_cols": dedup_cols if dedup_cols else None, "keep_mode": dedup_keep}

            elif selected_op == "filter_rows":
                p_c1, p_c2, p_c3, p_c4 = st.columns(4)
                with p_c1:
                    f_col = st.selectbox("Filter Column:", options=columns_list, key="wb_param_f_col")
                with p_c2:
                    f_op = st.selectbox(
                        "Condition:",
                        options=["equals", "contains", "greater_than", "less_than", "is_not_null", "is_null"],
                        key="wb_param_f_op",
                    )
                with p_c3:
                    f_val = st.text_input("Target Value:", value="0", key="wb_param_f_val")
                with p_c4:
                    f_action = st.selectbox("Action:", options=["keep", "drop"], key="wb_param_f_act")
                params = {"col_name": f_col, "operator": f_op, "target_val": f_val, "action": f_action}

            elif selected_op == "sort_records":
                p_c1, p_c2 = st.columns(2)
                with p_c1:
                    s_cols = st.multiselect("Sort Columns:", options=columns_list, default=[columns_list[0]] if columns_list else [], key="wb_param_s_cols")
                with p_c2:
                    s_order = st.selectbox("Order Direction:", options=["Ascending (A-Z, 0-9)", "Descending (Z-A, 9-0)"], key="wb_param_s_order")
                asc_flag = (s_order.startswith("Ascending"))
                params = {"sort_cols": s_cols, "ascending_list": [asc_flag] * len(s_cols)}

            elif selected_op == "select_records":
                p_c1, p_c2 = st.columns(2)
                with p_c1:
                    sel_mode = st.selectbox("Selection Mode:", options=["head", "tail", "sample"], key="wb_param_sel_mode")
                with p_c2:
                    sel_count = st.number_input("Number of Records:", min_value=1, max_value=100000, value=100, key="wb_param_sel_cnt")
                params = {"mode": sel_mode, "count": int(sel_count)}

            # 3. Data Cleaning
            elif selected_op == "standardize_text":
                p_c1, p_c2 = st.columns(2)
                with p_c1:
                    txt_cols = st.multiselect("Target Text Columns:", options=columns_list, key="wb_param_txt_cols")
                with p_c2:
                    txt_ops = st.multiselect(
                        "Cleaning Transformations:",
                        options=["trim", "remove_extra_spaces", "uppercase", "lowercase", "titlecase", "alphanumeric_only"],
                        default=["trim", "remove_extra_spaces"],
                        key="wb_param_txt_ops",
                    )
                params = {"columns": txt_cols, "operations": txt_ops}

            elif selected_op == "impute_missing":
                p_c1, p_c2, p_c3 = st.columns(3)
                with p_c1:
                    imp_cols = st.multiselect("Columns to Impute:", options=columns_list, key="wb_param_imp_cols")
                with p_c2:
                    imp_strat = st.selectbox("Strategy:", options=["constant", "mean", "median", "mode", "ffill", "bfill", "drop_rows"], key="wb_param_imp_strat")
                with p_c3:
                    imp_const = st.text_input("Constant Value (if constant):", value="N/A", key="wb_param_imp_const")
                params = {"columns": imp_cols, "strategy": imp_strat, "constant_value": imp_const}

            elif selected_op == "clean_numeric_formatting":
                p_c1, p_c2, p_c3 = st.columns(3)
                with p_c1:
                    num_cols = st.multiselect("Numeric Columns:", options=columns_list, key="wb_param_num_cols")
                with p_c2:
                    strip_sym = st.checkbox("Strip Currency & Symbols ($ € ₹ %)", value=True, key="wb_param_num_sym")
                with p_c3:
                    round_dec = st.number_input("Round to Decimals (optional):", min_value=-1, max_value=6, value=2, key="wb_param_num_dec")
                params = {
                    "columns": num_cols,
                    "strip_symbols": strip_sym,
                    "decimal_separator": ".",
                    "round_decimals": None if round_dec < 0 else int(round_dec),
                }

            elif selected_op == "standardize_dates":
                p_c1, p_c2 = st.columns(2)
                with p_c1:
                    dt_col = st.selectbox("Date Column:", options=columns_list, key="wb_param_dt_col")
                with p_c2:
                    dt_fmt = st.selectbox(
                        "Target Date Format:",
                        options=["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"],
                        key="wb_param_dt_fmt",
                    )
                params = {"column": dt_col, "target_format": dt_fmt}

            elif selected_op == "treat_outliers":
                p_c1, p_c2, p_c3 = st.columns(3)
                with p_c1:
                    out_col = st.selectbox("Target Column:", options=columns_list, key="wb_param_out_col")
                with p_c2:
                    out_act = st.selectbox("Action:", options=["cap", "flag", "replace_null", "drop_rows"], key="wb_param_out_act")
                with p_c3:
                    out_mult = st.number_input("IQR Multiplier:", min_value=1.0, max_value=5.0, value=1.5, step=0.1, key="wb_param_out_mult")
                params = {"column": out_col, "method": "iqr", "action": out_act, "multiplier": float(out_mult)}

            elif selected_op == "validate_required_fields":
                p_c1, p_c2 = st.columns(2)
                with p_c1:
                    req_cols = st.multiselect("Required Columns:", options=columns_list, key="wb_param_req_cols")
                with p_c2:
                    req_act = st.selectbox("Action on Missing:", options=["flag", "drop"], key="wb_param_req_act")
                params = {"required_columns": req_cols, "action": req_act}

            # 4. Structural Transformations
            elif selected_op == "group_and_aggregate":
                p_c1, p_c2, p_c3 = st.columns(3)
                with p_c1:
                    grp_cols = st.multiselect("Group By Field(s):", options=columns_list, key="wb_param_grp_cols")
                with p_c2:
                    val_col = st.selectbox("Measure Column:", options=columns_list, key="wb_param_grp_val")
                with p_c3:
                    agg_fn = st.selectbox("Aggregation Function:", options=["sum", "mean", "count", "min", "max"], key="wb_param_grp_fn")
                params = {"group_by_cols": grp_cols, "agg_spec": {val_col: agg_fn}}

            elif selected_op == "pivot_dataset":
                p_c1, p_c2, p_c3, p_c4 = st.columns(4)
                with p_c1:
                    piv_idx = st.multiselect("Index (Row) Columns:", options=columns_list, key="wb_param_piv_idx")
                with p_c2:
                    piv_cols = st.selectbox("Pivot Header Column:", options=columns_list, key="wb_param_piv_col")
                with p_c3:
                    piv_val = st.selectbox("Values Column:", options=columns_list, key="wb_param_piv_val")
                with p_c4:
                    piv_fn = st.selectbox("Aggregator:", options=["sum", "mean", "count"], key="wb_param_piv_fn")
                params = {"index_cols": piv_idx, "columns_col": piv_cols, "values_col": piv_val, "aggfunc": piv_fn}

            elif selected_op == "unpivot_dataset":
                p_c1, p_c2 = st.columns(2)
                with p_c1:
                    unp_id = st.multiselect("ID Anchor Columns:", options=columns_list, key="wb_param_unp_id")
                with p_c2:
                    unp_val = st.multiselect("Columns to Unpivot (Values):", options=[c for c in columns_list if c not in unp_id], key="wb_param_unp_val")
                params = {"id_vars": unp_id, "value_vars": unp_val, "var_name": "Attribute", "value_name": "Value"}

            # 5. Validation Rules
            elif selected_op in ["assert_columns_exist", "assert_no_nulls", "assert_unique_key"]:
                val_cols = st.multiselect("Target Columns:", options=columns_list, key="wb_param_val_cols")
                params = {"columns": val_cols}

            elif selected_op == "assert_min_rows":
                min_r = st.number_input("Minimum Required Rows:", min_value=1, value=1, key="wb_param_val_min_r")
                params = {"min_rows": int(min_r)}

            st.write("")
            act_col1, act_col2, _ = st.columns([1.5, 1.5, 3])

            with act_col1:
                if st.button("➕ Append Step to Pipeline", type="primary", use_container_width=True, key="wb_btn_append_step"):
                    new_step = WorkflowStep(
                        name=step_title,
                        category=selected_cat,
                        operation=selected_op,
                        params=params,
                        enabled=True,
                    )
                    wf.add_step(new_step)
                    st.session_state.wb_show_add_step = False
                    st.session_state.pipeline_execution_result = None
                    st.toast(f"Appended Step: {step_title}", icon="✅")
                    st.rerun()

            with act_col2:
                if st.button("🧪 Test Step Live", use_container_width=True, key="wb_btn_test_step"):
                    try:
                        test_step = WorkflowStep(
                            name="Test Step",
                            category=selected_cat,
                            operation=selected_op,
                            params=params,
                        )
                        test_out, test_msg = WorkflowEngine.execute_single_step(active_df.head(10), test_step)
                        st.session_state.wb_step_preview = {"df": test_out, "msg": test_msg}
                        st.success(f"Step test successful: {test_msg}")
                    except Exception as ex:
                        st.error(f"Step test failed: {ex}")

            if st.session_state.wb_step_preview is not None:
                st.caption(f"Preview Output: {st.session_state.wb_step_preview['msg']}")
                st.dataframe(st.session_state.wb_step_preview["df"], use_container_width=True)

    # -------------------------------------------------------------
    # PIPELINE EXECUTION ENGINE LOGIC
    # -------------------------------------------------------------
    if run_btn:
        if not wf.steps:
            st.warning("⚠️ The pipeline has no steps! Add steps or load a preset recipe first.")
        else:
            with st.spinner("⚡ Executing pipeline steps sequentially..."):
                exec_result = WorkflowEngine.execute_workflow(
                    initial_df=active_df,
                    workflow=wf,
                    stop_on_error=False,
                    capture_previews=True,
                    preview_rows=10,
                )
                st.session_state.pipeline_execution_result = exec_result
                if exec_result.is_success:
                    st.toast("Pipeline execution completed successfully!", icon="🎉")
                else:
                    st.toast(f"Pipeline finished with {exec_result.failed_steps} failed step(s).", icon="⚠️")

    # -------------------------------------------------------------
    # SEQUENTIAL PIPELINE STEP CANVAS & TIMELINE
    # -------------------------------------------------------------
    st.markdown("### 📋 Pipeline Execution Canvas")

    if not wf.steps:
        st.info("ℹ️ No transformation steps added yet. Click **➕ Add Step** above or select a preset recipe to begin.")
        q_c1, q_c2, q_c3 = st.columns(3)
        with q_c1:
            if st.button("🧹 Load Audit & Deduplicate Recipe", key="wb_quick_preset_1"):
                p = WorkflowEngine.get_preset_workflows()[0]
                st.session_state.current_workflow = WorkflowDefinition.from_dict(p.to_dict())
                st.rerun()
        with q_c2:
            if st.button("📊 Load Sales Tax Calculation Recipe", key="wb_quick_preset_2"):
                p = WorkflowEngine.get_preset_workflows()[1]
                st.session_state.current_workflow = WorkflowDefinition.from_dict(p.to_dict())
                st.rerun()
        with q_c3:
            if st.button("🎯 Load Outlier Treatment Recipe", key="wb_quick_preset_3"):
                p = WorkflowEngine.get_preset_workflows()[3]
                st.session_state.current_workflow = WorkflowDefinition.from_dict(p.to_dict())
                st.rerun()

    else:
        # Render visual steps
        exec_res: Optional[WorkflowExecutionResult] = st.session_state.pipeline_execution_result

        for idx, step in enumerate(wf.steps):
            # Check execution log for this step
            step_log = None
            if exec_res and idx < len(exec_res.logs):
                step_log = exec_res.logs[idx]

            cat_icon = {
                "column_ops": "📊",
                "row_ops": "📑",
                "data_cleaning": "🧹",
                "transformations": "🔄",
                "validation": "🛡️",
            }.get(step.category, "⚙️")

            status_badge = "⏳ Pending Run"
            if step_log:
                if step_log.status == "SUCCESS":
                    status_badge = f"✅ Success ({step_log.duration_ms:.1f}ms)"
                elif step_log.status == "FAILED":
                    status_badge = f"❌ Failed ({step_log.duration_ms:.1f}ms)"
                elif step_log.status == "SKIPPED":
                    status_badge = "⏭️ Skipped"

            with st.container(border=True):
                s_c1, s_c2, s_c3 = st.columns([4, 2, 2.5])

                with s_c1:
                    enable_check = st.checkbox(
                        f"**Step {idx + 1}: {cat_icon} {step.name}**",
                        value=step.enabled,
                        key=f"wb_step_en_{step.step_id}",
                    )
                    if enable_check != step.enabled:
                        step.enabled = enable_check
                        st.rerun()

                    st.caption(f"`Category:` **{step.category}** | `Operation:` **{step.operation}**")
                    param_str = ", ".join([f"{k}={v}" for k, v in step.params.items()])
                    st.caption(f"`Parameters:` `{param_str[:120]}{'...' if len(param_str) > 120 else ''}`")

                with s_c2:
                    st.markdown(f"**Status:** {status_badge}")
                    if step_log and step_log.status == "SUCCESS":
                        st.caption(f"Rows: `{step_log.input_rows} ➔ {step_log.output_rows}` | Cols: `{step_log.input_cols} ➔ {step_log.output_cols}`")

                with s_c3:
                    # Step reorder and deletion buttons
                    btn_up, btn_down, btn_del = st.columns(3)
                    with btn_up:
                        if st.button("⬆", key=f"wb_btn_up_{step.step_id}", help="Move Up", disabled=(idx == 0)):
                            wf.move_step(idx, idx - 1)
                            st.session_state.pipeline_execution_result = None
                            st.rerun()
                    with btn_down:
                        if st.button("⬇", key=f"wb_btn_down_{step.step_id}", help="Move Down", disabled=(idx == len(wf.steps) - 1)):
                            wf.move_step(idx, idx + 1)
                            st.session_state.pipeline_execution_result = None
                            st.rerun()
                    with btn_del:
                        if st.button("🗑️", key=f"wb_btn_del_{step.step_id}", help="Delete Step"):
                            wf.remove_step(idx)
                            st.session_state.pipeline_execution_result = None
                            st.rerun()

                # Expandable intermediate step inspection
                if step_log:
                    if step_log.status == "FAILED" and step_log.error_details:
                        st.error(f"Error: {step_log.error_details}")
                    elif step_log.status == "SUCCESS" and step_log.preview_df is not None:
                        with st.expander(f"🔍 Inspect Output of Step {idx + 1}: {step.name} ({step_log.message})"):
                            st.dataframe(step_log.preview_df, use_container_width=True)

    # -------------------------------------------------------------
    # FINAL EXECUTION SUMMARY & ACTIVE DATASET COMMIT
    # -------------------------------------------------------------
    if st.session_state.pipeline_execution_result is not None:
        exec_res: WorkflowExecutionResult = st.session_state.pipeline_execution_result
        st.markdown("---")
        st.markdown("### 🏆 Pipeline Execution Results & Summary")

        m1, m2, m3, m4 = st.columns(4)
        with m1:
            status_text = "PASSED" if exec_res.is_success else "COMPLETED WITH ERRORS"
            status_color = "#10B981" if exec_res.is_success else "#EF4444"
            render_metric_card("Pipeline Status", status_text, col=m1, color=status_color)
        with m2:
            render_metric_card("Total Run Duration", f"{exec_res.total_duration_ms:.1f} ms", col=m2, color="#3B82F6")
        with m3:
            row_delta = len(exec_res.final_df) - len(exec_res.initial_df)
            row_txt = f"{len(exec_res.final_df):,} ({row_delta:+d})"
            render_metric_card("Final Row Count", row_txt, col=m3, color="#8B5CF6")
        with m4:
            render_metric_card("Step Health", f"{exec_res.successful_steps}/{exec_res.total_steps} Succeeded", col=m4, color="#10B981")

        # Tabbed preview: Transformed Output vs Initial Dataset
        prev_tab1, prev_tab2 = st.tabs(["🚀 Transformed Output Dataset", "📄 Original Input Dataset"])
        with prev_tab1:
            st.dataframe(exec_res.final_df.head(25), use_container_width=True)
            st.caption(f"Showing first 25 of {len(exec_res.final_df):,} rows.")

        with prev_tab2:
            st.dataframe(exec_res.initial_df.head(25), use_container_width=True)
            st.caption(f"Showing first 25 of {len(exec_res.initial_df):,} original rows.")

        st.write("")
        c_commit1, c_commit2, _ = st.columns([2, 1.5, 2])
        with c_commit1:
            if st.button("🚀 Commit Output to Active Working Dataset", type="primary", use_container_width=True, key="wb_btn_commit_output"):
                SessionManager.update_working_df(
                    exec_res.final_df,
                    action_name=f"Workflow Pipeline: {wf.name}",
                    description=f"Executed {exec_res.successful_steps} sequential transformation steps.",
                )
                st.success("Successfully pushed transformed output to active session! Full undo/redo tracking active.")
                st.rerun()

        with c_commit2:
            # Save workflow recipe to disk catalog
            if st.button("💾 Save Recipe to Catalog", use_container_width=True, key="wb_btn_save_recipe"):
                saved_path = WorkflowEngine.save_workflow_to_disk(wf)
                st.toast(f"Saved recipe to disk: {saved_path.name}", icon="💾")


if __name__ == "__main__":
    show()
