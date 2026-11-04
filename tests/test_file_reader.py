"""
Unit and Integration Tests for Universal File Reader & Inspector (Phase 1)
"""
import pytest
from pathlib import Path
import pandas as pd

from config import SAMPLES_DIR
from utils.format_detector import FormatDetector
from core.file_reader import FileReaderRegistry, UniversalInspector
from utils.session_manager import SessionManager


@pytest.fixture(scope="module")
def sample_files():
    """Ensure sample files exist."""
    assert SAMPLES_DIR.exists(), "Samples directory must exist"
    return {
        "excel": SAMPLES_DIR / "sample_sales.xlsx",
        "csv": SAMPLES_DIR / "sample_customers.csv",
        "xml": SAMPLES_DIR / "sample_data.xml",
        "json": SAMPLES_DIR / "sample_inventory.json",
        "txt": SAMPLES_DIR / "sample_log.txt",
        "zip": SAMPLES_DIR / "sample_archive.zip",
    }


def test_format_detector(sample_files):
    """Test format detection across all supported input formats."""
    # Excel
    with open(sample_files["excel"], "rb") as f:
        res = FormatDetector.detect_format("sample_sales.xlsx", f.read())
        assert res["format"] == "excel"

    # CSV
    with open(sample_files["csv"], "rb") as f:
        res = FormatDetector.detect_format("sample_customers.csv", f.read())
        assert res["format"] == "csv"
        assert res["details"]["delimiter"] == ","

    # XML
    with open(sample_files["xml"], "rb") as f:
        res = FormatDetector.detect_format("sample_data.xml", f.read())
        assert res["format"] == "xml"

    # JSON
    with open(sample_files["json"], "rb") as f:
        res = FormatDetector.detect_format("sample_inventory.json", f.read())
        assert res["format"] == "json"

    # TXT
    with open(sample_files["txt"], "rb") as f:
        res = FormatDetector.detect_format("sample_log.txt", f.read())
        assert res["format"] == "txt"
        assert res["details"]["detected_delimiter"] == "|"

    # ZIP
    with open(sample_files["zip"], "rb") as f:
        res = FormatDetector.detect_format("sample_archive.zip", f.read())
        assert res["format"] == "zip"
        assert res["is_archive"] is True
        assert res["details"]["file_count"] == 5


def test_excel_reader(sample_files):
    """Test Excel reader sheet detection, switching, and inspection."""
    with open(sample_files["excel"], "rb") as f:
        raw = f.read()

    reader = FileReaderRegistry.get_reader("sample_sales.xlsx", raw)
    data = reader.read("sample_sales.xlsx", raw)

    assert data["format"] == "excel"
    assert "Orders" in data["sheets"]
    assert "Customers" in data["sheets"]
    assert "Inventory" in data["sheets"]
    assert isinstance(data["active_df"], pd.DataFrame)
    assert len(data["active_df"]) == 10

    # Test sheet selection
    data_cust = reader.read("sample_sales.xlsx", raw, sheet_name="Customers")
    assert data_cust["active_sheet"] == "Customers"
    assert len(data_cust["active_df"]) == 5


def test_csv_reader_and_quality_inspection(sample_files):
    """Test CSV parsing and data quality anomaly detection (duplicates, missing, dates, outliers)."""
    with open(sample_files["csv"], "rb") as f:
        raw = f.read()

    reader = FileReaderRegistry.get_reader("sample_customers.csv", raw)
    data = reader.read("sample_customers.csv", raw)
    df = data["active_df"]

    assert len(df) == 10
    assert "ID" in df.columns

    # Run inspection
    insp = UniversalInspector.inspect_dataframe(df, "sample_customers.csv", "csv")
    assert insp["rows"] == 10
    assert insp["columns"] == 6
    assert insp["duplicate_rows"] == 1  # Alan Turing duplicated
    assert insp["total_missing_cells"] == 2  # 2 missing Balances

    # Date inconsistencies detected in RegistrationDate (mixed YYYY-MM-DD and DD/MM/YYYY)
    assert "RegistrationDate" in insp["date_inconsistencies"]
    assert insp["date_inconsistencies"]["RegistrationDate"]["is_inconsistent"] is True

    # Numeric outlier detection on Balance (92000 outlier)
    balance_profile = next(p for p in insp["column_profiles"] if p["name"] == "Balance")
    assert balance_profile["outliers"]["outlier_count"] >= 1


def test_xml_reader_and_hierarchy(sample_files):
    """Test XML hierarchical structural analysis and tabular flattening."""
    with open(sample_files["xml"], "rb") as f:
        raw = f.read()

    reader = FileReaderRegistry.get_reader("sample_data.xml", raw)
    data = reader.read("sample_data.xml", raw)

    assert data["format"] == "xml"
    assert data["root_tag"] == "TRANSACTIONS"

    struct = data["xml_structure"]
    assert struct["max_tree_depth"] >= 4
    assert "RECORD" in struct["tag_counts"]
    assert struct["primary_repeated_tag"] == "RECORD" or struct["primary_repeated_tag"] == "ITEM"

    # Tabular preview
    assert data["active_df"] is not None
    assert len(data["active_df"]) > 0


def test_json_reader(sample_files):
    """Test JSON parsing and candidate array normalization."""
    with open(sample_files["json"], "rb") as f:
        raw = f.read()

    reader = FileReaderRegistry.get_reader("sample_inventory.json", raw)
    data = reader.read("sample_inventory.json", raw)

    assert data["format"] == "json"
    assert "items" in data["keys_at_root"]
    assert isinstance(data["active_df"], pd.DataFrame)
    assert len(data["active_df"]) == 5
    assert "item_id" in data["active_df"].columns


def test_zip_reader(sample_files):
    """Test ZIP archive inspection and selective extraction."""
    with open(sample_files["zip"], "rb") as f:
        raw = f.read()

    reader = FileReaderRegistry.get_reader("sample_archive.zip", raw)
    data = reader.read("sample_archive.zip", raw)

    assert data["format"] == "zip"
    assert len(data["supported_files"]) == 5
    assert "customers_clean.csv" in data["supported_files"]
    assert data["active_df"] is not None
