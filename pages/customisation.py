"""
Data Customisation Studio (Phase 2 & Phase 3)
Comprehensive workspace for Column Operations, Row Operations, Data Cleaning,
and Reshaping / Multi-Dataset Transformations.
Supports instant Undo, Redo, Reset, formula calculations, deduplication, filtering,
text/date standardization, outlier treatment, dataset merging, joins, and pivoting.
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
from core.transformations import (
    ColumnOperations,
    RowOperations,
    StructuralTransformationEngine,
)
from core.data_cleaning import DataCleaningEngine
from core.nlp_engine import NaturalLanguageEngine, ProposedOperation, ParsedInstructionResult
from core.workflow_engine import WorkflowDefinition, WorkflowStep
from config import SAMPLES_DIR


def show():
    inject_custom_css()
    SessionManager.init_session()

    render_page_header(
        title="Data Customisation & Transformation Studio",
        description="Workspace for column and row editing, data cleaning, date standardisation, dataset joins, and AI-assisted instructions.",
        badge="Phase 8 Active",
    )

    active_file = render_active_file_banner()
    if not active_file:
        st.markdown(
            """
            <div style="background: rgba(30, 41, 59, 0.5); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 10px; padding: 24px; text-align: center; margin: 20px 0;">
                <div style="font-size: 2rem; margin-bottom: 8px;">📂</div>
                <h3 style="color: #F8FAFC; margin: 0;">No Active Dataset Loaded</h3>
                <p style="color: #94A3B8; font-size: 0.95rem; margin-top: 6px;">
                    Upload your own dataset in <strong>2. Upload Files</strong>, or click below to immediately load a test dataset into the studio.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        c_load1, c_load2 = st.columns(2)
        with c_load1:
            if st.button("📊 Load Sample Sales Dataset (.xlsx)", use_container_width=True, key="cust_no_file_load_sales"):
                sample_p = SAMPLES_DIR / "sample_sales.xlsx"
                if sample_p.exists():
                    with open(sample_p, "rb") as sf:
                        SessionManager.add_uploaded_file("sample_sales.xlsx", sf.read())
                    st.success("Sample Sales dataset loaded!")
                    st.rerun()
        with c_load2:
            if st.button("👥 Load Sample Customers Dataset (.csv)", use_container_width=True, key="cust_no_file_load_cust"):
                sample_p = SAMPLES_DIR / "sample_customers.csv"
                if sample_p.exists():
                    with open(sample_p, "rb") as sf:
                        SessionManager.add_uploaded_file("sample_customers.csv", sf.read())
                    st.success("Sample Customers dataset loaded!")
                    st.rerun()
        return

    df = SessionManager.get_active_df()
    if df is None or df.empty:
        st.warning("The active dataset is currently empty.")
        return

    # -------------------------------------------------------------
    # TOP ACTION TOOLBAR: UNDO, REDO, RESET, STEP BADGE
    # -------------------------------------------------------------
    bar_col1, bar_col2, bar_col3, bar_col4 = st.columns([1.5, 1.5, 2, 5])

    with bar_col1:
        can_undo = SessionManager.can_undo()
        if st.button("↶ Undo", disabled=not can_undo, use_container_width=True, key="btn_undo"):
            success, msg = SessionManager.undo()
            if success:
                st.toast(msg, icon="↶")
                st.rerun()

    with bar_col2:
        can_redo = SessionManager.can_redo()
        if st.button("↷ Redo", disabled=not can_redo, use_container_width=True, key="btn_redo"):
            success, msg = SessionManager.redo()
            if success:
                st.toast(msg, icon="↷")
                st.rerun()

    with bar_col3:
        if st.button("🔄 Reset to Original", type="secondary", use_container_width=True, key="btn_reset_orig"):
            SessionManager.reset_working_df()
            st.toast("Dataset reverted to pristine baseline copy.", icon="🔄")
            st.rerun()

    with bar_col4:
        history = st.session_state.get("change_history", [])
        h_idx = st.session_state.get("history_index", 0)
        curr_action = history[h_idx]["action"] if history and 0 <= h_idx < len(history) else "Initial State"
        st.markdown(
            f"""
            <div style="padding: 6px 12px; background: rgba(30, 41, 59, 0.4); border-radius: 6px; border: 1px solid rgba(255,255,255,0.08); font-size: 0.85rem; color: #94A3B8;">
                <strong style="color: #60A5FA;">History: Step {h_idx} of {max(0, len(history)-1)}</strong> — <span style="color: #F8FAFC;">{curr_action}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.write("")

    # -------------------------------------------------------------
    # MAIN WORKSPACE TABS
    # -------------------------------------------------------------
    tab_ai, tab_cols, tab_rows, tab_clean, tab_struct, tab_history = st.tabs([
        "🤖 AI Natural Language Copilot",
        "🔤 Column Operations",
        "🔢 Row Operations",
        "🧼 Data Cleaning",
        "🔀 Reshape & Multi-Dataset",
        "📜 Change History & Audit",
    ])

    # =============================================================
    # TAB 0: AI NATURAL LANGUAGE COPILOT (PHASE 8)
    # =============================================================
    with tab_ai:
        st.markdown("### 🤖 Natural Language Instruction Copilot")
        st.caption(
            "Describe your required data transformations in plain English. The AI engine compiles instructions "
            "into validated operations, enforces human confirmation gates, and guarantees no columns are invented."
        )

        settings = st.session_state.get("app_settings", {})
        ai_provider = settings.get("ai_provider", "offline")
        gemini_api_key = settings.get("gemini_api_key", "")

        c_eng1, c_eng2 = st.columns([3, 1])
        with c_eng1:
            if ai_provider == "gemini" and gemini_api_key:
                st.info("⚡ **Active Engine:** Google Gemini Cloud LLM (REST API). Online model enabled.")
            else:
                st.info("🛡️ **Active Engine:** Universal Semantic NLP (Offline Mode). 100% private, instant execution, zero API keys required.")
        with c_eng2:
            st.caption("Configure online AI in `12. Settings`.")

        # Quick Example Prompts
        st.markdown("**Quick Example Prompts (Click to test):**")
        p_c1, p_c2, p_c3 = st.columns(3)
        with p_c1:
            if st.button("🏷️ Rename Column", use_container_width=True, key="ai_quick_ren"):
                c0 = df.columns[0]
                st.session_state["ai_prompt_input"] = f"Rename {c0} to {c0}_Standardized"
            if st.button("📅 Standardize Date", use_container_width=True, key="ai_quick_date"):
                date_c = next((c for c in df.columns if "date" in c.lower() or "dt" in c.lower()), df.columns[0])
                st.session_state["ai_prompt_input"] = f"Convert the date column {date_c} into DD-MM-YYYY"

        with p_c2:
            if st.button("🧹 Remove Duplicates", use_container_width=True, key="ai_quick_dedup"):
                id_c = next((c for c in df.columns if "id" in c.lower() or "no" in c.lower() or "num" in c.lower()), df.columns[0])
                st.session_state["ai_prompt_input"] = f"Remove all duplicate records based on {id_c}"
            if st.button("🧮 Calculate Tax Formula", use_container_width=True, key="ai_quick_calc"):
                num_c = next((c for c in df.columns if any(k in c.lower() for k in ["amount", "price", "cost", "total"])), df.columns[0])
                st.session_state["ai_prompt_input"] = f"Calculate Tax as [{num_c}] * 0.18"

        with p_c3:
            if st.button("🧼 Clean Numeric Formatting", use_container_width=True, key="ai_quick_num"):
                num_c = next((c for c in df.columns if any(k in c.lower() for k in ["amount", "price", "cost", "total"])), df.columns[0])
                st.session_state["ai_prompt_input"] = f"Clean numeric currency formatting in {num_c}"
            if st.button("🎯 Cap Statistical Outliers", use_container_width=True, key="ai_quick_outlier"):
                num_c = next((c for c in df.columns if any(k in c.lower() for k in ["amount", "price", "cost", "total"])), df.columns[0])
                st.session_state["ai_prompt_input"] = f"Cap outliers in {num_c}"

        st.write("")

        # Instruction Input Form
        current_prompt = st.session_state.get("ai_prompt_input", "")
        user_prompt = st.text_area(
            "Enter your instruction in natural language:",
            value=current_prompt,
            height=85,
            placeholder="e.g. Rename Patient ID to Registration Number, or Remove duplicates by Invoice Number, or Calculate Tax as [Amount] * 0.18",
            key="nl_instruction_textarea",
        )

        parse_btn = st.button("🔍 Parse & Propose Transformation", type="primary", use_container_width=True, key="ai_btn_parse")

        if parse_btn and user_prompt.strip():
            with st.spinner("Analyzing instruction semantics and validating schema..."):
                if ai_provider == "gemini" and gemini_api_key:
                    parse_result = NaturalLanguageEngine.parse_instruction_with_gemini(
                        instruction=user_prompt.strip(),
                        api_key=gemini_api_key,
                        df=df,
                    )
                else:
                    parse_result = NaturalLanguageEngine.parse_instruction_offline(
                        instruction=user_prompt.strip(),
                        df=df,
                    )
                st.session_state["ai_last_parse_result"] = parse_result

        # Display Parsed Transformation Proposals & Human Gate
        if "ai_last_parse_result" in st.session_state and st.session_state["ai_last_parse_result"] is not None:
            res: ParsedInstructionResult = st.session_state["ai_last_parse_result"]
            st.markdown("---")
            st.markdown("### 📋 Proposed Transformation Plan")

            if res.error_message:
                st.warning(f"⚠️ {res.error_message}")

            if res.requires_clarification:
                st.warning("⚠️ **Ambiguous Instruction:** The engine requires clarification before proceeding safely.")
                for op in res.parsed_operations:
                    if op.needs_clarification and op.clarification_question:
                        st.markdown(f"**Question:** {op.clarification_question}")
                        if op.clarification_options:
                            st.caption("Suggested clarifications:")
                            for opt in op.clarification_options:
                                if st.button(f"👉 {opt}", key=f"ai_opt_{opt}"):
                                    st.session_state["ai_prompt_input"] = opt
                                    st.rerun()

            elif not res.parsed_operations:
                st.info("No transformation operations were generated.")

            else:
                for idx, op in enumerate(res.parsed_operations):
                    with st.container(border=True):
                        h_col1, h_col2 = st.columns([3, 1])
                        with h_col1:
                            st.markdown(f"#### Step {idx + 1}: {op.human_explanation}")
                            st.markdown(
                                f"`Category:` **{op.category}** | `Operation:` **{op.operation}** | "
                                f"`Confidence:` **{op.confidence * 100:.0f}%**"
                            )
                            if op.affected_columns:
                                st.caption(f"Affected Columns: `[{', '.join(op.affected_columns)}]`")
                            st.caption(f"Parameters: `{op.parameters}`")

                        with h_col2:
                            if op.is_destructive:
                                st.error("⚠️ **Destructive**\nDeletes data or modifies structure.")
                            else:
                                st.success("🟢 **Safe**\nNon-destructive transformation.")

                # Destructive confirmation banner
                if res.has_destructive_ops:
                    st.warning(
                        "🛑 **HUMAN CONFIRMATION GATE:** One or more operations are destructive (e.g. deleting rows, dropping columns). "
                        "Please inspect the sandbox preview below before confirming execution."
                    )

                # Sandbox Live Preview
                try:
                    preview_df, preview_logs = NaturalLanguageEngine.execute_proposed_operations(
                        df.head(10), res.parsed_operations
                    )
                    with st.expander("🔍 Live Sandbox Preview (First 10 Rows)", expanded=True):
                        st.dataframe(preview_df, use_container_width=True)
                        st.caption(f"Transformation logs: {', '.join(preview_logs)}")
                except Exception as ex:
                    st.error(f"Cannot generate sandbox preview: {ex}")

                # Human Confirmation Actions
                st.write("")
                act_col1, act_col2, _ = st.columns([2, 2, 2])

                with act_col1:
                    if st.button("✅ Confirm & Execute Transformation", type="primary", use_container_width=True, key="ai_btn_confirm_exec"):
                        with st.spinner("Applying confirmed transformations to active dataset..."):
                            try:
                                final_transformed_df, exec_msgs = NaturalLanguageEngine.execute_proposed_operations(
                                    df, res.parsed_operations
                                )
                                SessionManager.update_working_df(
                                    final_transformed_df,
                                    action_name=f"AI: {res.parsed_operations[0].human_explanation[:40]}",
                                    description="; ".join(exec_msgs),
                                )
                                st.session_state["ai_last_parse_result"] = None
                                st.session_state["ai_prompt_input"] = ""
                                st.toast("Successfully executed AI transformations! Full undo/redo active.", icon="🎉")
                                st.rerun()
                            except Exception as ex:
                                st.error(f"Failed to execute transformation on full dataset: {ex}")

                with act_col2:
                    if st.button("➕ Add to Workflow Builder", use_container_width=True, key="ai_btn_send_to_wb"):
                        if "current_workflow" not in st.session_state:
                            st.session_state.current_workflow = WorkflowDefinition(name="Custom Data Pipeline")
                        for op in res.parsed_operations:
                            st.session_state.current_workflow.add_step(op.to_workflow_step())
                        st.toast(f"Appended {len(res.parsed_operations)} step(s) to Workflow Builder!", icon="➕")

    # =============================================================
    # TAB 1: COLUMN OPERATIONS
    # =============================================================
    with tab_cols:
        col_op_mode = st.selectbox(
            "Select Column Transformation:",
            [
                "Rename Columns",
                "Add New Column",
                "Delete Columns",
                "Reorder Columns",
                "Merge Columns",
                "Split Column",
                "Change Data Types",
                "Replace Column Values",
                "Calculate Column / Formula",
                "Map Column Values (Dictionary)",
            ],
            key="col_op_selector",
        )

        st.markdown("---")

        # 1. RENAME COLUMNS
        if col_op_mode == "Rename Columns":
            st.markdown("##### ✏️ Rename Column(s)")
            r_col1, r_col2 = st.columns([1, 2])
            with r_col1:
                target_col = st.selectbox("Column to rename:", options=list(df.columns), key="ren_col_target")
                new_col_name = st.text_input("New column name:", value=target_col, key="ren_col_new_name")
                if st.button("Apply Rename", key="btn_apply_rename"):
                    try:
                        new_df, msg = ColumnOperations.rename_columns(df, {target_col: new_col_name})
                        SessionManager.update_working_df(new_df, "Rename Column", msg)
                        st.success(msg)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

            with r_col2:
                st.caption("Quick batch rename: Rename multiple columns simultaneously below.")
                with st.expander("⚡ Batch Rename All Columns"):
                    batch_renames = {}
                    b_cols = st.columns(2)
                    for i, c in enumerate(df.columns):
                        with b_cols[i % 2]:
                            new_val = st.text_input(f"'{c}' ->", value=c, key=f"batch_ren_{c}")
                            if new_val != c:
                                batch_renames[c] = new_val

                    if batch_renames and st.button("Apply Batch Rename", key="btn_apply_batch_ren"):
                        try:
                            new_df, msg = ColumnOperations.rename_columns(df, batch_renames)
                            SessionManager.update_working_df(new_df, "Batch Rename", msg)
                            st.success(msg)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

        # 2. ADD NEW COLUMN
        elif col_op_mode == "Add New Column":
            st.markdown("##### ➕ Add New Column")
            a1, a2, a3 = st.columns(3)
            with a1:
                new_col_name = st.text_input("New Column Name:", placeholder="e.g. Status_Code", key="add_col_name")
            with a2:
                val_type = st.selectbox(
                    "Value Type:",
                    ["Constant Text / Number", "Sequential Number (1, 2, 3...)", "Copy From Existing Column", "Empty / Null"],
                    key="add_col_val_type",
                )
            with a3:
                constant_val = None
                source_c = None
                if val_type == "Constant Text / Number":
                    constant_val = st.text_input("Constant Value:", value="", key="add_col_const_val")
                elif val_type == "Sequential Number (1, 2, 3...)":
                    constant_val = st.number_input("Start Number:", value=1, step=1, key="add_col_start_seq")
                elif val_type == "Copy From Existing Column":
                    source_c = st.selectbox("Source Column:", options=list(df.columns), key="add_col_src_col")

            if st.button("Add Column", key="btn_apply_add_col"):
                try:
                    mapped_type = "constant"
                    if "Sequential" in val_type:
                        mapped_type = "sequence"
                    elif "Copy" in val_type:
                        mapped_type = "copy_col"
                    elif "Empty" in val_type:
                        mapped_type = "null"

                    new_df, msg = ColumnOperations.add_column(
                        df, col_name=new_col_name, value_type=mapped_type, value=constant_val, source_col=source_c
                    )
                    SessionManager.update_working_df(new_df, "Add Column", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        # 3. DELETE COLUMNS
        elif col_op_mode == "Delete Columns":
            st.markdown("##### 🗑️ Delete Columns")
            cols_to_del = st.multiselect("Select columns to delete:", options=list(df.columns), key="del_cols_sel")
            if cols_to_del:
                st.warning(f"⚠️ Warning: Deleting {len(cols_to_del)} column(s): {', '.join(cols_to_del)}")
                confirm = st.checkbox("I confirm I want to remove these columns", key="del_cols_confirm")
                if st.button("Delete Selected Columns", type="primary", disabled=not confirm, key="btn_apply_del_cols"):
                    try:
                        new_df, msg = ColumnOperations.delete_columns(df, cols_to_del)
                        SessionManager.update_working_df(new_df, "Delete Columns", msg)
                        st.success(msg)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
            else:
                st.info("Select one or more columns above to delete.")

        # 4. REORDER COLUMNS
        elif col_op_mode == "Reorder Columns":
            st.markdown("##### 🔃 Reorder Columns")
            st.caption("Re-arrange the sequence of columns in the dataset.")
            all_cols = list(df.columns)
            new_ordering = st.multiselect(
                "Arrange column order:",
                options=all_cols,
                default=all_cols,
                help="Select all columns in your desired sequence",
                key="reorder_cols_sel",
            )
            c_actions1, c_actions2 = st.columns(2)
            with c_actions1:
                if st.button("Apply New Column Order", disabled=len(new_ordering) != len(all_cols), key="btn_apply_reorder"):
                    try:
                        new_df, msg = ColumnOperations.reorder_columns(df, new_ordering)
                        SessionManager.update_working_df(new_df, "Reorder Columns", msg)
                        st.success(msg)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
            with c_actions2:
                if st.button("Sort Columns Alphabetically (A-Z)", key="btn_sort_cols_az"):
                    try:
                        sorted_cols = sorted(all_cols)
                        new_df, msg = ColumnOperations.reorder_columns(df, sorted_cols)
                        SessionManager.update_working_df(new_df, "Sort Columns A-Z", "Sorted columns alphabetically")
                        st.success(msg)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

        # 5. MERGE COLUMNS
        elif col_op_mode == "Merge Columns":
            st.markdown("##### 🔗 Merge Columns")
            m1, m2, m3 = st.columns(3)
            with m1:
                merge_srcs = st.multiselect("Columns to merge (in order):", options=list(df.columns), key="merge_src_cols")
            with m2:
                merge_delim = st.text_input("Delimiter / Separator:", value=" ", key="merge_delim_input")
                merge_drop = st.checkbox("Drop source columns after merge", value=False, key="merge_drop_sources")
            with m3:
                merge_target = st.text_input("Target Column Name:", placeholder="e.g. FullName", key="merge_target_name")

            if st.button("Merge Columns", key="btn_apply_merge"):
                try:
                    new_df, msg = ColumnOperations.merge_columns(
                        df, source_cols=merge_srcs, target_col=merge_target, delimiter=merge_delim, drop_sources=merge_drop
                    )
                    SessionManager.update_working_df(new_df, "Merge Columns", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        # 6. SPLIT COLUMN
        elif col_op_mode == "Split Column":
            st.markdown("##### ✂️ Split Column")
            s1, s2, s3 = st.columns(3)
            with s1:
                split_src = st.selectbox("Column to split:", options=list(df.columns), key="split_src_col")
            with s2:
                split_delim = st.text_input("Split Delimiter:", value=" ", key="split_delim_input")
                split_drop = st.checkbox("Drop source column after split", value=False, key="split_drop_source")
            with s3:
                split_names_raw = st.text_input("New Column Names (comma-separated):", placeholder="e.g. Part1, Part2", key="split_names_input")

            if st.button("Split Column", key="btn_apply_split"):
                try:
                    new_names = [x.strip() for x in split_names_raw.split(",") if x.strip()]
                    new_df, msg = ColumnOperations.split_column(
                        df, source_col=split_src, delimiter=split_delim, new_cols=new_names, drop_source=split_drop
                    )
                    SessionManager.update_working_df(new_df, "Split Column", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        # 7. CHANGE DATA TYPES
        elif col_op_mode == "Change Data Types":
            st.markdown("##### 🏷️ Cast Column Data Type")
            t1, t2, t3 = st.columns(3)
            with t1:
                cast_col = st.selectbox("Select column:", options=list(df.columns), key="cast_col_select")
            with t2:
                cast_type = st.selectbox(
                    "Target Data Type:",
                    ["integer", "float", "string", "datetime", "boolean"],
                    key="cast_type_select",
                )
            with t3:
                date_fmt = None
                if cast_type == "datetime":
                    date_fmt = st.text_input("Date Format (optional, e.g. %Y-%m-%d, %d/%m/%Y):", value="", key="cast_date_fmt")
                    if not date_fmt.strip():
                        date_fmt = None

            if st.button("Convert Data Type", key="btn_apply_cast"):
                try:
                    new_df, msg = ColumnOperations.cast_column_type(df, col_name=cast_col, target_type=cast_type, date_format=date_fmt)
                    SessionManager.update_working_df(new_df, "Cast Column Type", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        # 8. REPLACE COLUMN VALUES
        elif col_op_mode == "Replace Column Values":
            st.markdown("##### 🔄 Replace Column Values")
            rep1, rep2 = st.columns(2)
            with rep1:
                rep_col_scope = st.selectbox(
                    "Column Scope:",
                    options=["[All Columns]"] + list(df.columns),
                    key="rep_col_scope",
                )
                rep_target_col = None if rep_col_scope == "[All Columns]" else rep_col_scope
                rep_mode = st.radio("Match Mode:", ["exact", "contains", "regex"], horizontal=True, key="rep_match_mode")

            with rep2:
                rep_find = st.text_input("Find Value (use '[NULL]' to target empty cells):", key="rep_find_val")
                rep_replace = st.text_input("Replace With:", key="rep_replace_val")

            if st.button("Apply Replacement", key="btn_apply_replace"):
                try:
                    new_df, msg = ColumnOperations.replace_values(
                        df, col_name=rep_target_col, find_val=rep_find, replace_val=rep_replace, match_mode=rep_mode
                    )
                    SessionManager.update_working_df(new_df, "Replace Values", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        # 9. CALCULATE COLUMN / FORMULAS
        elif col_op_mode == "Calculate Column / Formula":
            st.markdown("##### 🧮 Create Calculated Column / Apply Formula")
            st.caption(
                "Reference columns inside square brackets `[ColName]`. "
                "Examples: `[Amount] * 1.18`, `[StockOnHand] * [UnitPrice]`, `round([CreditLimit] * 0.1, 2)`"
            )

            calc1, calc2 = st.columns([1, 2])
            with calc1:
                calc_target = st.text_input("Target Column Name:", placeholder="e.g. TotalWithTax", key="calc_target_name")
            with calc2:
                calc_formula = st.text_input("Formula Expression:", placeholder="e.g. [Amount] * 1.18", key="calc_formula_input")

            # Quick formula helpers
            st.markdown("**Quick Inserts:**")
            avail_cols = list(df.columns)
            q_cols = st.columns(min(6, len(avail_cols)))
            for i, c in enumerate(avail_cols[:6]):
                with q_cols[i]:
                    st.code(f"[{c}]")

            if st.button("Evaluate & Apply Formula", key="btn_apply_calc"):
                try:
                    new_df, msg = ColumnOperations.calculate_column(df, target_col=calc_target, formula=calc_formula)
                    SessionManager.update_working_df(new_df, "Calculated Column", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error evaluating formula: {str(e)}")

        # 10. MAP COLUMN VALUES (DICTIONARY)
        elif col_op_mode == "Map Column Values (Dictionary)":
            st.markdown("##### 🗺️ Map Column Values to Another")
            st.caption("Map distinct values in a source column to standard values in a target column.")

            map1, map2 = st.columns(2)
            with map1:
                map_src = st.selectbox("Source Column:", options=list(df.columns), key="map_src_col")
                map_target = st.text_input("Target Column Name (can overwrite source):", value=map_src, key="map_target_name")
                map_default = st.text_input("Default value if unmapped (optional):", value="", key="map_def_val")

            with map2:
                distinct_vals = df[map_src].dropna().unique().tolist()[:10]
                st.caption(f"Top distinct values in `{map_src}` (configure mapping below):")
                user_mapping = {}
                m_subcols = st.columns(2)
                for i, dv in enumerate(distinct_vals):
                    with m_subcols[i % 2]:
                        mapped_v = st.text_input(f"'{dv}' ->", value=str(dv), key=f"map_val_{dv}")
                        if mapped_v != str(dv):
                            user_mapping[str(dv)] = mapped_v

            if st.button("Apply Value Mapping", key="btn_apply_mapping"):
                try:
                    def_val = map_default if map_default.strip() else None
                    new_df, msg = ColumnOperations.map_column_values(
                        df, source_col=map_src, target_col=map_target, mapping=user_mapping, default_val=def_val
                    )
                    SessionManager.update_working_df(new_df, "Map Column Values", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    # =============================================================
    # TAB 2: ROW OPERATIONS
    # =============================================================
    with tab_rows:
        row_op_mode = st.selectbox(
            "Select Row Operation:",
            [
                "Filter Rows",
                "Remove Duplicates",
                "Sort Records",
                "Delete Rows by Index / Selection",
                "Insert New Row",
                "Update Existing Records by Identifier",
            ],
            key="row_op_selector",
        )

        st.markdown("---")

        # 1. FILTER ROWS
        if row_op_mode == "Filter Rows":
            st.markdown("##### 🔍 Filter Rows")
            st.caption("Filter records based on conditional criteria, choosing to keep or drop matching rows.")

            f1, f2, f3, f4 = st.columns(4)
            with f1:
                filter_col = st.selectbox("Column to evaluate:", options=list(df.columns), key="filter_col_sel")
            with f2:
                filter_op = st.selectbox(
                    "Operator:",
                    [
                        "equals",
                        "not_equals",
                        "contains",
                        "not_contains",
                        "starts_with",
                        "ends_with",
                        "greater_than",
                        "greater_equal",
                        "less_than",
                        "less_equal",
                        "is_null",
                        "is_not_null",
                        "in_list",
                    ],
                    key="filter_op_sel",
                )
            with f3:
                filter_val = None
                if filter_op not in ["is_null", "is_not_null"]:
                    filter_val = st.text_input("Comparison Value (comma-separated for in_list):", key="filter_val_input")
            with f4:
                filter_action = st.radio("Action:", ["keep matching rows", "drop matching rows"], key="filter_act_rad")
                action_clean = "keep" if "keep" in filter_action else "drop"

            if st.button("Apply Row Filter", key="btn_apply_filter"):
                try:
                    new_df, msg = RowOperations.filter_rows(
                        df, col_name=filter_col, operator=filter_op, target_val=filter_val, action=action_clean
                    )
                    SessionManager.update_working_df(new_df, "Filter Rows", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        # 2. REMOVE DUPLICATES
        elif row_op_mode == "Remove Duplicates":
            st.markdown("##### 👥 Remove Duplicate Records")
            st.caption("Deduplicate dataset across all columns or based on key identifiers.")

            d1, d2 = st.columns(2)
            with d1:
                dup_subset = st.multiselect(
                    "Key columns to check duplicates on (leave empty to check all columns):",
                    options=list(df.columns),
                    key="dup_subset_cols",
                )
            with d2:
                dup_keep = st.selectbox(
                    "Keep instance:",
                    options=["first", "last", "none (drop all duplicates)"],
                    key="dup_keep_mode",
                )
                keep_clean = "none" if "none" in dup_keep else dup_keep

            if st.button("Remove Duplicates", key="btn_apply_dedup"):
                try:
                    new_df, msg = RowOperations.remove_duplicates(df, subset_cols=dup_subset, keep_mode=keep_clean)
                    SessionManager.update_working_df(new_df, "Remove Duplicates", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        # 3. SORT RECORDS
        elif row_op_mode == "Sort Records":
            st.markdown("##### 📶 Sort Records")
            st.caption("Sort by one or multiple columns in ascending or descending order.")

            s_col1, s_col2 = st.columns(2)
            with s_col1:
                sort_columns = st.multiselect("Columns to sort by (in order):", options=list(df.columns), key="sort_cols_sel")
            with s_col2:
                sort_order = st.selectbox("Ordering:", ["Ascending (A-Z, 0-9)", "Descending (Z-A, 9-0)"], key="sort_order_sel")
                is_asc = "Ascending" in sort_order

            if st.button("Apply Sorting", disabled=not sort_columns, key="btn_apply_sort"):
                try:
                    asc_list = [is_asc] * len(sort_columns)
                    new_df, msg = RowOperations.sort_records(df, sort_cols=sort_columns, ascending_list=asc_list)
                    SessionManager.update_working_df(new_df, "Sort Records", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        # 4. DELETE ROWS BY INDEX / SELECTION
        elif row_op_mode == "Delete Rows by Index / Selection":
            st.markdown("##### 🗑️ Delete Selected Rows")
            del_r1, del_r2 = st.columns(2)
            with del_r1:
                del_mode = st.radio("Selection Method:", ["By Row Index Numbers", "Slice Range (Start to End)"], key="del_r_mode")
                if del_mode == "By Row Index Numbers":
                    indices_str = st.text_input("Row indices to delete (comma-separated, e.g. 0, 3, 5):", key="del_indices_input")
                else:
                    rng_start = st.number_input("Start index:", min_value=0, max_value=max(0, len(df)-1), value=0, key="del_rng_start")
                    rng_end = st.number_input("End index (inclusive):", min_value=0, max_value=max(0, len(df)-1), value=min(5, len(df)-1), key="del_rng_end")

            with del_r2:
                confirm_del_r = st.checkbox("Confirm deletion of selected rows", key="confirm_del_rows")
                if st.button("Delete Rows", type="primary", disabled=not confirm_del_r, key="btn_apply_del_rows"):
                    try:
                        if del_mode == "By Row Index Numbers":
                            indices = [int(x.strip()) for x in indices_str.split(",") if x.strip().isdigit()]
                        else:
                            indices = list(range(int(rng_start), int(rng_end) + 1))

                        new_df, msg = RowOperations.delete_rows_by_indices(df, indices)
                        SessionManager.update_working_df(new_df, "Delete Rows", msg)
                        st.success(msg)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

        # 5. INSERT NEW ROW
        elif row_op_mode == "Insert New Row":
            st.markdown("##### ➕ Insert New Row")
            st.caption("Provide values for each column to append or insert a record.")

            ins1, ins2 = st.columns(2)
            with ins1:
                ins_pos = st.selectbox("Insertion Position:", ["bottom", "top", "specific index"], key="ins_pos_sel")
            with ins2:
                ins_idx = 0
                if ins_pos == "specific index":
                    ins_idx = st.number_input("Insert at index:", min_value=0, max_value=len(df), value=0, key="ins_idx_input")

            # Form fields for each column
            row_inputs = {}
            f_cols = st.columns(min(3, len(df.columns)))
            for i, c in enumerate(df.columns):
                with f_cols[i % min(3, len(df.columns))]:
                    val = st.text_input(f"Column: {c}", key=f"ins_field_{c}")
                    if val.strip():
                        row_inputs[c] = val.strip()

            if st.button("Insert Row", key="btn_apply_insert_row"):
                try:
                    new_df, msg = RowOperations.insert_row(df, row_data=row_inputs, position=ins_pos, index_pos=int(ins_idx))
                    SessionManager.update_working_df(new_df, "Insert Row", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        # 6. UPDATE EXISTING RECORDS BY IDENTIFIER
        elif row_op_mode == "Update Existing Records by Identifier":
            st.markdown("##### 🎯 Update Existing Record(s) by Matching Identifier")
            st.caption("Locate records matching a key column and update specific target values.")

            u1, u2, u3, u4 = st.columns(4)
            with u1:
                u_key_col = st.selectbox("Key Column (Identifier):", options=list(df.columns), key="upd_key_col")
            with u2:
                u_key_val = st.text_input("Matching Key Value:", key="upd_key_val")
            with u3:
                u_target_col = st.selectbox("Target Column to Update:", options=list(df.columns), key="upd_target_col")
            with u4:
                u_new_val = st.text_input("New Value to Assign:", key="upd_new_val")

            if st.button("Update Record(s)", key="btn_apply_update_key"):
                try:
                    new_df, msg = RowOperations.update_record_by_key(
                        df, key_col=u_key_col, key_value=u_key_val, target_col=u_target_col, new_value=u_new_val
                    )
                    SessionManager.update_working_df(new_df, "Update Record by Key", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    # =============================================================
    # TAB 3: DATA CLEANING (PHASE 3)
    # =============================================================
    with tab_clean:
        clean_op_mode = st.selectbox(
            "Select Data Cleaning Operation:",
            [
                "Handle Missing Values / Imputation",
                "Standardise Text & Spacing",
                "Standardise Date Formats",
                "Correct Numerical Formatting",
                "Detect & Treat Outliers",
                "Validate Required Fields",
            ],
            key="clean_op_selector",
        )

        st.markdown("---")

        # 1. HANDLE MISSING VALUES
        if clean_op_mode == "Handle Missing Values / Imputation":
            st.markdown("##### 🧩 Missing Value Treatment & Imputation")
            st.caption("Replace null or empty values across selected fields using statistical or constant methods.")

            m_c1, m_c2, m_c3 = st.columns(3)
            with m_c1:
                miss_cols = st.multiselect("Columns to treat:", options=list(df.columns), key="miss_cols_sel")
            with m_c2:
                miss_strat = st.selectbox(
                    "Imputation Strategy:",
                    [
                        "constant (custom value)",
                        "mean (numeric average)",
                        "median (numeric midpoint)",
                        "mode (most frequent value)",
                        "ffill (forward fill)",
                        "bfill (backward fill)",
                        "drop_rows (remove incomplete rows)",
                    ],
                    key="miss_strat_sel",
                )
                strat_clean = miss_strat.split(" ")[0]
            with m_c3:
                const_input = None
                if strat_clean == "constant":
                    const_input = st.text_input("Constant Value to Fill:", value="Unknown", key="miss_const_val")

            if st.button("Apply Missing Value Treatment", disabled=not miss_cols, key="btn_apply_missing"):
                try:
                    new_df, msg = DataCleaningEngine.impute_missing(
                        df, columns=miss_cols, strategy=strat_clean, constant_value=const_input
                    )
                    SessionManager.update_working_df(new_df, "Impute Missing", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        # 2. STANDARDISE TEXT & SPACING
        elif clean_op_mode == "Standardise Text & Spacing":
            st.markdown("##### 🔤 Standardise Text & Spacing")
            st.caption("Clean up messy string formatting, strip unwanted spaces, and normalize casing.")

            txt1, txt2 = st.columns([1, 2])
            with txt1:
                txt_cols = st.multiselect("Columns to clean:", options=list(df.columns), key="txt_clean_cols")
            with txt2:
                st.markdown("**Select Cleaning Rules:**")
                t_sub1, t_sub2, t_sub3 = st.columns(3)
                with t_sub1:
                    op_trim = st.checkbox("Trim edge spaces", value=True, key="chk_trim")
                    op_collapse = st.checkbox("Collapse multi-spaces", value=True, key="chk_collapse")
                with t_sub2:
                    case_choice = st.radio(
                        "Casing Normalization:",
                        ["Leave casing as-is", "UPPERCASE", "lowercase", "Title Case"],
                        key="rad_casing",
                    )
                with t_sub3:
                    op_punct = st.checkbox("Remove punctuation", value=False, key="chk_punct")
                    op_alphanum = st.checkbox("Alphanumeric only", value=False, key="chk_alphanum")

            if st.button("Apply Text Normalization", disabled=not txt_cols, key="btn_apply_txt_clean"):
                try:
                    selected_ops = []
                    if op_trim:
                        selected_ops.append("trim")
                    if op_collapse:
                        selected_ops.append("remove_extra_spaces")
                    if case_choice == "UPPERCASE":
                        selected_ops.append("uppercase")
                    elif case_choice == "lowercase":
                        selected_ops.append("lowercase")
                    elif case_choice == "Title Case":
                        selected_ops.append("titlecase")
                    if op_alphanum:
                        selected_ops.append("alphanumeric_only")
                    elif op_punct:
                        selected_ops.append("remove_punctuation")

                    new_df, msg = DataCleaningEngine.standardize_text(df, columns=txt_cols, operations=selected_ops)
                    SessionManager.update_working_df(new_df, "Standardise Text", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        # 3. STANDARDISE DATE FORMATS
        elif clean_op_mode == "Standardise Date Formats":
            st.markdown("##### 📅 Standardise Date Formats")
            st.caption("Reconcile mixed date entries (e.g. YYYY-MM-DD mixed with DD/MM/YYYY or Tally YYYYMMDD) into a unified format.")

            dt1, dt2, dt3 = st.columns(3)
            with dt1:
                date_target_col = st.selectbox("Date Column:", options=list(df.columns), key="dt_target_col")
            with dt2:
                target_date_format = st.selectbox(
                    "Target Output Format:",
                    [
                        "YYYY-MM-DD (%Y-%m-%d)",
                        "DD-MM-YYYY (%d-%m-%Y)",
                        "DD/MM/YYYY (%d/%m/%Y)",
                        "MM/DD/YYYY (%m/%d/%Y)",
                        "YYYYMMDD (Tally Format)",
                    ],
                    key="dt_out_fmt",
                )
                fmt_code = "%Y-%m-%d"
                if "DD-MM-YYYY" in target_date_format:
                    fmt_code = "%d-%m-%Y"
                elif "DD/MM/YYYY" in target_date_format:
                    fmt_code = "%d/%m/%Y"
                elif "MM/DD/YYYY" in target_date_format:
                    fmt_code = "%m/%d/%Y"
                elif "Tally" in target_date_format:
                    fmt_code = "%Y%m%d"

            with dt3:
                dayfirst_opt = st.radio("Interpret Ambiguous Dates (e.g. 01/02/2026):", ["Day first (DD/MM)", "Month first (MM/DD)"], key="dt_dayfirst_rad")
                dayfirst_bool = "Day first" in dayfirst_opt

            if st.button("Standardise Dates", key="btn_apply_date_std"):
                try:
                    new_df, msg = DataCleaningEngine.standardize_dates(
                        df, column=date_target_col, target_format=fmt_code, dayfirst=dayfirst_bool
                    )
                    SessionManager.update_working_df(new_df, "Standardise Dates", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        # 4. CORRECT NUMERICAL FORMATTING
        elif clean_op_mode == "Correct Numerical Formatting":
            st.markdown("##### 💲 Correct Numerical Formatting")
            st.caption("Strip currency symbols, commas, percent signs, handle negative (brackets), and round decimals.")

            num1, num2, num3 = st.columns(3)
            with num1:
                num_target_cols = st.multiselect("Numeric Columns:", options=list(df.columns), key="num_clean_cols")
            with num2:
                strip_curr = st.checkbox("Strip currency symbols ($ € £ ₹ ¥) and commas", value=True, key="chk_strip_curr")
                dec_sep = st.selectbox("Decimal Separator in Data:", [". (Period, standard)", ", (Comma, European)"], key="dec_sep_sel")
                dec_clean = "," if "Comma" in dec_sep else "."
            with num3:
                apply_round = st.checkbox("Round to fixed decimal places", value=False, key="chk_apply_round")
                round_n = st.number_input("Decimal places:", min_value=0, max_value=6, value=2, key="num_round_places") if apply_round else None

            if st.button("Clean Numbers", disabled=not num_target_cols, key="btn_apply_num_clean"):
                try:
                    new_df, msg = DataCleaningEngine.clean_numeric_formatting(
                        df, columns=num_target_cols, strip_symbols=strip_curr, decimal_separator=dec_clean, round_decimals=round_n
                    )
                    SessionManager.update_working_df(new_df, "Clean Numeric Format", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        # 5. DETECT & TREAT OUTLIERS
        elif clean_op_mode == "Detect & Treat Outliers":
            st.markdown("##### 📊 Detect & Treat Outliers")
            st.caption("Identify extreme values using IQR or Z-score boundaries and apply capping, flagging, or removal.")

            o1, o2, o3 = st.columns(3)
            with o1:
                out_col = st.selectbox("Numeric Column:", options=list(df.columns), key="outlier_col_sel")
            with o2:
                out_method = st.radio("Detection Metric:", ["IQR (Interquartile Range 1.5x)", "Z-Score (Standard Deviations > 3.0)"], key="out_metric_rad")
                m_code = "iqr" if "IQR" in out_method else "z_score"
            with o3:
                out_action = st.selectbox(
                    "Treatment Action:",
                    [
                        "cap (Winsorize to upper/lower bounds)",
                        "flag (Add boolean flag column)",
                        "replace_null (Set outliers to null)",
                        "drop_rows (Delete outlier rows)",
                    ],
                    key="out_action_sel",
                )
                act_code = out_action.split(" ")[0]

            if st.button("Treat Outliers", key="btn_apply_outliers"):
                try:
                    new_df, msg = DataCleaningEngine.treat_outliers(df, column=out_col, method=m_code, action=act_code)
                    SessionManager.update_working_df(new_df, "Treat Outliers", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        # 6. VALIDATE REQUIRED FIELDS
        elif clean_op_mode == "Validate Required Fields":
            st.markdown("##### 🛡️ Validate Required Fields")
            st.caption("Identify or purge records that are missing mandatory business fields.")

            v1, v2 = st.columns(2)
            with v1:
                req_cols = st.multiselect("Mandatory Columns:", options=list(df.columns), key="req_cols_sel")
            with v2:
                req_act = st.radio("Validation Failure Action:", ["Flag incomplete rows (adds 'has_missing_required')", "Drop incomplete rows"], key="req_act_rad")
                act_str = "drop" if "Drop" in req_act else "flag"

            if st.button("Validate Fields", disabled=not req_cols, key="btn_apply_req_val"):
                try:
                    new_df, msg = DataCleaningEngine.validate_required_fields(df, required_columns=req_cols, action=act_str)
                    SessionManager.update_working_df(new_df, "Validate Required Fields", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")

    # =============================================================
    # TAB 4: RESHAPE & MULTI-DATASET (PHASE 3)
    # =============================================================
    with tab_struct:
        struct_mode = st.selectbox(
            "Select Structural Transformation:",
            [
                "Append / Concatenate Datasets",
                "Join / Merge Datasets",
                "Pivot Data (Long to Wide)",
                "Unpivot / Melt Data (Wide to Long)",
                "Group By & Aggregate",
            ],
            key="struct_op_selector",
        )

        st.markdown("---")

        files_in_session = st.session_state.get("files", {})
        other_files = {fid: f for fid, f in files_in_session.items() if fid != st.session_state.active_file_id}

        # 1. APPEND DATASETS
        if struct_mode == "Append / Concatenate Datasets":
            st.markdown("##### 📑 Append / Concatenate Two Datasets")
            st.caption("Stack rows from another dataset into the active dataset, reconciling column variations.")

            if not other_files:
                st.info("ℹ️ To append datasets, at least two files must be loaded into memory.")
                if st.button("📥 Load sample_customers.csv into memory as secondary dataset", key="btn_load_sec_append"):
                    sample_path = SAMPLES_DIR / "sample_customers.csv"
                    if sample_path.exists():
                        with open(sample_path, "rb") as sf:
                            SessionManager.add_uploaded_file("sample_customers.csv", sf.read())
                        st.success("Loaded secondary dataset! Ready to append.")
                        st.rerun()
            else:
                app1, app2 = st.columns(2)
                with app1:
                    target_sec_fid = st.selectbox(
                        "Select dataset to append:",
                        options=list(other_files.keys()),
                        format_func=lambda x: other_files[x]["filename"],
                        key="append_sec_file_sel",
                    )
                    add_source_col = st.checkbox("Add '_source_dataset' indicator column", value=True, key="chk_app_source_col")

                with app2:
                    sec_file = other_files[target_sec_fid]
                    sec_df = sec_file.get("parsed_data", {}).get("active_df")
                    if sec_df is not None:
                        st.caption(f"Secondary dataset: **{sec_file['filename']}** ({len(sec_df)} rows, {len(sec_df.columns)} cols)")
                        st.dataframe(sec_df.head(3), use_container_width=True)

                if st.button("Append Datasets", key="btn_apply_append"):
                    try:
                        sec_df = other_files[target_sec_fid]["parsed_data"]["active_df"]
                        new_df, msg = StructuralTransformationEngine.append_datasets(
                            df, sec_df,
                            source1_name=active_file["filename"],
                            source2_name=other_files[target_sec_fid]["filename"],
                            add_source_tag=add_source_col,
                        )
                        SessionManager.update_working_df(new_df, "Append Datasets", msg)
                        st.success(msg)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {str(e)}")

        # 2. JOIN / MERGE DATASETS
        elif struct_mode == "Join / Merge Datasets":
            st.markdown("##### 🔗 Join / Merge Two Datasets on Key Column")
            st.caption("Merge attributes from another loaded dataset based on matching identifier columns.")

            if not other_files:
                st.info("ℹ️ To join datasets, at least two files must be loaded into memory.")
                if st.button("📥 Load sample_customers.csv into memory as secondary dataset", key="btn_load_sec_join"):
                    sample_path = SAMPLES_DIR / "sample_customers.csv"
                    if sample_path.exists():
                        with open(sample_path, "rb") as sf:
                            SessionManager.add_uploaded_file("sample_customers.csv", sf.read())
                        st.success("Loaded secondary dataset! Ready to join.")
                        st.rerun()
            else:
                j1, j2, j3, j4 = st.columns(4)
                with j1:
                    join_sec_fid = st.selectbox(
                        "Secondary dataset to join:",
                        options=list(other_files.keys()),
                        format_func=lambda x: other_files[x]["filename"],
                        key="join_sec_file_sel",
                    )
                with j2:
                    join_type = st.selectbox("Join Type:", ["inner", "left", "right", "outer"], key="join_type_sel")

                sec_df = other_files[join_sec_fid].get("parsed_data", {}).get("active_df")
                sec_cols = list(sec_df.columns) if sec_df is not None and isinstance(sec_df, pd.DataFrame) else []
                with j3:
                    left_key = st.selectbox("Key in Primary Dataset:", options=list(df.columns), key="join_left_key")
                with j4:
                    right_key = st.selectbox("Key in Secondary Dataset:", options=sec_cols, key="join_right_key")

                if st.button("Execute Join", disabled=(not sec_cols), key="btn_apply_join"):
                    try:
                        if sec_df is None or not isinstance(sec_df, pd.DataFrame):
                            raise ValueError("Secondary dataset is empty or not in tabular format.")
                        new_df, msg = StructuralTransformationEngine.join_datasets(
                            df, sec_df, left_on=left_key, right_on=right_key, how=join_type
                        )
                        SessionManager.update_working_df(new_df, f"Join ({join_type.upper()})", msg)
                        st.success(msg)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error executing join: {str(e)}")

        # 3. PIVOT DATA (LONG TO WIDE)
        elif struct_mode == "Pivot Data (Long to Wide)":
            st.markdown("##### 🔄 Pivot Data (Long to Wide Format)")
            st.caption("Reshape records into columns based on unique category values.")

            p1, p2, p3, p4 = st.columns(4)
            with p1:
                piv_idx = st.multiselect("Row Index Column(s):", options=list(df.columns), key="piv_idx_sel")
            with p2:
                piv_col = st.selectbox("Column to spread into Headers:", options=list(df.columns), key="piv_col_sel")
            with p3:
                piv_val = st.selectbox("Values Column to aggregate:", options=list(df.columns), key="piv_val_sel")
            with p4:
                piv_agg = st.selectbox("Aggregation Function:", ["sum", "mean", "count", "min", "max", "first"], key="piv_agg_sel")

            if st.button("Pivot Dataset", disabled=not piv_idx, key="btn_apply_pivot"):
                try:
                    new_df, msg = StructuralTransformationEngine.pivot_dataset(
                        df, index_cols=piv_idx, columns_col=piv_col, values_col=piv_val, aggfunc=piv_agg
                    )
                    SessionManager.update_working_df(new_df, "Pivot Dataset", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error pivoting dataset: {str(e)}")

        # 4. UNPIVOT / MELT DATA (WIDE TO LONG)
        elif struct_mode == "Unpivot / Melt Data (Wide to Long)":
            st.markdown("##### ↕️ Unpivot / Melt Data (Wide to Long Format)")
            st.caption("Convert multi-column attributes into key-value rows.")

            u_col1, u_col2, u_col3, u_col4 = st.columns(4)
            with u_col1:
                unpiv_ids = st.multiselect("Identifier Column(s) (Keep as Rows):", options=list(df.columns), key="unpiv_ids_sel")
            with u_col2:
                unpiv_vals = st.multiselect(
                    "Columns to Unpivot (Values):",
                    options=[c for c in df.columns if c not in unpiv_ids],
                    key="unpiv_vals_sel",
                )
            with u_col3:
                var_header = st.text_input("Name for Variable Column:", value="Attribute", key="unpiv_var_name")
            with u_col4:
                val_header = st.text_input("Name for Value Column:", value="Value", key="unpiv_val_name")

            if st.button("Unpivot Dataset", disabled=not unpiv_vals, key="btn_apply_unpivot"):
                try:
                    new_df, msg = StructuralTransformationEngine.unpivot_dataset(
                        df, id_vars=unpiv_ids, value_vars=unpiv_vals, var_name=var_header, value_name=val_header
                    )
                    SessionManager.update_working_df(new_df, "Unpivot Dataset", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error unpivoting dataset: {str(e)}")

        # 5. GROUP BY & AGGREGATE
        elif struct_mode == "Group By & Aggregate":
            st.markdown("##### 📊 Group & Aggregate Data")
            st.caption("Group dataset by categories and compute summary metrics.")

            g1, g2 = st.columns(2)
            with g1:
                grp_cols = st.multiselect("Group By Columns:", options=list(df.columns), key="grp_cols_sel")
            with g2:
                agg_target_cols = st.multiselect(
                    "Columns to Aggregate:",
                    options=[c for c in df.columns if c not in grp_cols],
                    key="grp_agg_cols_sel",
                )

            agg_spec = {}
            if agg_target_cols:
                st.markdown("**Select Aggregation Function per Column:**")
                a_cols = st.columns(min(4, len(agg_target_cols)))
                for i, col in enumerate(agg_target_cols):
                    with a_cols[i % min(4, len(agg_target_cols))]:
                        fn = st.selectbox(f"Fn for '{col}':", ["sum", "mean", "count", "min", "max", "median"], key=f"agg_fn_{col}")
                        agg_spec[col] = fn

            if st.button("Group & Aggregate", disabled=(not grp_cols or not agg_spec), key="btn_apply_groupby"):
                try:
                    new_df, msg = StructuralTransformationEngine.group_and_aggregate(
                        df, group_by_cols=grp_cols, agg_spec=agg_spec
                    )
                    SessionManager.update_working_df(new_df, "Group & Aggregate", msg)
                    st.success(msg)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error grouping dataset: {str(e)}")

    # =============================================================
    # TAB 5: CHANGE HISTORY & AUDIT
    # =============================================================
    with tab_history:
        st.markdown("##### 📜 Operational Change History & Audit Log")
        history = st.session_state.get("change_history", [])
        if history:
            h_df = pd.DataFrame(history)
            st.dataframe(h_df, use_container_width=True, hide_index=True)
        else:
            st.info("No transformation steps recorded yet.")

    st.markdown("---")

    # -------------------------------------------------------------
    # LIVE WORKING DATASET PREVIEW
    # -------------------------------------------------------------
    st.markdown("### 👁️ Live Working Dataset Preview")
    prev_c1, prev_c2 = st.columns([4, 2])
    with prev_c1:
        st.caption(f"Showing live state: **{len(df)}** rows | **{len(df.columns)}** columns | In-RAM copy")
    with prev_c2:
        search_kw = st.text_input("🔍 Quick Search Rows:", placeholder="Type to filter preview...", key="cust_live_search")

    preview_slice = df
    if search_kw.strip():
        mask = preview_slice.astype(str).apply(lambda row: row.str.contains(search_kw, case=False).any(), axis=1)
        preview_slice = preview_slice[mask]

    st.dataframe(preview_slice.head(50), use_container_width=True)


if __name__ == "__main__":
    show()
