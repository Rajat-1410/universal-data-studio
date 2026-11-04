"""
Unit Tests for Universal Workflow Engine (Phase 7)
Validates step execution, pipeline chaining, telemetry logging, error recovery,
JSON serialization, and disk persistence.
"""
import json
import pytest
import pandas as pd
import numpy as np

from core.workflow_engine import (
    WorkflowStep,
    WorkflowDefinition,
    WorkflowEngine,
    StepExecutionLog,
    WorkflowExecutionResult,
)


@pytest.fixture
def sample_sales_df():
    """Generates a sample sales DataFrame for testing pipelines."""
    return pd.DataFrame({
        "OrderID": [101, 102, 103, 104, 105, 105],
        "Customer": [" acme corp ", "globex inc", "initech", "hooli", "pied piper", "pied piper"],
        "Region": ["North", "South", "East", "West", "North", "North"],
        "Amount": ["$1,000.50", "2500.00", "€150.75", "4,200", "(500)", "1,000"],
        "OrderDate": ["2026-01-15", "16/01/2026", "20260117", "2026-01-18", "19-01-2026", "2026-01-19"],
    })


def test_workflow_step_serialization():
    step = WorkflowStep(
        step_id="step1",
        name="Rename Customer",
        category="column_ops",
        operation="rename_columns",
        params={"mapping": {"Customer": "Client"}},
    )
    data = step.to_dict()
    assert data["step_id"] == "step1"
    assert data["category"] == "column_ops"

    rebuilt = WorkflowStep.from_dict(data)
    assert rebuilt.name == "Rename Customer"
    assert rebuilt.params["mapping"] == {"Customer": "Client"}


def test_workflow_definition_manipulation():
    wf = WorkflowDefinition(name="Test Pipeline")
    s1 = WorkflowStep(name="Step 1", category="column_ops", operation="rename_columns")
    s2 = WorkflowStep(name="Step 2", category="row_ops", operation="remove_duplicates")
    s3 = WorkflowStep(name="Step 3", category="validation", operation="assert_min_rows")

    wf.add_step(s1)
    wf.add_step(s2)
    wf.add_step(s3)
    assert len(wf.steps) == 3

    # Move step 0 to step 2
    wf.move_step(0, 2)
    assert wf.steps[0].name == "Step 2"
    assert wf.steps[2].name == "Step 1"

    # Remove step
    wf.remove_step(1)
    assert len(wf.steps) == 2

    # JSON roundtrip
    json_str = wf.to_json()
    wf_loaded = WorkflowDefinition.from_json(json_str)
    assert wf_loaded.name == "Test Pipeline"
    assert len(wf_loaded.steps) == 2


def test_execute_single_step(sample_sales_df):
    step = WorkflowStep(
        name="Clean Numeric Amount",
        category="data_cleaning",
        operation="clean_numeric_formatting",
        params={"columns": ["Amount"], "strip_symbols": True},
    )
    df_res, msg = WorkflowEngine.execute_single_step(sample_sales_df, step)
    assert pd.api.types.is_numeric_dtype(df_res["Amount"])
    assert "Cleaned numeric formatting" in msg


