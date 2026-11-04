"""
Unit Tests for Data Cleaning and Structural Transformations (Phase 3)
"""
import pytest
import pandas as pd
import numpy as np

from core.data_cleaning import DataCleaningEngine
from core.transformations import StructuralTransformationEngine


@pytest.fixture
def messy_df():
    """Returns a dirty dataframe with missing values, messy text, mixed dates, and outliers."""
    return pd.DataFrame({
        "ID": [1, 2, 3, 4, 5],
        "Customer": ["  acme corp  ", "GLOBEX INC", "Initech,   LLC", "wayne enterprises", "Stark   Industries"],
        "Revenue": ["$1,500.50", "840.00", "(250.00)", "$12,000.00", "€ 95,000.00"],
        "OrderDate": ["2026-01-15", "16/01/2026", "20260118", "19-01-2026", "2026-01-20"],
        "Score": [85.0, np.nan, 90.0, np.nan, 95.0],
        "Category": ["A", "B", None, "A", "A"],
    })


# ---------------------------------------------------------------------------
# DATA CLEANING TESTS
# ---------------------------------------------------------------------------

def test_impute_missing_constant(messy_df):
    df_clean, msg = DataCleaningEngine.impute_missing(messy_df, ["Score"], strategy="constant", constant_value=0.0)
    assert df_clean["Score"].isna().sum() == 0
    assert (df_clean["Score"] == 0.0).sum() == 2


def test_impute_missing_mean(messy_df):
    df_clean, msg = DataCleaningEngine.impute_missing(messy_df, ["Score"], strategy="mean")
    assert df_clean["Score"].isna().sum() == 0
    # Mean of 85, 90, 95 is 90.0
    assert df_clean["Score"].iloc[1] == 90.0


def test_impute_missing_mode(messy_df):
    df_clean, msg = DataCleaningEngine.impute_missing(messy_df, ["Category"], strategy="mode")
    assert df_clean["Category"].isna().sum() == 0
    assert df_clean["Category"].iloc[2] == "A"


def test_impute_drop_rows(messy_df):
    df_clean, msg = DataCleaningEngine.impute_missing(messy_df, ["Score"], strategy="drop_rows")
    assert len(df_clean) == 3


def test_standardize_text(messy_df):
    df_clean, msg = DataCleaningEngine.standardize_text(
        messy_df, ["Customer"], operations=["trim", "remove_extra_spaces", "titlecase"]
    )
    assert df_clean["Customer"].iloc[0] == "Acme Corp"
    assert df_clean["Customer"].iloc[4] == "Stark Industries"


def test_standardize_dates(messy_df):
    # Mixed formats: ISO 2026-01-15, Slash 16/01/2026, Tally 20260118, Dash 19-01-2026
    df_clean, msg = DataCleaningEngine.standardize_dates(messy_df, "OrderDate", target_format="%Y-%m-%d")
    assert df_clean["OrderDate"].iloc[0] == "2026-01-15"
    assert df_clean["OrderDate"].iloc[1] == "2026-01-16"
    assert df_clean["OrderDate"].iloc[2] == "2026-01-18"
    assert df_clean["OrderDate"].iloc[3] == "2026-01-19"


def test_clean_numeric_formatting(messy_df):
    # Currency symbols ($ and €), commas, accounting negative (250)
    df_clean, msg = DataCleaningEngine.clean_numeric_formatting(messy_df, ["Revenue"], strip_symbols=True)
    assert df_clean["Revenue"].iloc[0] == 1500.50
    assert df_clean["Revenue"].iloc[1] == 840.00
    assert df_clean["Revenue"].iloc[2] == -250.00
    assert df_clean["Revenue"].iloc[3] == 12000.00
    assert df_clean["Revenue"].iloc[4] == 95000.00


