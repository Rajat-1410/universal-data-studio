"""
Unit Tests for Column and Row Transformation Operations (Phase 2)
"""
import pytest
import pandas as pd
import numpy as np

from core.transformations import ColumnOperations, RowOperations


@pytest.fixture
def sample_df():
    """Returns a fresh sample dataframe for testing."""
    return pd.DataFrame({
        "ID": [101, 102, 103, 104, 105],
        "Name": ["John Doe", "Jane Smith", "Bob Jones", "Alice Brown", "Charlie Davis"],
        "Department": ["Sales", "Engineering", "Sales", "HR", "Engineering"],
        "Salary": [50000.0, 85000.0, 52000.0, 48000.0, 92000.0],
        "JoiningDate": ["2020-01-15", "2019-06-01", "2021-03-20", "2018-11-10", "2022-08-15"],
        "IsActive": [True, True, False, True, True],
    })


# ---------------------------------------------------------------------------
# COLUMN OPERATIONS TESTS
# ---------------------------------------------------------------------------

def test_rename_columns(sample_df):
    new_df, msg = ColumnOperations.rename_columns(sample_df, {"Salary": "BaseSalary", "Name": "FullName"})
    assert "BaseSalary" in new_df.columns
    assert "FullName" in new_df.columns
    assert "Salary" not in new_df.columns

    # Test collision error
    with pytest.raises(ValueError):
        ColumnOperations.rename_columns(sample_df, {"Salary": "Name"})


def test_add_column(sample_df):
    # Constant
    df1, _ = ColumnOperations.add_column(sample_df, "Country", "constant", "USA")
    assert "Country" in df1.columns
    assert (df1["Country"] == "USA").all()

    # Sequence
    df2, _ = ColumnOperations.add_column(sample_df, "SeqNo", "sequence", 100)
    assert list(df2["SeqNo"]) == [100, 101, 102, 103, 104]

    # Copy column
    df3, _ = ColumnOperations.add_column(sample_df, "NameCopy", "copy_col", source_col="Name")
    assert (df3["NameCopy"] == sample_df["Name"]).all()

    # Empty null
    df4, _ = ColumnOperations.add_column(sample_df, "Notes", "null")
    assert df4["Notes"].isna().all()


def test_delete_columns(sample_df):
    new_df, _ = ColumnOperations.delete_columns(sample_df, ["Department", "IsActive"])
    assert "Department" not in new_df.columns
    assert "IsActive" not in new_df.columns
    assert len(new_df.columns) == 4

    # Cannot delete all columns
    with pytest.raises(ValueError):
        ColumnOperations.delete_columns(sample_df, list(sample_df.columns))


def test_reorder_columns(sample_df):
    reversed_cols = list(sample_df.columns)[::-1]
    new_df, _ = ColumnOperations.reorder_columns(sample_df, reversed_cols)
    assert list(new_df.columns) == reversed_cols


def test_merge_columns(sample_df):
    new_df, _ = ColumnOperations.merge_columns(
        sample_df, source_cols=["ID", "Name"], target_col="ID_Name", delimiter=" - ", drop_sources=True
    )
    assert "ID_Name" in new_df.columns
    assert new_df["ID_Name"].iloc[0] == "101 - John Doe"
    assert "ID" not in new_df.columns
    assert "Name" not in new_df.columns


def test_split_column(sample_df):
    new_df, _ = ColumnOperations.split_column(
        sample_df, source_col="Name", delimiter=" ", new_cols=["FirstName", "LastName"], drop_source=True
    )
    assert "FirstName" in new_df.columns
    assert "LastName" in new_df.columns
    assert new_df["FirstName"].iloc[0] == "John"
    assert new_df["LastName"].iloc[0] == "Doe"
    assert "Name" not in new_df.columns


def test_cast_column_type(sample_df):
    # Float to Int
    df_int, _ = ColumnOperations.cast_column_type(sample_df, "Salary", "integer")
    assert df_int["Salary"].dtype == "Int64"

    # String to Datetime
    df_dt, _ = ColumnOperations.cast_column_type(sample_df, "JoiningDate", "datetime", date_format="%Y-%m-%d")
    assert pd.api.types.is_datetime64_any_dtype(df_dt["JoiningDate"])


def test_replace_values(sample_df):
    new_df, _ = ColumnOperations.replace_values(sample_df, "Department", "Sales", "Commercial", match_mode="exact")
    assert (new_df["Department"] == "Commercial").sum() == 2
    assert (new_df["Department"] == "Sales").sum() == 0


def test_calculate_column(sample_df):
    # Calculated salary with 10% bonus: [Salary] * 1.10
    new_df, _ = ColumnOperations.calculate_column(sample_df, "TotalComp", "[Salary] * 1.1")
    assert "TotalComp" in new_df.columns
    assert new_df["TotalComp"].iloc[0] == pytest.approx(55000.0)


def test_map_column_values(sample_df):
    mapping = {"Sales": "S", "Engineering": "ENG", "HR": "HumanResources"}
    new_df, _ = ColumnOperations.map_column_values(sample_df, "Department", "DeptCode", mapping)
    assert new_df["DeptCode"].iloc[0] == "S"
    assert new_df["DeptCode"].iloc[1] == "ENG"


# ---------------------------------------------------------------------------
# ROW OPERATIONS TESTS
# ---------------------------------------------------------------------------

def test_filter_rows(sample_df):
    # Keep Sales
    df_sales, _ = RowOperations.filter_rows(sample_df, "Department", "equals", "Sales", action="keep")
    assert len(df_sales) == 2

    # Drop Sales
    df_no_sales, _ = RowOperations.filter_rows(sample_df, "Department", "equals", "Sales", action="drop")
    assert len(df_no_sales) == 3

    # Greater than numeric
    df_high_sal, _ = RowOperations.filter_rows(sample_df, "Salary", ">", 60000, action="keep")
    assert len(df_high_sal) == 2


def test_delete_rows_by_indices(sample_df):
    new_df, _ = RowOperations.delete_rows_by_indices(sample_df, [0, 2])
    assert len(new_df) == 3
    assert new_df["ID"].iloc[0] == 102


def test_remove_duplicates():
    df_dups = pd.DataFrame({
        "Key": [1, 2, 2, 3],
        "Val": ["A", "B", "B", "C"],
    })
    new_df, _ = RowOperations.remove_duplicates(df_dups, subset_cols=["Key"], keep_mode="first")
    assert len(new_df) == 3


def test_sort_records(sample_df):
    sorted_df, _ = RowOperations.sort_records(sample_df, ["Salary"], ascending_list=[False])
    assert sorted_df["Salary"].iloc[0] == 92000.0


def test_insert_row(sample_df):
    new_row = {"ID": 999, "Name": "New Person", "Salary": 60000}
    df_inserted, _ = RowOperations.insert_row(sample_df, new_row, position="top")
    assert len(df_inserted) == 6
    assert df_inserted["ID"].iloc[0] == 999


def test_update_record_by_key(sample_df):
    updated_df, _ = RowOperations.update_records_by_key(sample_df, "ID", 101, "Salary", 75000.0)
    assert updated_df.loc[updated_df["ID"] == 101, "Salary"].iloc[0] == 75000.0
