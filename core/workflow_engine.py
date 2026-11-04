"""
Universal Workflow Engine
Manages sequential execution of custom transformation steps, pipeline chaining,
intermediate step previews, JSON recipe serialization/deserialization, and preset workflows.
"""
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
import numpy as np

from config import BASE_DIR
from core.transformations import ColumnOperations, RowOperations, StructuralTransformationEngine
from core.data_cleaning import DataCleaningEngine


WORKFLOWS_DIR = BASE_DIR / "workflows"
WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class WorkflowStep:
    """Individual transformation step in a workflow pipeline."""
    step_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "New Step"
    category: str = "column_ops"  # column_ops, row_ops, data_cleaning, transformations, validation
    operation: str = "rename_columns"
    params: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowStep":
        return cls(
            step_id=data.get("step_id", str(uuid.uuid4())[:8]),
            name=data.get("name", "Untitled Step"),
            category=data.get("category", "column_ops"),
            operation=data.get("operation", "rename_columns"),
            params=data.get("params", {}),
            enabled=data.get("enabled", True),
        )


@dataclass
class StepExecutionLog:
    """Execution telemetry and snapshot for a single pipeline step."""
    step_id: str
    step_num: int
    name: str
    category: str
    operation: str
    status: str  # "SUCCESS", "FAILED", "SKIPPED"
    message: str
    input_rows: int
    output_rows: int
    input_cols: int
    output_cols: int
    duration_ms: float
    error_details: Optional[str] = None
    preview_df: Optional[pd.DataFrame] = None


@dataclass
class WorkflowExecutionResult:
    """Aggregated output of a workflow execution run."""
    workflow_id: str
    workflow_name: str
    is_success: bool
    total_steps: int
    successful_steps: int
    failed_steps: int
    skipped_steps: int
    total_duration_ms: float
    initial_df: pd.DataFrame
    final_df: pd.DataFrame
    logs: List[StepExecutionLog] = field(default_factory=list)