def test_treat_outliers():
    df_outliers = pd.DataFrame({"Val": [10.0, 11.0, 12.0, 10.5, 11.2, 999.0]})
    # Cap outlier
    df_capped, msg = DataCleaningEngine.treat_outliers(df_outliers, "Val", method="iqr", action="cap", multiplier=1.5)
    assert df_capped["Val"].max() < 999.0

    # Flag outlier
    df_flagged, _ = DataCleaningEngine.treat_outliers(df_outliers, "Val", method="iqr", action="flag")
    assert "is_outlier_Val" in df_flagged.columns
    assert df_flagged["is_outlier_Val"].sum() == 1


def test_validate_required_fields(messy_df):
    df_flagged, msg = DataCleaningEngine.validate_required_fields(messy_df, ["Score", "Category"], action="flag")
    assert "has_missing_required" in df_flagged.columns
    assert df_flagged["has_missing_required"].sum() == 3

    df_dropped, _ = DataCleaningEngine.validate_required_fields(messy_df, ["Score"], action="drop")
    assert len(df_dropped) == 3


# ---------------------------------------------------------------------------
# STRUCTURAL TRANSFORMATION TESTS
# ---------------------------------------------------------------------------

def test_append_datasets():
    df1 = pd.DataFrame({"ID": [1, 2], "Name": ["A", "B"]})
    df2 = pd.DataFrame({"ID": [3, 4], "Name": ["C", "D"]})
    appended, msg = StructuralTransformationEngine.append_datasets(df1, df2, "File1", "File2", add_source_tag=True)
    assert len(appended) == 4
    assert "_source_dataset" in appended.columns
    assert appended["_source_dataset"].iloc[0] == "File1"
    assert appended["_source_dataset"].iloc[2] == "File2"


def test_join_datasets():
    df_cust = pd.DataFrame({"CustID": [1, 2, 3], "Name": ["Acme", "Globex", "Initech"]})
    df_orders = pd.DataFrame({"CustID": [1, 2, 4], "Amount": [500, 1200, 300]})

    # Inner Join
    inner_df, _ = StructuralTransformationEngine.join_datasets(df_cust, df_orders, "CustID", "CustID", how="inner")
    assert len(inner_df) == 2

    # Left Join
    left_df, _ = StructuralTransformationEngine.join_datasets(df_cust, df_orders, "CustID", "CustID", how="left")
    assert len(left_df) == 3


def test_pivot_dataset():
    df_long = pd.DataFrame({
        "Year": [2024, 2024, 2025, 2025],
        "Region": ["North", "South", "North", "South"],
        "Sales": [100, 150, 120, 180],
    })
    pivoted, msg = StructuralTransformationEngine.pivot_dataset(
        df_long, index_cols=["Region"], columns_col="Year", values_col="Sales", aggfunc="sum"
    )
    assert len(pivoted) == 2
    assert "Region" in pivoted.columns
    assert "2024" in [str(c) for c in pivoted.columns] or 2024 in pivoted.columns


def test_unpivot_dataset():
    df_wide = pd.DataFrame({
        "Product": ["Widget", "Gadget"],
        "Q1": [10, 20],
        "Q2": [15, 25],
    })
    unpivoted, msg = StructuralTransformationEngine.unpivot_dataset(
        df_wide, id_vars=["Product"], value_vars=["Q1", "Q2"], var_name="Quarter", value_name="Units"
    )
    assert len(unpivoted) == 4
    assert "Quarter" in unpivoted.columns
    assert "Units" in unpivoted.columns


def test_group_and_aggregate():
    df_sales = pd.DataFrame({
        "Region": ["North", "North", "South", "South"],
        "Amount": [100, 200, 300, 400],
        "Qty": [1, 2, 3, 4],
    })
    grouped, msg = StructuralTransformationEngine.group_and_aggregate(
        df_sales, group_by_cols=["Region"], agg_spec={"Amount": "sum", "Qty": "mean"}
    )
    assert len(grouped) == 2
    north_row = grouped[grouped["Region"] == "North"].iloc[0]
    assert north_row["Amount"] == 300
    assert north_row["Qty"] == 1.5
