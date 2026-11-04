"""
Tests for Session Management, UI Helpers, Date Inconsistencies, and Outlier Profiling
"""
import pytest
import pandas as pd
import numpy as np

from utils.helpers import (
    format_bytes,
    detect_date_inconsistencies,
    compute_column_outliers,
    calculate_dataset_health,
)
from utils.format_detector import FormatDetector
from core.file_writer import UniversalFileWriter


def test_format_bytes():
    assert format_bytes(0) == "0 B"
    assert "KB" in format_bytes(1024)
    assert "MB" in format_bytes(1048576)
    assert "GB" in format_bytes(1073741824)


def test_date_inconsistency_detection():
    # Consistent dates
    s_consistent = pd.Series(["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"])
    res = detect_date_inconsistencies(s_consistent)
    assert res["has_dates"] is True
    assert res["is_inconsistent"] is False

    # Inconsistent mixed dates
    s_mixed = pd.Series(["2026-01-01", "02/01/2026", "2026-01-03", "04-01-2026"])
    res_mixed = detect_date_inconsistencies(s_mixed)
    assert res_mixed["has_dates"] is True
    assert res_mixed["is_inconsistent"] is True
    assert len(res_mixed["detected_patterns"]) >= 2


def test_outlier_detection():
    # Normal distribution with extreme outlier
    data = [10.0, 11.0, 12.0, 10.5, 11.2, 10.8, 12.1, 11.5, 999.0]
    s = pd.Series(data)
    outliers = compute_column_outliers(s)
    assert outliers["outlier_count"] == 1
    assert outliers["upper_bound"] < 999.0


def test_dataset_health_score():
    # Perfect dataset
    clean_df = pd.DataFrame({"A": [1, 2, 3], "B": ["x", "y", "z"]})
    h_clean = calculate_dataset_health(clean_df)
    assert h_clean["score"] == 100.0
    assert h_clean["grade"] == "A"

    # Degraded dataset with missing and duplicates
    dirty_df = pd.DataFrame({
        "ID": [1, 1, 2, 3],
        "Val": [None, None, 10.0, 20.0],
    })
    h_dirty = calculate_dataset_health(dirty_df)
    assert h_dirty["score"] < 100.0
    assert len(h_dirty["penalties"]) > 0


def test_universal_file_writer():
    df = pd.DataFrame({"ID": [1, 2], "Name": ["A", "B"]})

    excel_bytes = UniversalFileWriter.to_excel(df)
    assert len(excel_bytes) > 0
    assert excel_bytes.startswith(b"PK")

    csv_bytes = UniversalFileWriter.to_csv(df)
    assert b"ID,Name" in csv_bytes

    json_bytes = UniversalFileWriter.to_json(df)
    assert b'"Name": "A"' in json_bytes or b'"Name":"A"' in json_bytes

    txt_bytes = UniversalFileWriter.to_txt(df)
    assert b"ID|Name" in txt_bytes
