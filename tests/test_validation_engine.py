"""
Unit Tests for Universal Validation Engine (Phase 9)
Tests comprehensive data auditing, business rule enforcement,
health scoring, and multi-sheet Excel diagnostic export.
"""
import io
import pytest
import pandas as pd
import numpy as np

from core.validation_engine import ValidationEngine, ValidationReport, ValidationFinding


@pytest.fixture
def sample_audit_df():
    """Generates a test DataFrame with intentional data quality issues."""
    return pd.DataFrame({
        "CustID": [101, 102, 103, 103, 105],  # 1 duplicate key (103)
        "Name": ["Acme Corp", "Globex", None, "Initech", "Hooli"],  # 1 null
        "Amount": [1200.50, -50.00, 3400.00, 250.00, 999999.00],  # 1 negative, 1 extreme outlier
        "JoinDate": ["2026-01-01", "02/01/2026", "20260103", "2026-01-04", "2026-01-05"],  # Mixed date formats
    })


def test_audit_empty_dataframe():
    report = ValidationEngine.audit_dataset(pd.DataFrame())
    assert report.status == "FAILED"
    assert report.total_records == 0
    assert len(report.findings) > 0


def test_audit_dataset_issues_detection(sample_audit_df):
    report = ValidationEngine.audit_dataset(sample_audit_df, dataset_name="Test Customers")

    assert report.total_records == 5
    assert report.total_columns == 4
    assert report.missing_cells == 1
    assert report.duplicate_rows == 0  # not all columns duplicated
    assert report.date_format_issues_count >= 1

    # Check categories in findings
    finding_cats = [f.category for f in report.findings]
    assert "Missing Data" in finding_cats
    assert "Date Consistency" in finding_cats


def test_audit_with_business_rules(sample_audit_df):
    report = ValidationEngine.audit_dataset(
        sample_audit_df,
        required_columns=["Name", "MissingCol"],
        unique_key_columns=["CustID"],
        numeric_non_negative=["Amount"],
    )

    assert report.status == "FAILED"  # MissingCol is completely missing
    rule_results = {r["Rule"]: r["Status"] for r in report.rule_results}

    assert "Column Exists: MissingCol" in rule_results
    assert rule_results["Column Exists: MissingCol"] == "FAILED"

    assert "Mandatory Non-Null: Name" in rule_results
    assert rule_results["Mandatory Non-Null: Name"] == "FAILED"  # 1 null in Name

    assert "Unique Key: [CustID]" in rule_results
    assert rule_results["Unique Key: [CustID]"] == "FAILED"  # 103 is duplicated

    assert "Non-Negative: Amount" in rule_results
    assert rule_results["Non-Negative: Amount"] == "FAILED"  # -50.00 is negative


def test_generate_excel_audit_report(sample_audit_df):
    report = ValidationEngine.audit_dataset(
        sample_audit_df,
        required_columns=["Name"],
        unique_key_columns=["CustID"],
    )
    history = [{"step": 1, "action": "Test Step", "timestamp": "2026-11-04 12:00:00"}]

    excel_bytes = ValidationEngine.generate_excel_audit_report(
        report=report,
        df=sample_audit_df,
        transformation_history=history,
    )

    assert isinstance(excel_bytes, bytes)
    assert len(excel_bytes) > 0

    # Read back sheets with Pandas
    excel_file = io.BytesIO(excel_bytes)
    xl = pd.ExcelFile(excel_file)
    sheet_names = xl.sheet_names

    assert "Executive_Summary" in sheet_names
    assert "Data_Quality_Findings" in sheet_names
    assert "Rule_Validation_Results" in sheet_names
    assert "Transformation_History" in sheet_names

    summary_df = pd.read_excel(excel_file, sheet_name="Executive_Summary")
    assert len(summary_df) > 0
