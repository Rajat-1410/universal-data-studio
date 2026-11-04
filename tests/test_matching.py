"""
Unit Tests for Record Matching & Reconciliation Engine (Phase 4)
"""
import pytest
import pandas as pd
import numpy as np

from core.record_matching import RecordMatchingEngine


@pytest.fixture
def original_and_revised():
    df_orig = pd.DataFrame({
        "OrderID": [1001, 1002, 1003, 1004, 1005],
        "Customer": ["Acme Corp", "Globex", "Initech", "Umbrella", "Wayne Ent"],
        "Amount": [1500.0, 840.0, 2300.0, 450.0, 12000.0],
        "Status": ["Pending", "Pending", "Delivered", "Cancelled", "Delivered"],
    })

    df_rev = pd.DataFrame({
        "OrderID": [1001, 1002, 1003, 1006, 1007],
        "Customer": ["Acme Corp", "Globex Inc", "Initech", "Hooli", "Pied Piper"],
        "Amount": [1750.0, 840.0, 2300.0, 950.0, 4800.0],
        "Status": ["Completed", "Pending", "Delivered", "Pending", "Delivered"],
    })
    return df_orig, df_rev


def test_compare_datasets(original_and_revised):
    df_orig, df_rev = original_and_revised
    report = RecordMatchingEngine.compare_datasets(df_orig, df_rev, key_columns=["OrderID"])
    summary = report["summary"]

    assert summary["total_original"] == 5
    assert summary["total_revised"] == 5
    assert summary["matched_keys"] == 3  # 1001, 1002, 1003
    assert summary["modified_count"] == 2  # 1001 (Amount & Status), 1002 (Customer Name)
    assert summary["unmodified_count"] == 1  # 1003 is identical
    assert summary["new_count"] == 2  # 1006, 1007
    assert summary["missing_count"] == 2  # 1004, 1005

    comp_df = report["comparison_df"]
    assert len(comp_df) == 7
    assert set(comp_df["Match_Status"]) == {"MODIFIED", "IDENTICAL", "NEW_IN_REVISED", "MISSING_IN_REVISED"}


def test_reconcile_update_modified(original_and_revised):
    df_orig, df_rev = original_and_revised
    reconciled, msg, counts = RecordMatchingEngine.reconcile_datasets(
        df_orig, df_rev, key_columns=["OrderID"], update_modified=True, insert_new=False, remove_missing=False
    )

    # 1001 should have updated amount 1750.0 and status Completed
    row_1001 = reconciled[reconciled["OrderID"] == 1001].iloc[0]
    assert row_1001["Amount"] == 1750.0
    assert row_1001["Status"] == "Completed"
    assert counts["updated"] == 2


def test_reconcile_insert_new(original_and_revised):
    df_orig, df_rev = original_and_revised
    reconciled, msg, counts = RecordMatchingEngine.reconcile_datasets(
        df_orig, df_rev, key_columns=["OrderID"], update_modified=False, insert_new=True, remove_missing=False
    )
    assert counts["inserted"] == 2
    assert 1006 in reconciled["OrderID"].values
    assert 1007 in reconciled["OrderID"].values
    assert len(reconciled) == 7


def test_reconcile_remove_missing(original_and_revised):
    df_orig, df_rev = original_and_revised
    reconciled, msg, counts = RecordMatchingEngine.reconcile_datasets(
        df_orig, df_rev, key_columns=["OrderID"], update_modified=True, insert_new=True, remove_missing=True
    )
    assert counts["removed"] == 2
    assert 1004 not in reconciled["OrderID"].values
    assert 1005 not in reconciled["OrderID"].values
    # 3 common + 2 new = 5
    assert len(reconciled) == 5