def test_execute_pipeline_chaining(sample_sales_df):
    wf = WorkflowDefinition(name="Full Sales Pipeline")

    # Step 1: Clean text
    wf.add_step(WorkflowStep(
        name="Trim Customer Names",
        category="data_cleaning",
        operation="standardize_text",
        params={"columns": ["Customer"], "operations": ["trim", "titlecase"]},
    ))

    # Step 2: Clean numeric
    wf.add_step(WorkflowStep(
        name="Clean Amount",
        category="data_cleaning",
        operation="clean_numeric_formatting",
        params={"columns": ["Amount"], "strip_symbols": True},
    ))

    # Step 3: Remove duplicate OrderID
    wf.add_step(WorkflowStep(
        name="Deduplicate by OrderID",
        category="row_ops",
        operation="remove_duplicates",
        params={"subset_cols": ["OrderID"], "keep_mode": "first"},
    ))

    # Step 4: Calculate Column
    wf.add_step(WorkflowStep(
        name="Calculate Tax",
        category="column_ops",
        operation="calculate_column",
        params={"target_col": "TotalWithTax", "formula": "[Amount] * 1.18"},
    ))

    # Step 5: Validation
    wf.add_step(WorkflowStep(
        name="Validate Unique OrderID",
        category="validation",
        operation="assert_unique_key",
        params={"columns": ["OrderID"]},
    ))

    result = WorkflowEngine.execute_workflow(sample_sales_df, wf)

    assert result.is_success is True
    assert result.total_steps == 5
    assert result.successful_steps == 5
    assert result.failed_steps == 0
    assert "TotalWithTax" in result.final_df.columns
    # 6 rows originally, 1 duplicate removed -> 5 rows remaining
    assert len(result.final_df) == 5
    assert result.final_df["Customer"].iloc[0] == "Acme Corp"


def test_execute_pipeline_with_disabled_step(sample_sales_df):
    wf = WorkflowDefinition(name="Test Disabled Step")
    wf.add_step(WorkflowStep(
        name="Disabled Step",
        category="column_ops",
        operation="delete_columns",
        params={"columns": ["Region"]},
        enabled=False,
    ))
    wf.add_step(WorkflowStep(
        name="Keep Step",
        category="column_ops",
        operation="rename_columns",
        params={"mapping": {"Region": "SalesRegion"}},
        enabled=True,
    ))

    res = WorkflowEngine.execute_workflow(sample_sales_df, wf)
    assert res.skipped_steps == 1
    assert res.successful_steps == 1
    assert "SalesRegion" in res.final_df.columns


def test_execute_pipeline_error_handling(sample_sales_df):
    wf = WorkflowDefinition(name="Failing Pipeline")

    # Step 1: Valid
    wf.add_step(WorkflowStep(
        name="Valid Rename",
        category="column_ops",
        operation="rename_columns",
        params={"mapping": {"Region": "SalesRegion"}},
    ))

    # Step 2: Invalid (non-existent column)
    wf.add_step(WorkflowStep(
        name="Invalid Calculation",
        category="column_ops",
        operation="calculate_column",
        params={"target_col": "Total", "formula": "[NonExistentCol] * 2"},
    ))

    # Step 3: Following Step
    wf.add_step(WorkflowStep(
        name="Following Step",
        category="row_ops",
        operation="remove_duplicates",
    ))

    # Test stop_on_error = True
    res_stop = WorkflowEngine.execute_workflow(sample_sales_df, wf, stop_on_error=True)
    assert res_stop.is_success is False
    assert res_stop.failed_steps == 1
    assert res_stop.skipped_steps == 1  # Step 3 skipped because of stop_on_error
    assert res_stop.successful_steps == 1

    # Test stop_on_error = False
    res_cont = WorkflowEngine.execute_workflow(sample_sales_df, wf, stop_on_error=False)
    assert res_cont.is_success is False
    assert res_cont.failed_steps == 1
    assert res_cont.successful_steps == 2  # Step 1 and Step 3 executed


def test_preset_workflows():
    presets = WorkflowEngine.get_preset_workflows()
    assert len(presets) >= 4
    preset_ids = [p.workflow_id for p in presets]
    assert "preset_audit_dedup" in preset_ids
    assert "preset_sales_tax_calc" in preset_ids


def test_disk_save_and_load(tmp_path):
    wf = WorkflowDefinition(name="Test Disk Recipe", tags=["test"])
    wf.add_step(WorkflowStep(name="Step A", category="row_ops", operation="remove_duplicates"))

    saved_path = WorkflowEngine.save_workflow_to_disk(wf, filename="test_recipe_tmp.json")
    assert saved_path.exists()

    loaded_wf = WorkflowEngine.load_workflow_from_disk(saved_path)
    assert loaded_wf.name == "Test Disk Recipe"
    assert len(loaded_wf.steps) == 1

    # Clean up disk file
    saved_path.unlink()
