"""
Helper utilities for data profiling, formatting, date diagnostics, and statistics.
"""
import re
import math
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd
import numpy as np


def format_bytes(size_bytes: int) -> str:
    """Formats raw bytes into human readable string (KB, MB, GB)."""
    if size_bytes == 0:
        return "0 B"
    size_name = ("B", "KB", "MB", "GB", "TB")
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    return f"{s} {size_name[i]}"


def detect_date_inconsistencies(series: pd.Series, max_sample: int = 500) -> Dict[str, Any]:
    """
    Scans a series for date-like strings and checks for format inconsistencies
    (e.g., mixed DD/MM/YYYY, YYYY-MM-DD, MM/DD/YYYY, or unparseable dates).
    """
    clean_series = series.dropna().astype(str).str.strip()
    if clean_series.empty:
        return {"has_dates": False, "is_inconsistent": False, "detected_patterns": {}, "inconsistency_count": 0}

    sample = clean_series.head(max_sample)

    patterns = {
        "YYYY-MM-DD": re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$"),
        "DD/MM/YYYY": re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"),
        "DD-MM-YYYY": re.compile(r"^\d{1,2}-\d{1,2}-\d{4}$"),
        "MM/DD/YYYY": re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$"),
        "ISO_TIMESTAMP": re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}"),
        "TALLY_DATE": re.compile(r"^\d{8}$"),  # YYYYMMDD as used in Tally XML
    }

    pattern_counts: Dict[str, int] = {}
    matched_total = 0

    for val in sample:
        matched = False
        for name, pat in patterns.items():
            if pat.match(val):
                pattern_counts[name] = pattern_counts.get(name, 0) + 1
                matched = True
                break
        if matched:
            matched_total += 1

    # Check if column is predominantly date-like
    is_date_col = (matched_total / len(sample)) >= 0.35 if len(sample) > 0 else False
    is_inconsistent = len(pattern_counts) > 1 and is_date_col

    return {
        "has_dates": is_date_col,
        "is_inconsistent": is_inconsistent,
        "sample_size": len(sample),
        "detected_patterns": pattern_counts,
        "primary_pattern": max(pattern_counts.items(), key=lambda x: x[1])[0] if pattern_counts else None,
        "unmatched_ratio": (len(sample) - matched_total) / len(sample) if is_date_col else 0.0,
    }


def compute_column_outliers(series: pd.Series, multiplier: float = 1.5) -> Dict[str, Any]:
    """Computes IQR-based outlier count and bounds for a numeric series."""
    numeric_series = pd.to_numeric(series, errors="coerce").dropna()
    if len(numeric_series) < 4:
        return {"outlier_count": 0, "outlier_percentage": 0.0, "lower_bound": None, "upper_bound": None}

    q25 = numeric_series.quantile(0.25)
    q75 = numeric_series.quantile(0.75)
    iqr = q75 - q25

    if iqr == 0:
        return {"outlier_count": 0, "outlier_percentage": 0.0, "lower_bound": q25, "upper_bound": q75}

    lower_bound = q25 - (multiplier * iqr)
    upper_bound = q75 + (multiplier * iqr)
    outliers = numeric_series[(numeric_series < lower_bound) | (numeric_series > upper_bound)]

    return {
        "outlier_count": int(len(outliers)),
        "outlier_percentage": round((len(outliers) / len(numeric_series)) * 100, 2),
        "lower_bound": float(lower_bound),
        "upper_bound": float(upper_bound),
    }


def calculate_dataset_health(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Computes an overall Data Health Score (0-100) based on:
    - Missing value percentage (weight 40%)
    - Duplicate rows percentage (weight 30%)
    - Mixed/unclean data types & date inconsistencies (weight 30%)
    """
    if df is None or df.empty:
        return {"score": 100, "grade": "A+", "status": "Empty / Clean", "penalties": []}

    total_cells = df.size
    total_missing = int(df.isna().sum().sum())
    missing_pct = (total_missing / total_cells) * 100 if total_cells > 0 else 0

    total_rows = len(df)
    try:
        has_unhashable = any(
            df[c].dtype == object and df[c].apply(lambda v: isinstance(v, (list, dict, set))).any()
            for c in df.columns
        )
        if has_unhashable:
            dedup_df = df.apply(lambda col: col.astype(str) if col.dtype == object else col)
            duplicate_rows = int(dedup_df.duplicated().sum()) if total_rows > 0 else 0
        else:
            duplicate_rows = int(df.duplicated().sum()) if total_rows > 0 else 0
    except Exception:
        duplicate_rows = 0
    duplicate_pct = (duplicate_rows / total_rows) * 100 if total_rows > 0 else 0

    # Penalties
    score = 100.0
    penalties = []

    # Missing penalty (up to 40 pts)
    missing_penalty = min(40.0, missing_pct * 1.5)
    if missing_penalty > 0:
        score -= missing_penalty
        penalties.append(f"Missing values (-{missing_penalty:.1f} pts, {missing_pct:.1f}% missing)")

    # Duplicate penalty (up to 30 pts)
    dup_penalty = min(30.0, duplicate_pct * 1.5)
    if dup_penalty > 0:
        score -= dup_penalty
        penalties.append(f"Duplicate records (-{dup_penalty:.1f} pts, {duplicate_pct:.1f}% duplicates)")

    # Date inconsistencies penalty
    date_issues = 0
    for col in df.columns:
        if df[col].dtype == object:
            date_diag = detect_date_inconsistencies(df[col], max_sample=200)
            if date_diag.get("is_inconsistent"):
                date_issues += 1

    if date_issues > 0:
        date_penalty = min(20.0, date_issues * 5.0)
        score -= date_penalty
        penalties.append(f"Date format inconsistencies in {date_issues} column(s) (-{date_penalty:.1f} pts)")

    score = max(0.0, round(score, 1))

    if score >= 90:
        grade = "A"
        status = "Excellent"
        color = "#10B981"
    elif score >= 75:
        grade = "B"
        status = "Good"
        color = "#3B82F6"
    elif score >= 60:
        grade = "C"
        status = "Fair (Needs Attention)"
        color = "#F59E0B"
    else:
        grade = "D"
        status = "Poor (Needs Cleaning)"
        color = "#EF4444"

    return {
        "score": score,
        "grade": grade,
        "status": status,
        "color": color,
        "missing_pct": round(missing_pct, 2),
        "duplicate_rows": duplicate_rows,
        "duplicate_pct": round(duplicate_pct, 2),
        "penalties": penalties,
    }
