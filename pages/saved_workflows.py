"""
Universal Data Customisation & Automation Studio
Page 11: Saved Workflows & Recipe Catalog
Repository of pre-bundled and custom-built workflow recipes.
Supports 1-click pipeline execution, schema import/export, and builder integration.
"""
import json
import streamlit as st
import pandas as pd

from config import SAMPLES_DIR, BASE_DIR
from utils.ui_components import (
    inject_custom_css,
    render_page_header,
    render_active_file_banner,
    render_metric_card,
)
from utils.session_manager import SessionManager
from core.workflow_engine import (
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowExecutionResult,
)


def show():
    inject_custom_css()
    SessionManager.init_session()
    WorkflowEngine.ensure_presets_on_disk()

    render_page_header(
        title="Saved Workflows & Reusable Recipes",
        description="Catalog of automated data transformation pipelines and reusable processing blueprints. Execute workflows with 1 click on any dataset.",
        badge="Phase 7 Active",
    )

    render_active_file_banner()

    active_df = SessionManager.get_active_df()
    active_meta = SessionManager.get_active_file_metadata()

    # -------------------------------------------------------------
    # RECIPE IMPORTER ACCORDION
    # -------------------------------------------------------------
    with st.expander("📥 Import New Workflow Recipe (.json)", expanded=False):
        uploaded_recipe = st.file_uploader(
            "Upload workflow JSON recipe:",
            type=["json"],
            key="sw_upload_json",
            help="Upload a previously exported workflow definition file.",
        )
        if uploaded_recipe is not None:
            try:
                recipe_str = uploaded_recipe.read().decode("utf-8")
                imported_wf = WorkflowDefinition.from_json(recipe_str)
                st.success(f"Successfully parsed recipe: **{imported_wf.name}** ({len(imported_wf.steps)} steps)")
                if st.button("💾 Save Imported Recipe to Catalog", type="primary", key="sw_btn_save_imported"):
                    WorkflowEngine.save_workflow_to_disk(imported_wf)
                    st.toast(f"Saved {imported_wf.name} to catalog!", icon="✅")
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to parse recipe JSON: {e}")

    st.markdown("---")

    # -------------------------------------------------------------
    # RECIPE CATALOG & SEARCH
    # -------------------------------------------------------------
    presets = WorkflowEngine.get_preset_workflows()
    disk_workflows = WorkflowEngine.list_disk_workflows()

    # Combine preset and user workflows, avoiding duplicate IDs
    all_workflows_map = {}
    for p in presets:
        all_workflows_map[p.workflow_id] = (p, "System Preset")
    for dw in disk_workflows:
        if dw.workflow_id not in all_workflows_map:
            all_workflows_map[dw.workflow_id] = (dw, "User Custom")

    c_search, c_filter = st.columns([3, 1])
    with c_search:
        search_query = st.text_input("🔍 Search Workflows & Tags:", placeholder="e.g. sales, deduplicate, audit, crm...", key="sw_search")
    with c_filter:
        type_filter = st.selectbox("Category Filter:", options=["All Recipes", "System Presets", "User Custom"], key="sw_filter")

    filtered_workflows = []
    for wid, (wf, origin) in all_workflows_map.items():
        if type_filter == "System Presets" and origin != "System Preset":
            continue
        if type_filter == "User Custom" and origin != "User Custom":
            continue
        if search_query:
            q = search_query.lower()
            text_match = q in wf.name.lower() or q in wf.description.lower() or any(q in t.lower() for t in wf.tags)
            if not text_match:
                continue
        filtered_workflows.append((wf, origin))

    st.markdown(f"### 📚 Available Recipes ({len(filtered_workflows)})")

    if not filtered_workflows:
        st.info("No workflows match your search query.")
        return

    for wf, origin in filtered_workflows:
        is_preset = (origin == "System Preset")
        badge_color = "#3B82F6" if is_preset else "#10B981"

        with st.container(border=True):
            r_c1, r_c2 = st.columns([3, 1.2])

            with r_c1:
                st.markdown(f"#### {wf.name}")
                st.caption(f"{wf.description}")
                tags_str = " ".join([f"`#{t}`" for t in wf.tags])
                st.markdown(f"**Origin:** <span style='background-color:{badge_color}22; color:{badge_color}; padding:2px 8px; border-radius:10px; font-size:12px; font-weight:600;'>{origin}</span> | **Version:** `{wf.version}` | **Steps:** `{len(wf.steps)}` | {tags_str}", unsafe_allow_html=True)

                # Expandable step sequence preview
                with st.expander(f"📋 View Pipeline Steps ({len(wf.steps)} operations)"):
                    for s_idx, step in enumerate(wf.steps):
                        icon = {
                            "column_ops": "📊",
                            "row_ops": "📑",
                            "data_cleaning": "🧹",
                            "transformations": "🔄",
                            "validation": "🛡️",
                        }.get(step.category, "⚙️")
                        st.markdown(f"**{s_idx + 1}. {icon} {step.name}** (`{step.operation}`)")
                        if step.params:
                            st.caption(f"Params: `{json.dumps(step.params)[:100]}`")

            with r_c2:
                st.write("")
                # 1-Click Execution on Active Dataset
                if active_df is not None:
                    if st.button("⚡ Apply to Active Data", key=f"sw_btn_apply_{wf.workflow_id}", type="primary", use_container_width=True):
                        with st.spinner(f"Executing '{wf.name}'..."):
                            result = WorkflowEngine.execute_workflow(active_df, wf)
                            if result.is_success:
                                SessionManager.update_working_df(
                                    result.final_df,
                                    action_name=f"Recipe: {wf.name}",
                                    description=f"Applied {result.successful_steps} steps in {result.total_duration_ms:.1f}ms",
                                )
                                st.success(f"Applied recipe successfully in {result.total_duration_ms:.1f}ms! Dataset updated.")
                                st.rerun()
                            else:
                                st.error(f"Recipe execution encountered {result.failed_steps} error(s). Review in Workflow Builder.")
                else:
                    st.caption("Select a dataset in the workspace to run this workflow.")

                # Open in Workflow Builder
                if st.button("🛠️ Open in Builder", key=f"sw_btn_edit_{wf.workflow_id}", use_container_width=True):
                    st.session_state.current_workflow = WorkflowDefinition.from_dict(wf.to_dict())
                    st.session_state.pipeline_execution_result = None
                    st.toast(f"Loaded '{wf.name}' into Workflow Builder!", icon="🛠️")
                    st.switch_page("pages/workflow_builder.py")

                # Export JSON
                wf_json = wf.to_json(indent=2)
                st.download_button(
                    label="📥 Export Recipe",
                    data=wf_json,
                    file_name=f"{wf.workflow_id}.json",
                    mime="application/json",
                    use_container_width=True,
                    key=f"sw_btn_dl_{wf.workflow_id}",
                )

                # Delete (only for user custom workflows)
                if not is_preset:
                    if st.button("🗑️ Delete Recipe", key=f"sw_btn_del_{wf.workflow_id}", use_container_width=True):
                        WorkflowEngine.delete_workflow_from_disk(wf.workflow_id)
                        st.toast(f"Deleted recipe: {wf.name}", icon="🗑️")
                        st.rerun()


if __name__ == "__main__":
    show()