@dataclass
class WorkflowDefinition:
    """Complete workflow recipe with metadata and sequential step chain."""
    workflow_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = "Custom Data Pipeline"
    description: str = "Sequential data manipulation workflow"
    version: str = "1.0.0"
    created_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    updated_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    tags: List[str] = field(default_factory=lambda: ["custom"])
    steps: List[WorkflowStep] = field(default_factory=list)

    def add_step(self, step: WorkflowStep) -> None:
        self.steps.append(step)
        self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def remove_step(self, step_idx: int) -> bool:
        if 0 <= step_idx < len(self.steps):
            self.steps.pop(step_idx)
            self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return True
        return False

    def move_step(self, from_idx: int, to_idx: int) -> bool:
        if 0 <= from_idx < len(self.steps) and 0 <= to_idx < len(self.steps):
            step = self.steps.pop(from_idx)
            self.steps.insert(to_idx, step)
            self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
            "steps": [s.to_dict() for s in self.steps],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowDefinition":
        steps = [WorkflowStep.from_dict(s) for s in data.get("steps", [])]
        return cls(
            workflow_id=data.get("workflow_id", str(uuid.uuid4())[:8]),
            name=data.get("name", "Custom Workflow"),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            created_at=data.get("created_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            updated_at=data.get("updated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            tags=data.get("tags", ["custom"]),
            steps=steps,
        )

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> "WorkflowDefinition":
        return cls.from_dict(json.loads(json_str))


class WorkflowEngine:
    """Core workflow execution engine supporting step execution and chaining."""

    # -------------------------------------------------------------
    # STEP EXECUTION DISPATCHER
    # -------------------------------------------------------------
    @classmethod
    def execute_single_step(cls, df: pd.DataFrame, step: WorkflowStep) -> Tuple[pd.DataFrame, str]:
        """
        Executes a single workflow step against a DataFrame.
        Returns the transformed DataFrame and a human-readable status message.
        """
        p = step.params
        op = step.operation

        # --- A. COLUMN OPERATIONS ---
        if step.category == "column_ops":
            if op == "rename_columns":
                mapping = p.get("mapping", {})
                return ColumnOperations.rename_columns(df, mapping)
            elif op == "add_column":
                return ColumnOperations.add_column(
                    df,
                    col_name=p.get("col_name", "new_col"),
                    mode=p.get("mode", "constant"),
                    constant_val=p.get("constant_val", ""),
                    source_col=p.get("source_col"),
                    seq_start=int(p.get("seq_start", 1)),
                )
            elif op == "delete_columns":
                return ColumnOperations.delete_columns(df, cols_to_delete=p.get("columns", []))
            elif op == "reorder_columns":
                return ColumnOperations.reorder_columns(df, new_order=p.get("columns", []))
            elif op == "merge_columns":
                return ColumnOperations.merge_columns(
                    df,
                    cols_to_merge=p.get("cols_to_merge", []),
                    target_col=p.get("target_col", "merged_col"),
                    separator=p.get("separator", " "),
                    drop_sources=bool(p.get("drop_sources", False)),
                )
            elif op == "split_column":
                return ColumnOperations.split_column(
                    df,
                    source_col=p.get("source_col", ""),
                    delimiter=p.get("delimiter", ","),
                    new_cols=p.get("new_cols", []),
                    drop_source=bool(p.get("drop_source", False)),
                )
            elif op == "cast_column_type":
                return ColumnOperations.cast_column_type(
                    df,
                    col_name=p.get("col_name", ""),
                    target_type=p.get("target_type", "string"),
                    date_format=p.get("date_format"),
                )
            elif op == "replace_values":
                return ColumnOperations.replace_values(
                    df,
                    col_name=p.get("col_name"),
                    find_val=p.get("find_val", ""),
                    replace_val=p.get("replace_val", ""),
                    match_mode=p.get("match_mode", "exact"),
                    use_regex=bool(p.get("use_regex", False)),
                )
            elif op == "calculate_column":
                return ColumnOperations.calculate_column(
                    df,
                    target_col=p.get("target_col", "calculated"),
                    formula=p.get("formula", ""),
                )
            elif op == "map_column_values":
                return ColumnOperations.map_column_values(
                    df,
                    source_col=p.get("source_col", ""),
                    target_col=p.get("target_col", "mapped_col"),
                    mapping=p.get("mapping", {}),
                    default_val=p.get("default_val"),
                )
            else:
                raise ValueError(f"Unknown column operation '{op}'")

        # --- B. ROW OPERATIONS ---
        elif step.category == "row_ops":
            if op == "filter_rows":
                return RowOperations.filter_rows(
                    df,
                    col_name=p.get("col_name", ""),
                    operator=p.get("operator", "equals"),
                    target_val=p.get("target_val"),
                    action=p.get("action", "keep"),
                )
            elif op == "delete_rows_by_indices":
                return RowOperations.delete_rows_by_indices(df, indices=p.get("indices", []))
            elif op == "remove_duplicates":
                return RowOperations.remove_duplicates(
                    df,
                    subset_cols=p.get("subset_cols"),
                    keep_mode=p.get("keep_mode", "first"),
                )
            elif op == "sort_records":
                return RowOperations.sort_records(
                    df,
                    sort_cols=p.get("sort_cols", []),
                    ascending_list=p.get("ascending_list", [True]),
                    na_position=p.get("na_position", "last"),
                )
            elif op == "select_records":
                return RowOperations.select_records(
                    df,
                    mode=p.get("mode", "head"),
                    count=int(p.get("count", 10)),
                )
            else:
                raise ValueError(f"Unknown row operation '{op}'")

        # --- C. DATA CLEANING ---
        elif step.category == "data_cleaning":
            if op == "impute_missing":
                return DataCleaningEngine.impute_missing(
                    df,
                    columns=p.get("columns", []),
                    strategy=p.get("strategy", "constant"),
                    constant_value=p.get("constant_value"),
                )
            elif op == "standardize_text":
                return DataCleaningEngine.standardize_text(
                    df,
                    columns=p.get("columns", []),
                    operations=p.get("operations", ["trim"]),
                )
            elif op == "standardize_dates":
                return DataCleaningEngine.standardize_dates(
                    df,
                    column=p.get("column", ""),
                    target_format=p.get("target_format", "%Y-%m-%d"),
                    dayfirst=p.get("dayfirst"),
                )
            elif op == "clean_numeric_formatting":
                return DataCleaningEngine.clean_numeric_formatting(
                    df,
                    columns=p.get("columns", []),
                    strip_symbols=bool(p.get("strip_symbols", True)),
                    decimal_separator=p.get("decimal_separator", "."),
                    round_decimals=p.get("round_decimals"),
                )
            elif op == "treat_outliers":
                return DataCleaningEngine.treat_outliers(
                    df,
                    column=p.get("column", ""),
                    method=p.get("method", "iqr"),
                    action=p.get("action", "cap"),
                    multiplier=float(p.get("multiplier", 1.5)),
                    z_threshold=float(p.get("z_threshold", 3.0)),
                )
            elif op == "validate_required_fields":
                return DataCleaningEngine.validate_required_fields(
                    df,
                    required_columns=p.get("required_columns", []),
                    action=p.get("action", "flag"),
                )
            else:
                raise ValueError(f"Unknown data cleaning operation '{op}'")

        # --- D. STRUCTURAL TRANSFORMATIONS ---
        elif step.category == "transformations":
            if op == "group_and_aggregate":
                return StructuralTransformationEngine.group_and_aggregate(
                    df,
                    group_by_cols=p.get("group_by_cols", []),
                    agg_spec=p.get("agg_spec", {}),
                )
            elif op == "pivot_dataset":
                return StructuralTransformationEngine.pivot_dataset(
                    df,
                    index_cols=p.get("index_cols", []),
                    columns_col=p.get("columns_col", ""),
                    values_col=p.get("values_col", ""),
                    aggfunc=p.get("aggfunc", "sum"),
                )
            elif op == "unpivot_dataset":
                return StructuralTransformationEngine.unpivot_dataset(
                    df,
                    id_vars=p.get("id_vars", []),
                    value_vars=p.get("value_vars", []),
                    var_name=p.get("var_name", "Attribute"),
                    value_name=p.get("value_name", "Value"),
                )
            else:
                raise ValueError(f"Unknown structural transformation '{op}'")

        # --- E. VALIDATION RULES ---
        elif step.category == "validation":
            if op == "assert_columns_exist":
                missing = [c for c in p.get("columns", []) if c not in df.columns]
                if missing:
                    raise AssertionError(f"Validation failed: Required column(s) missing: {missing}")
                return df, f"Validated that required columns exist: {p.get('columns', [])}"
            elif op == "assert_no_nulls":
                cols = p.get("columns", [])
                null_cols = [c for c in cols if c in df.columns and df[c].isna().sum() > 0]
                if null_cols:
                    raise AssertionError(f"Validation failed: Column(s) contain nulls: {null_cols}")
                return df, f"Validated that specified columns contain 0 nulls: {cols}"
            elif op == "assert_unique_key":
                cols = p.get("columns", [])
                if not cols:
                    raise AssertionError("No columns specified for uniqueness validation.")
                dups = int(df.duplicated(subset=cols).sum())
                if dups > 0:
                    raise AssertionError(f"Validation failed: {dups} duplicate records found for keys: {cols}")
                return df, f"Validated 100% unique primary key: {cols}"
            elif op == "assert_min_rows":
                min_r = int(p.get("min_rows", 1))
                if len(df) < min_r:
                    raise AssertionError(f"Validation failed: DataFrame has {len(df)} rows, minimum required is {min_r}")
                return df, f"Validated row count: {len(df)} >= {min_r}"
            else:
                raise ValueError(f"Unknown validation operation '{op}'")

        else:
            raise ValueError(f"Unknown step category '{step.category}'")

    # -------------------------------------------------------------
    # SEQUENTIAL PIPELINE EXECUTION
    # -------------------------------------------------------------
    @classmethod
    def execute_workflow(
        cls,
        initial_df: pd.DataFrame,
        workflow: WorkflowDefinition,
        stop_on_error: bool = False,
        capture_previews: bool = True,
        preview_rows: int = 10,
    ) -> WorkflowExecutionResult:
        """
        Executes a sequence of steps sequentially. The output DataFrame from step N
        feeds as the input to step N+1. Captures runtime logs and intermediate previews.
        """
        start_time_total = time.perf_counter()
        current_df = initial_df.copy()

        logs: List[StepExecutionLog] = []
        successful_steps = 0
        failed_steps = 0
        skipped_steps = 0

        for idx, step in enumerate(workflow.steps, start=1):
            if not step.enabled:
                skipped_steps += 1
                logs.append(
                    StepExecutionLog(
                        step_id=step.step_id,
                        step_num=idx,
                        name=step.name,
                        category=step.category,
                        operation=step.operation,
                        status="SKIPPED",
                        message="Step is disabled in workflow configuration.",
                        input_rows=len(current_df),
                        output_rows=len(current_df),
                        input_cols=len(current_df.columns),
                        output_cols=len(current_df.columns),
                        duration_ms=0.0,
                        preview_df=current_df.head(preview_rows) if capture_previews else None,
                    )
                )
                continue

            step_start = time.perf_counter()
            in_rows, in_cols = len(current_df), len(current_df.columns)

            try:
                transformed_df, msg = cls.execute_single_step(current_df, step)
                duration_ms = round((time.perf_counter() - step_start) * 1000, 2)
                out_rows, out_cols = len(transformed_df), len(transformed_df.columns)

                current_df = transformed_df
                successful_steps += 1

                logs.append(
                    StepExecutionLog(
                        step_id=step.step_id,
                        step_num=idx,
                        name=step.name,
                        category=step.category,
                        operation=step.operation,
                        status="SUCCESS",
                        message=msg,
                        input_rows=in_rows,
                        output_rows=out_rows,
                        input_cols=in_cols,
                        output_cols=out_cols,
                        duration_ms=duration_ms,
                        preview_df=current_df.head(preview_rows) if capture_previews else None,
                    )
                )

            except Exception as e:
                duration_ms = round((time.perf_counter() - step_start) * 1000, 2)
                failed_steps += 1
                err_msg = str(e)

                logs.append(
                    StepExecutionLog(
                        step_id=step.step_id,
                        step_num=idx,
                        name=step.name,
                        category=step.category,
                        operation=step.operation,
                        status="FAILED",
                        message=f"Error executing step: {err_msg}",
                        input_rows=in_rows,
                        output_rows=in_rows,
                        input_cols=in_cols,
                        output_cols=in_cols,
                        duration_ms=duration_ms,
                        error_details=err_msg,
                        preview_df=current_df.head(preview_rows) if capture_previews else None,
                    )
                )

                if stop_on_error:
                    # Mark remaining steps as skipped
                    for rem_idx in range(idx + 1, len(workflow.steps) + 1):
                        rem_step = workflow.steps[rem_idx - 1]
                        logs.append(
                            StepExecutionLog(
                                step_id=rem_step.step_id,
                                step_num=rem_idx,
                                name=rem_step.name,
                                category=rem_step.category,
                                operation=rem_step.operation,
                                status="SKIPPED",
                                message="Skipped due to preceding step failure (stop_on_error=True).",
                                input_rows=len(current_df),
                                output_rows=len(current_df),
                                input_cols=len(current_df.columns),
                                output_cols=len(current_df.columns),
                                duration_ms=0.0,
                            )
                        )
                        skipped_steps += 1
                    break

        total_duration_ms = round((time.perf_counter() - start_time_total) * 1000, 2)
        is_success = (failed_steps == 0)

        return WorkflowExecutionResult(
            workflow_id=workflow.workflow_id,
            workflow_name=workflow.name,
            is_success=is_success,
            total_steps=len(workflow.steps),
            successful_steps=successful_steps,
            failed_steps=failed_steps,
            skipped_steps=skipped_steps,
            total_duration_ms=total_duration_ms,
            initial_df=initial_df,
            final_df=current_df,
            logs=logs,
        )

    # -------------------------------------------------------------
    # RECIPE PRESETS & PERSISTENCE
    # -------------------------------------------------------------
    @classmethod
    def get_preset_workflows(cls) -> List[WorkflowDefinition]:
        """Provides pre-bundled production workflows ready for 1-click execution."""
        # 1. Audit & Deduplication Pipeline
        p1 = WorkflowDefinition(
            workflow_id="preset_audit_dedup",
            name="🧹 Comprehensive Audit & Deduplicate",
            description="Normalizes text, standardizes date formats, eliminates duplicates, and sorts records cleanly.",
            version="1.0.0",
            tags=["audit", "cleaning", "deduplication"],
            steps=[
                WorkflowStep(
                    step_id="step_p1_1",
                    name="Trim & Normalize All Text Fields",
                    category="data_cleaning",
                    operation="standardize_text",
                    params={"operations": ["trim", "remove_extra_spaces"]},
                ),
                WorkflowStep(
                    step_id="step_p1_2",
                    name="Standardize Primary Date Column",
                    category="data_cleaning",
                    operation="standardize_dates",
                    params={"column": "OrderDate", "target_format": "%Y-%m-%d"},
                ),
                WorkflowStep(
                    step_id="step_p1_3",
                    name="Remove Duplicate Records Across All Columns",
                    category="row_ops",
                    operation="remove_duplicates",
                    params={"subset_cols": None, "keep_mode": "first"},
                ),
                WorkflowStep(
                    step_id="step_p1_4",
                    name="Verify Non-Empty Dataset",
                    category="validation",
                    operation="assert_min_rows",
                    params={"min_rows": 1},
                ),
            ],
        )

        # 2. Sales Normalization & Tax Calculation Pipeline
        p2 = WorkflowDefinition(
            workflow_id="preset_sales_tax_calc",
            name="📊 Sales Tax Calculation & Regional Aggregation",
            description="Cleans currency amounts, calculates GST/VAT (18%), standardizes regions, and aggregates by region.",
            version="1.0.0",
            tags=["sales", "tax", "aggregation"],
            steps=[
                WorkflowStep(
                    step_id="step_p2_1",
                    name="Clean Numeric Amount Formatting",
                    category="data_cleaning",
                    operation="clean_numeric_formatting",
                    params={"columns": ["Amount"], "strip_symbols": True, "decimal_separator": ".", "round_decimals": 2},
                ),
                WorkflowStep(
                    step_id="step_p2_2",
                    name="Calculate Amount With Tax (18%)",
                    category="column_ops",
                    operation="calculate_column",
                    params={"target_col": "TotalWithTax", "formula": "[Amount] * 1.18"},
                ),
                WorkflowStep(
                    step_id="step_p2_3",
                    name="Uppercase Region Names",
                    category="data_cleaning",
                    operation="standardize_text",
                    params={"columns": ["Region"], "operations": ["trim", "uppercase"]},
                ),
                WorkflowStep(
                    step_id="step_p2_4",
                    name="Group & Aggregate Total by Region",
                    category="transformations",
                    operation="group_and_aggregate",
                    params={"group_by_cols": ["Region"], "agg_spec": {"Amount": "sum", "TotalWithTax": "sum"}},
                ),
            ],
        )

        # 3. CRM & Contact Sanitation Pipeline
        p3 = WorkflowDefinition(
            workflow_id="preset_crm_sanitization",
            name="📇 CRM Contact Sanitation & Validation",
            description="Title-cases customer names, cleans whitespaces, fills missing cities, and verifies uniqueness.",
            version="1.0.0",
            tags=["crm", "customers", "contacts"],
            steps=[
                WorkflowStep(
                    step_id="step_p3_1",
                    name="TitleCase Customer Names",
                    category="data_cleaning",
                    operation="standardize_text",
                    params={"columns": ["CustomerName"], "operations": ["trim", "titlecase"]},
                ),
                WorkflowStep(
                    step_id="step_p3_2",
                    name="Impute Missing City with 'Unassigned'",
                    category="data_cleaning",
                    operation="impute_missing",
                    params={"columns": ["City"], "strategy": "constant", "constant_value": "Unassigned"},
                ),
                WorkflowStep(
                    step_id="step_p3_3",
                    name="Eliminate Duplicate Customers by ID",
                    category="row_ops",
                    operation="remove_duplicates",
                    params={"subset_cols": ["CustomerID"], "keep_mode": "first"},
                ),
            ],
        )

        # 4. Outlier Detection & Suppression Pipeline
        p4 = WorkflowDefinition(
            workflow_id="preset_outlier_treatment",
            name="🎯 Statistical Outlier Suppression (IQR)",
            description="Identifies extreme numerical values using IQR and caps them to 1.5x boundaries.",
            version="1.0.0",
            tags=["statistics", "outliers", "data_quality"],
            steps=[
                WorkflowStep(
                    step_id="step_p4_1",
                    name="Clean Numeric Column",
                    category="data_cleaning",
                    operation="clean_numeric_formatting",
                    params={"columns": ["Amount"], "strip_symbols": True},
                ),
                WorkflowStep(
                    step_id="step_p4_2",
                    name="Cap Extreme Values via IQR 1.5x",
                    category="data_cleaning",
                    operation="treat_outliers",
                    params={"column": "Amount", "method": "iqr", "action": "cap", "multiplier": 1.5},
                ),
                WorkflowStep(
                    step_id="step_p4_3",
                    name="Sort by Cleaned Amount Descending",
                    category="row_ops",
                    operation="sort_records",
                    params={"sort_cols": ["Amount"], "ascending_list": [False]},
                ),
            ],
        )

        return [p1, p2, p3, p4]

    @classmethod
    def ensure_presets_on_disk(cls) -> None:
        """Seeds built-in presets onto disk if not already existing."""
        for preset in cls.get_preset_workflows():
            preset_file = WORKFLOWS_DIR / f"{preset.workflow_id}.json"
            if not preset_file.exists():
                cls.save_workflow_to_disk(preset, filename=f"{preset.workflow_id}.json")

    @classmethod
    def save_workflow_to_disk(cls, workflow: WorkflowDefinition, filename: Optional[str] = None) -> Path:
        """Saves a workflow definition to the workflows storage directory as JSON."""
        safe_name = filename or f"{workflow.workflow_id}.json"
        if not safe_name.endswith(".json"):
            safe_name += ".json"
        target_path = WORKFLOWS_DIR / safe_name
        with open(target_path, "w", encoding="utf-8") as f:
            f.write(workflow.to_json(indent=2))
        return target_path

    @classmethod
    def load_workflow_from_disk(cls, filepath_or_name: Union[str, Path]) -> WorkflowDefinition:
        """Loads a workflow definition from JSON file on disk."""
        path = Path(filepath_or_name)
        if not path.is_absolute():
            path = WORKFLOWS_DIR / path
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            return WorkflowDefinition.from_json(f.read())

    @classmethod
    def list_disk_workflows(cls) -> List[WorkflowDefinition]:
        """Lists all custom workflows stored on disk in the workflows directory."""
        workflows = []
        for file in sorted(WORKFLOWS_DIR.glob("*.json")):
            try:
                wf = cls.load_workflow_from_disk(file)
                workflows.append(wf)
            except Exception:
                continue
        return workflows

    @classmethod
    def delete_workflow_from_disk(cls, workflow_id: str) -> bool:
        """Deletes a saved workflow JSON file from disk."""
        target = WORKFLOWS_DIR / f"{workflow_id}.json"
        if target.exists():
            target.unlink()
            return True
        return False
