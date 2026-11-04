"""
Unit Tests for Universal Natural Language Customisation Engine (Phase 8)
Tests instruction parsing, fuzzy schema matching, ambiguity detection,
destructive operation tagging, and confirmed execution.
"""
import pytest
import pandas as pd
import numpy as np

from core.nlp_engine import NaturalLanguageEngine, ProposedOperation, ParsedInstructionResult


@pytest.fixture
def sample_patient_df():
    """Generates sample healthcare dataset with Patient ID, Date, Amount, City."""
    return pd.DataFrame({
        "Patient ID": [101, 102, 103, 104, 104],
        "PatientName": [" John Doe ", "Jane Smith", "Bob Jones", "Alice Lee", "Alice Lee"],
        "Invoice Number": ["INV-001", "INV-002", "INV-003", "INV-004", "INV-004"],
        "VisitDate": ["2026-01-15", "16/01/2026", "20260117", "2026-01-18", "2026-01-18"],
        "Amount": ["$150.00", "220.50", "€95.00", "310", "310"],
        "City": ["Boston", "New York", None, "Chicago", "Chicago"],
    })


def test_parse_rename_column(sample_patient_df):
    res = NaturalLanguageEngine.parse_instruction_offline(
        "Rename Patient ID to Registration Number",
        df=sample_patient_df,
    )
    assert len(res.parsed_operations) == 1
    op = res.parsed_operations[0]
    assert op.operation == "rename_columns"
    assert op.parameters["mapping"] == {"Patient ID": "Registration Number"}
    assert op.is_destructive is False
    assert op.needs_clarification is False


def test_parse_remove_duplicates(sample_patient_df):
    res = NaturalLanguageEngine.parse_instruction_offline(
        "Remove all duplicate records based on Invoice Number",
        df=sample_patient_df,
    )
    assert len(res.parsed_operations) == 1
    op = res.parsed_operations[0]
    assert op.operation == "remove_duplicates"
    assert op.parameters["subset_cols"] == ["Invoice Number"]
    # Deleting rows is tagged as destructive for human confirmation gate
    assert op.is_destructive is True
    assert res.has_destructive_ops is True


def test_parse_date_standardization(sample_patient_df):
    res = NaturalLanguageEngine.parse_instruction_offline(
        "Convert the date column into DD-MM-YYYY",
        df=sample_patient_df,
    )
    assert len(res.parsed_operations) == 1
    op = res.parsed_operations[0]
    assert op.operation == "standardize_dates"
    assert op.parameters["column"] == "VisitDate"
    assert op.parameters["target_format"] == "%d-%m-%Y"


def test_parse_formula_calculation(sample_patient_df):
    res = NaturalLanguageEngine.parse_instruction_offline(
        "Calculate Tax as [Amount] * 0.18",
        df=sample_patient_df,
    )
    assert len(res.parsed_operations) == 1
    op = res.parsed_operations[0]
    assert op.operation == "calculate_column"
    assert op.parameters["target_col"] == "Tax"
    assert "[Amount]" in op.parameters["formula"]


def test_parse_text_cleaning(sample_patient_df):
    res = NaturalLanguageEngine.parse_instruction_offline(
        "Trim all text in PatientName and convert to title case",
        df=sample_patient_df,
    )
    assert len(res.parsed_operations) == 1
    op = res.parsed_operations[0]
    assert op.operation == "standardize_text"
    assert "PatientName" in op.parameters["columns"]
    assert "trim" in op.parameters["operations"]


def test_parse_clean_numeric(sample_patient_df):
    res = NaturalLanguageEngine.parse_instruction_offline(
        "Clean numeric currency formatting in Amount",
        df=sample_patient_df,
    )
    assert len(res.parsed_operations) == 1
    op = res.parsed_operations[0]
    assert op.operation == "clean_numeric_formatting"
    assert op.parameters["columns"] == ["Amount"]


def test_parse_impute_missing(sample_patient_df):
    res = NaturalLanguageEngine.parse_instruction_offline(
        "Fill missing values in City with 'Unknown'",
        df=sample_patient_df,
    )
    assert len(res.parsed_operations) == 1
    op = res.parsed_operations[0]
    assert op.operation == "impute_missing"
    assert op.parameters["columns"] == ["City"]
    assert op.parameters["constant_value"] == "Unknown"


def test_parse_drop_column_destructive(sample_patient_df):
    res = NaturalLanguageEngine.parse_instruction_offline(
        "Drop column City",
        df=sample_patient_df,
    )
    assert len(res.parsed_operations) == 1
    op = res.parsed_operations[0]
    assert op.operation == "delete_columns"
    assert op.parameters["columns"] == ["City"]
    assert op.is_destructive is True


def test_parse_sort_records(sample_patient_df):
    res = NaturalLanguageEngine.parse_instruction_offline(
        "Sort records by Amount descending",
        df=sample_patient_df,
    )
    assert len(res.parsed_operations) == 1
    op = res.parsed_operations[0]
    assert op.operation == "sort_records"
    assert op.parameters["sort_cols"] == ["Amount"]
    assert op.parameters["ascending_list"] == [False]


def test_parse_group_by(sample_patient_df):
    res = NaturalLanguageEngine.parse_instruction_offline(
        "Group by City and sum Amount",
        df=sample_patient_df,
    )
    assert len(res.parsed_operations) == 1
    op = res.parsed_operations[0]
    assert op.operation == "group_and_aggregate"
    assert op.parameters["group_by_cols"] == ["City"]


def test_parse_special_routing():
    # Tally module routing
    res_tally = NaturalLanguageEngine.parse_instruction_offline(
        "Update the existing voucher amounts using the revised Excel file"
    )
    assert res_tally.parsed_operations[0].category == "tally"

    # Conversion routing
    res_conv = NaturalLanguageEngine.parse_instruction_offline(
        "Convert this XML into a structured Excel file"
    )
    assert res_conv.parsed_operations[0].category == "conversion"


def test_ambiguity_and_clarification(sample_patient_df):
    res = NaturalLanguageEngine.parse_instruction_offline(
        "Please make the data look better and fix everything",
        df=sample_patient_df,
    )
    assert res.requires_clarification is True
    op = res.parsed_operations[0]
    assert op.needs_clarification is True
    assert op.clarification_question is not None
    assert len(op.clarification_options) > 0


def test_execute_proposed_operations(sample_patient_df):
    op = ProposedOperation(
        category="column_ops",
        operation="rename_columns",
        parameters={"mapping": {"Patient ID": "Registration Number"}},
        human_explanation="Rename Patient ID",
        affected_columns=["Patient ID"],
    )
    df_res, logs = NaturalLanguageEngine.execute_proposed_operations(sample_patient_df, [op])
    assert "Registration Number" in df_res.columns
    assert "Patient ID" not in df_res.columns
    assert len(logs) == 1
