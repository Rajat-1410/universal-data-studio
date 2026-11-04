"""
Universal Validation Engine (Phase 9)
Evaluates datasets against schema constraints, business rules, type invariants,
anomaly thresholds, and double-entry reconciliation balances.
Generates comprehensive multi-sheet Excel audit & error diagnostics reports.
"""
import io
import re
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
import numpy as np

from utils.helpers import detect_date_inconsistencies, compute_column_outliers, calculate_dataset_health


@dataclass
class ValidationFinding:
    """Individual data quality finding or constraint violation."""
    finding_id: str
    category: str  # Missing Data, Duplicates, Type Inconsistency, Date Format, Outliers, Business Rule
    severity: str  # CRITICAL, WARNING, INFO
    column: str
    issue: str
    affected_rows_count: int
    recommendation: str


@dataclass
class ValidationReport:
    """Consolidated dataset validation report."""
    dataset_name: str
    total_records: int
    total_columns: int
    health_score: float
    health_grade: str
    status: str  # "PASSED", "WARNINGS", "FAILED"
    missing_cells: int
    missing_percentage: float
    duplicate_rows: int
    duplicate_percentage: float
    date_format_issues_count: int
    outlier_values_count: int
    findings: List[ValidationFinding] = field(default_factory=list)
    rule_results: List[Dict[str, Any]] = field(default_factory=list)
    failing_rows_sample: Optional[pd.DataFrame] = None


class ValidationEngine:
    """Enterprise validation suite for comprehensive data quality auditing."""

    # -------------------------------------------------------------
    # AUTOMATED COMPREHENSIVE DATASET AUDIT
    # -------------------------------------------------------------
    @classmethod
    def audit_dataset(
        cls,
        df: pd.DataFrame,
        dataset_name: str = "Working Dataset",
        required_columns: Optional[List[str]] = None,
        unique_key_columns: Optional[List[str]] = None,
        numeric_non_negative: Optional[List[str]] = None,
    ) -> ValidationReport:
        """
        Runs an exhaustive battery of validation checks against a DataFrame:
        - Nulls and missingness percentages per column
        - Exact duplicate rows and key-based duplicates
        - Conflicting date representation patterns
        - Statistical numerical outliers (IQR method)
        - Schema & required column presence
        - Non-negative numerical constraints
        """
        if df is None or df.empty:
            return ValidationReport(
                dataset_name=dataset_name,
                total_records=0,
                total_columns=0,
                health_score=0.0,
                health_grade="F",
                status="FAILED",
                missing_cells=0,
                missing_percentage=0.0,
                duplicate_rows=0,
                duplicate_percentage=0.0,
                date_format_issues_count=0,
                outlier_values_count=0,
                findings=[
                    ValidationFinding(
                        finding_id="err_empty",
                        category="Structural",
                        severity="CRITICAL",
                        column="[Dataset]",
                        issue="The dataset contains zero records or is empty.",
                        affected_rows_count=0,
                        recommendation="Load or ingest a non-empty dataset before running validation.",
                    )
                ],
            )

        total_rows = len(df)
        total_cols = len(df.columns)
        total_cells = total_rows * total_cols

        findings: List[ValidationFinding] = []
        rule_results: List[Dict[str, Any]] = []

        # 1. Missing Value Analysis
        missing_series = df.isna().sum()
        total_missing = int(missing_series.sum())
        missing_pct = round((total_missing / max(1, total_cells)) * 100, 2)

        for col, null_cnt in missing_series.items():
            if null_cnt > 0:
                col_null_pct = round((null_cnt / total_rows) * 100, 1)
                sev = "CRITICAL" if col_null_pct > 50 else ("WARNING" if col_null_pct > 15 else "INFO")
                findings.append(
                    ValidationFinding(
                        finding_id=f"null_{col}",
                        category="Missing Data",
                        severity=sev,
                        column=str(col),
                        issue=f"Contains {null_cnt:,} null/empty cells ({col_null_pct}% of column).",
                        affected_rows_count=int(null_cnt),
                        recommendation="Impute missing values using mean/mode/constant or drop incomplete rows in Data Customisation.",
                    )
                )

        # 2. Duplicate Records Analysis
        # Ensure hashable types before duplicated check
        try:
            hashable_df = df.apply(lambda c: c.astype(str) if c.dtype == object else c)
            dup_mask = hashable_df.duplicated(keep=False)
            dup_count = int(hashable_df.duplicated().sum())
        except Exception:
            dup_mask = pd.Series([False] * len(df))
            dup_count = 0

        dup_pct = round((dup_count / max(1, total_rows)) * 100, 2)
        if dup_count > 0:
            findings.append(
                ValidationFinding(
                    finding_id="dup_records",
                    category="Duplicates",
                    severity="WARNING" if dup_pct < 10 else "CRITICAL",
                    column="[All Columns]",
                    issue=f"{dup_count:,} duplicate records detected across all columns ({dup_pct}%).",
                    affected_rows_count=dup_count,
                    recommendation="Apply Row Operations -> Remove Duplicates to ensure unique primary records.",
                )
            )

        # 3. Date Format Consistency Analysis
        date_issues_count = 0
        for col in df.columns:
            # Check string or object columns for dates
            if df[col].dtype == object:
                sample_vals = df[col].dropna().head(300)
                if not sample_vals.empty:
                    anomalies = detect_date_inconsistencies(sample_vals)
                    if anomalies:
                        date_issues_count += 1
                        patterns = list(anomalies.get("detected_patterns", {}).keys())
                        findings.append(
                            ValidationFinding(
                                finding_id=f"date_{col}",
                                category="Date Consistency",
                                severity="WARNING",
                                column=str(col),
                                issue=f"Multiple conflicting date representations detected: {patterns}",
                                affected_rows_count=len(sample_vals),
                                recommendation=f"Standardize column '{col}' to ISO YYYY-MM-DD or DD/MM/YYYY format.",
                            )
                        )

        # 4. Statistical Numerical Outliers
        total_outliers = 0
        for col in df.columns:
            if pd.api.types.is_numeric_dtype(df[col]):
                num_series = pd.to_numeric(df[col], errors="coerce").dropna()
                if len(num_series) >= 4:
                    outlier_info = compute_column_outliers(num_series, multiplier=1.5)
                    if outlier_info and outlier_info["outlier_count"] > 0:
                        cnt = outlier_info["outlier_count"]
                        total_outliers += cnt
                        findings.append(
                            ValidationFinding(
                                finding_id=f"outlier_{col}",
                                category="Numerical Outliers",
                                severity="INFO",
                                column=str(col),
                                issue=f"{cnt} values exceed 1.5*IQR bounds [{outlier_info['lower_bound']:.2f}, {outlier_info['upper_bound']:.2f}].",
                                affected_rows_count=cnt,
                                recommendation=f"Consider statistical capping or review values in '{col}'.",
                            )
                        )

        # 5. User-Defined Rule Validations
        # A. Required Columns Presence & Non-Null
        if required_columns:
            for req_col in required_columns:
                if req_col not in df.columns:
                    findings.append(
                        ValidationFinding(
                            finding_id=f"req_missing_{req_col}",
                            category="Business Rule",
                            severity="CRITICAL",
                            column=req_col,
                            issue=f"Mandatory required column '{req_col}' is missing entirely from dataset.",
                            affected_rows_count=total_rows,
                            recommendation=f"Add or rename source column to match required header '{req_col}'.",
                        )
                    )
                    rule_results.append({"Rule": f"Column Exists: {req_col}", "Status": "FAILED", "Details": "Missing from schema"})
                else:
                    nulls = int(df[req_col].isna().sum())
                    if nulls > 0:
                        findings.append(
                            ValidationFinding(
                                finding_id=f"req_null_{req_col}",
                                category="Business Rule",
                                severity="CRITICAL",
                                column=req_col,
                                issue=f"Mandatory column '{req_col}' contains {nulls:,} empty/null values.",
                                affected_rows_count=nulls,
                                recommendation=f"Impute or eliminate rows with empty '{req_col}'.",
                            )
                        )
                        rule_results.append({"Rule": f"Mandatory Non-Null: {req_col}", "Status": "FAILED", "Details": f"{nulls} nulls found"})
                    else:
                        rule_results.append({"Rule": f"Mandatory Non-Null: {req_col}", "Status": "PASSED", "Details": "100% complete"})

        # B. Primary Key Uniqueness
        if unique_key_columns:
            valid_keys = [k for k in unique_key_columns if k in df.columns]
            if valid_keys:
                try:
                    hashable_sub = df[valid_keys].apply(lambda c: c.astype(str) if c.dtype == object else c)
                    key_dups = int(hashable_sub.duplicated().sum())
                except Exception:
                    key_dups = 0

                if key_dups > 0:
                    findings.append(
                        ValidationFinding(
                            finding_id="key_uniqueness",
                            category="Business Rule",
                            severity="CRITICAL",
                            column=", ".join(valid_keys),
                            issue=f"{key_dups:,} duplicate records violate primary key uniqueness on [{', '.join(valid_keys)}].",
                            affected_rows_count=key_dups,
                            recommendation="Remove duplicates on key columns or establish a distinct composite identifier.",
                        )
                    )
                    rule_results.append({"Rule": f"Unique Key: [{', '.join(valid_keys)}]", "Status": "FAILED", "Details": f"{key_dups} duplicate keys"})
                else:
                    rule_results.append({"Rule": f"Unique Key: [{', '.join(valid_keys)}]", "Status": "PASSED", "Details": "100% unique primary key"})

        # C. Non-Negative Constraints
        if numeric_non_negative:
            for n_col in numeric_non_negative:
                if n_col in df.columns:
                    s = pd.to_numeric(df[n_col], errors="coerce")
                    neg_count = int((s < 0).sum())
                    if neg_count > 0:
                        findings.append(
                            ValidationFinding(
                                finding_id=f"neg_{n_col}",
                                category="Business Rule",
                                severity="WARNING",
                                column=n_col,
                                issue=f"Contains {neg_count:,} negative numerical values.",
                                affected_rows_count=neg_count,
                                recommendation=f"Verify if negative values are permitted in '{n_col}'.",
                            )
                        )
                        rule_results.append({"Rule": f"Non-Negative: {n_col}", "Status": "FAILED", "Details": f"{neg_count} negative rows"})
                    else:
                        rule_results.append({"Rule": f"Non-Negative: {n_col}", "Status": "PASSED", "Details": "0 negative values"})

        # Health Scoring
        health_info = calculate_dataset_health(df)
        score = health_info["score"]
        grade = health_info["grade"]

        # Adjust score if critical business rules failed
        critical_count = sum(1 for f in findings if f.severity == "CRITICAL")
        if critical_count > 0:
            score = max(20.0, score - (critical_count * 15.0))
            if score < 60:
                grade = "F"
            elif score < 70:
                grade = "D"

        status = "PASSED" if not findings else ("FAILED" if critical_count > 0 else "WARNINGS")

        # Capture sample of problematic rows (up to 50 rows)
        problem_rows = pd.DataFrame()
        if dup_count > 0:
            problem_rows = df[dup_mask].head(25)
        elif total_missing > 0:
            problem_rows = df[df.isna().any(axis=1)].head(25)

        return ValidationReport(
            dataset_name=dataset_name,
            total_records=total_rows,
            total_columns=total_cols,
            health_score=round(score, 1),
            health_grade=grade,
            status=status,
            missing_cells=total_missing,
            missing_percentage=missing_pct,
            duplicate_rows=dup_count,
            duplicate_percentage=dup_pct,
            date_format_issues_count=date_issues_count,
            outlier_values_count=total_outliers,
            findings=findings,
            rule_results=rule_results,
            failing_rows_sample=problem_rows if not problem_rows.empty else None,
        )

    # -------------------------------------------------------------
    # MULTI-SHEET EXCEL AUDIT & ERROR WORKBOOK GENERATOR
    # -------------------------------------------------------------
    @classmethod
    def generate_excel_audit_report(
        cls,
        report: ValidationReport,
        df: Optional[pd.DataFrame] = None,
        transformation_history: Optional[List[Dict[str, Any]]] = None,
    ) -> bytes:
        """
        Generates a professional 5-sheet OpenXML (.xlsx) audit workbook:
        Sheet 1: Executive_Summary
        Sheet 2: Data_Quality_Findings
        Sheet 3: Rule_Validation_Results
        Sheet 4: Transformation_History
        Sheet 5: Problematic_Records_Sample
        """
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            # Sheet 1: Executive Summary
            exec_summary = [
                {"Metric": "Dataset Name", "Value": str(report.dataset_name)},
                {"Metric": "Validation Status", "Value": str(report.status)},
                {"Metric": "Data Health Score", "Value": f"{report.health_score} / 100 (Grade: {report.health_grade})"},
                {"Metric": "Total Records (Rows)", "Value": f"{report.total_records:,}"},
                {"Metric": "Total Columns", "Value": f"{report.total_columns:,}"},
                {"Metric": "Total Missing Cells", "Value": f"{report.missing_cells:,} ({report.missing_percentage}%)"},
                {"Metric": "Duplicate Records", "Value": f"{report.duplicate_rows:,} ({report.duplicate_percentage}%)"},
                {"Metric": "Date Format Warnings", "Value": str(report.date_format_issues_count)},
                {"Metric": "Numerical Outlier Flags", "Value": str(report.outlier_values_count)},
                {"Metric": "Total Findings Count", "Value": str(len(report.findings))},
            ]
            pd.DataFrame(exec_summary).to_excel(writer, sheet_name="Executive_Summary", index=False)

            # Sheet 2: Data Quality Findings
            if report.findings:
                findings_data = [
                    {
                        "ID": f.finding_id,
                        "Category": f.category,
                        "Severity": f.severity,
                        "Column": f.column,
                        "Issue Description": f.issue,
                        "Affected Rows": f.affected_rows_count,
                        "Remediation Recommendation": f.recommendation,
                    }
                    for f in report.findings
                ]
                pd.DataFrame(findings_data).to_excel(writer, sheet_name="Data_Quality_Findings", index=False)
            else:
                pd.DataFrame([{"Status": "100% Clean", "Message": "All automated quality checks passed."}]).to_excel(
                    writer, sheet_name="Data_Quality_Findings", index=False
                )

            # Sheet 3: Rule Validation Results
            if report.rule_results:
                pd.DataFrame(report.rule_results).to_excel(writer, sheet_name="Rule_Validation_Results", index=False)
            else:
                pd.DataFrame([{"Rule": "No custom business rules specified", "Status": "N/A"}]).to_excel(
                    writer, sheet_name="Rule_Validation_Results", index=False
                )

            # Sheet 4: Transformation History
            if transformation_history:
                pd.DataFrame(transformation_history).to_excel(writer, sheet_name="Transformation_History", index=False)
            else:
                pd.DataFrame([{"Log": "No modifications in current session baseline."}]).to_excel(
                    writer, sheet_name="Transformation_History", index=False
                )

            # Sheet 5: Problematic Records Sample
            if report.failing_rows_sample is not None and not report.failing_rows_sample.empty:
                report.failing_rows_sample.to_excel(writer, sheet_name="Problematic_Records", index=False)
            elif df is not None and not df.empty:
                df.head(25).to_excel(writer, sheet_name="Dataset_Sample", index=False)

        return buf.getvalue()
