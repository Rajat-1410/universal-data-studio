"""
Universal Data Cleaning Engine
Implements missing value handling, text normalization, multi-format date standardization,
numeric currency/decimal cleanup, outlier treatment, and field validation for Phase 3.
"""
import re
import math
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
import numpy as np


class DataCleaningEngine:
    """Universal data quality and cleaning operations."""

    @classmethod
    def impute_missing(
        cls,
        df: pd.DataFrame,
        columns: Optional[Union[List[str], str]] = None,
        strategy: str = "constant",
        constant_value: Any = None,
        col_name: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, str]:
        """
        Handles missing/null values across designated columns.
        Strategies: 'constant', 'mean', 'median', 'mode', 'ffill', 'bfill', 'drop_rows'.
        """
        df_copy = df.copy()
        raw_cols = columns if columns is not None else col_name
        if raw_cols is None:
            raise ValueError("No columns specified for missing value treatment.")
        if isinstance(raw_cols, str):
            raw_cols = [raw_cols]

        target_cols = [c for c in raw_cols if c in df_copy.columns]
        if not target_cols:
            raise ValueError("No valid columns selected for missing value treatment.")

        initial_nulls = int(df_copy[target_cols].isna().sum().sum())

        if strategy == "drop_rows":
            initial_len = len(df_copy)
            df_copy = df_copy.dropna(subset=target_cols).reset_index(drop=True)
            dropped = initial_len - len(df_copy)
            return df_copy, f"Dropped {dropped} row(s) containing missing values in [{', '.join(target_cols)}]"

        for col in target_cols:
            series = df_copy[col]
            if series.isna().sum() == 0:
                continue

            if strategy == "mean":
                num_s = pd.to_numeric(series, errors="coerce")
                if num_s.notna().sum() > 0:
                    mean_val = float(num_s.mean())
                    df_copy[col] = series.fillna(mean_val)
            elif strategy == "median":
                num_s = pd.to_numeric(series, errors="coerce")
                if num_s.notna().sum() > 0:
                    median_val = float(num_s.median())
                    df_copy[col] = series.fillna(median_val)
            elif strategy == "mode":
                mode_vals = series.mode(dropna=True)
                if not mode_vals.empty:
                    df_copy[col] = series.fillna(mode_vals.iloc[0])
            elif strategy == "ffill":
                df_copy[col] = series.ffill()
            elif strategy == "bfill":
                df_copy[col] = series.bfill()
            elif strategy == "constant":
                df_copy[col] = series.fillna(constant_value)

        remaining_nulls = int(df_copy[target_cols].isna().sum().sum())
        imputed_count = initial_nulls - remaining_nulls
        return df_copy, f"Imputed {imputed_count} null cell(s) in [{', '.join(target_cols)}] using strategy '{strategy}'"

    @classmethod
    def standardize_text(
        cls,
        df: pd.DataFrame,
        columns: Optional[Union[List[str], str]] = None,
        operations: Optional[List[str]] = None,
        col_name: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, str]:
        """
        Cleans and normalizes text fields:
        - trim: strip leading/trailing whitespace
        - remove_extra_spaces: collapse multi-spaces into single space
        - uppercase: convert to UPPERCASE
        - lowercase: convert to lowercase
        - titlecase: convert to Title Case
        - alphanumeric_only: keep letters, numbers, and single spaces
        - remove_punctuation: strip punctuation marks
        """
        df_copy = df.copy()
        raw_cols = columns if columns is not None else col_name
        if raw_cols is None:
            raise ValueError("No columns specified for text standardization.")
        if isinstance(raw_cols, str):
            raw_cols = [raw_cols]

        target_cols = [c for c in raw_cols if c in df_copy.columns]
        if not target_cols:
            raise ValueError("No valid columns selected for text standardization.")
        if not operations:
            raise ValueError("At least one text cleaning operation must be selected.")

        for col in target_cols:
            # Work on non-null string representation
            def clean_str(val):
                if pd.isna(val):
                    return val
                s = str(val)

                if "trim" in operations:
                    s = s.strip()
                if "remove_extra_spaces" in operations:
                    s = re.sub(r"\s+", " ", s)
                if "uppercase" in operations:
                    s = s.upper()
                elif "lowercase" in operations:
                    s = s.lower()
                elif "titlecase" in operations:
                    s = s.title()
                if "alphanumeric_only" in operations:
                    s = re.sub(r"[^\w\s]", "", s)
                elif "remove_punctuation" in operations:
                    s = re.sub(r"[^\w\s]", "", s)

                return s

            df_copy[col] = df_copy[col].apply(clean_str)

        ops_desc = ", ".join(operations)
        return df_copy, f"Standardized text in [{', '.join(target_cols)}] ({ops_desc})"

    @classmethod
    def standardize_dates(
        cls,
        df: pd.DataFrame,
        column: Optional[str] = None,
        target_format: str = "%Y-%m-%d",
        dayfirst: Optional[bool] = None,
        col_name: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, str]:
        """
        Parses mixed date representations (YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY, YYYYMMDD)
        and standardizes into target_format string or datetime.
        """
        df_copy = df.copy()
        col = column or col_name
        if not col or col not in df_copy.columns:
            raise ValueError(f"Column '{col}' does not exist.")

        series = df_copy[col]
        initial_non_null = int(series.notna().sum())

        def parse_single_date(val):
            if pd.isna(val) or str(val).strip() == "":
                return np.nan

            s = str(val).strip()

            # Handle Tally compact date: YYYYMMDD (8 digits)
            if re.match(r"^\d{8}$", s):
                try:
                    dt = pd.to_datetime(s, format="%Y%m%d")
                    return dt.strftime(target_format) if target_format != "datetime" else dt
                except Exception:
                    pass

            # Try flexible pandas date parser
            try:
                # If year is first (YYYY-MM-DD), dayfirst must be False
                if re.match(r"^\d{4}[-/]", s):
                    df_flag = False
                elif dayfirst is not None:
                    df_flag = dayfirst
                else:
                    df_flag = ("/" in s or "-" in s)

                dt = pd.to_datetime(s, dayfirst=df_flag, errors="coerce")
                if pd.notna(dt):
                    return dt.strftime(target_format) if target_format != "datetime" else dt
            except Exception:
                pass

            # Fallback: standard to_datetime
            try:
                dt = pd.to_datetime(s, errors="coerce")
                if pd.notna(dt):
                    return dt.strftime(target_format) if target_format != "datetime" else dt
            except Exception:
                pass

            return np.nan

        parsed_series = series.apply(parse_single_date)
        valid_converted = int(parsed_series.notna().sum())
        df_copy[column] = parsed_series

        desc = f"Standardized date format in '{column}' to '{target_format}' ({valid_converted}/{initial_non_null} converted)"
        return df_copy, desc

    @classmethod
    def clean_numeric_formatting(
        cls,
        df: pd.DataFrame,
        columns: Optional[Union[List[str], str]] = None,
        strip_symbols: bool = True,
        decimal_separator: str = ".",
        round_decimals: Optional[int] = None,
        col_name: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, str]:
        """
        Strips currency symbols ($ € £ ₹ ¥), commas, spaces, and percentage signs,
        converts accounting parentheses like (500) to -500, and casts to float.
        """
        df_copy = df.copy()
        raw_cols = columns if columns is not None else col_name
        if raw_cols is None:
            raise ValueError("No columns specified for numeric cleaning.")
        if isinstance(raw_cols, str):
            raw_cols = [raw_cols]

        target_cols = [c for c in raw_cols if c in df_copy.columns]
        if not target_cols:
            raise ValueError("No valid columns selected for numeric cleaning.")

        for col in target_cols:
            def parse_num(val):
                if pd.isna(val):
                    return np.nan
                if isinstance(val, (int, float)):
                    num = float(val)
                    return round(num, round_decimals) if round_decimals is not None else num

                s = str(val).strip()
                if not s:
                    return np.nan

                # Accounting format: (123.45) -> -123.45
                if s.startswith("(") and s.endswith(")"):
                    s = "-" + s[1:-1]

                # Strip currency symbols and letters
                if strip_symbols:
                    s = re.sub(r"[$€£₹¥% ]", "", s)

                # European comma decimal: e.g. 1.250,50 -> 1250.50
                if decimal_separator == ",":
                    # Remove thousand dots then replace comma with dot
                    s = s.replace(".", "").replace(",", ".")
                else:
                    # Remove thousand commas
                    s = s.replace(",", "")

                try:
                    num = float(s)
                    return round(num, round_decimals) if round_decimals is not None else num
                except Exception:
                    return np.nan

            df_copy[col] = df_copy[col].apply(parse_num)

        desc = f"Cleaned numeric formatting in [{', '.join(target_cols)}]"
        if round_decimals is not None:
            desc += f" (rounded to {round_decimals} decimals)"
        return df_copy, desc

    @classmethod
    def treat_outliers(
        cls,
        df: pd.DataFrame,
        column: str,
        method: str = "iqr",
        action: str = "cap",
        multiplier: float = 1.5,
        z_threshold: float = 3.0,
    ) -> Tuple[pd.DataFrame, str]:
        """
        Detects and treats numerical outliers using IQR or Z-Score.
        Actions:
        - 'cap': Winsorize / clamp values to [lower_bound, upper_bound]
        - 'flag': adds boolean column 'is_outlier_<col>'
        - 'replace_null': replaces outlier values with NaN
        - 'drop_rows': drops rows containing outliers
        """
        df_copy = df.copy()
        if column not in df_copy.columns:
            raise ValueError(f"Column '{column}' does not exist.")

        numeric_series = pd.to_numeric(df_copy[column], errors="coerce")
        clean_vals = numeric_series.dropna()
        if len(clean_vals) < 4:
            return df_copy, f"Insufficient data in '{column}' to compute outliers."

        if method == "iqr":
            q25 = clean_vals.quantile(0.25)
            q75 = clean_vals.quantile(0.75)
            iqr = q75 - q25
            lower_bound = float(q25 - (multiplier * iqr))
            upper_bound = float(q75 + (multiplier * iqr))
        else:  # z_score
            mean_val = clean_vals.mean()
            std_val = clean_vals.std()
            if std_val == 0:
                return df_copy, f"Zero variance in '{column}'; no outliers detected."
            lower_bound = float(mean_val - (z_threshold * std_val))
            upper_bound = float(mean_val + (z_threshold * std_val))

        outlier_mask = (numeric_series < lower_bound) | (numeric_series > upper_bound)
        outlier_count = int(outlier_mask.sum())

        if action == "flag":
            flag_col = f"is_outlier_{column}"
            df_copy[flag_col] = outlier_mask
            desc = f"Flagged {outlier_count} outlier(s) in column '{flag_col}' (Bounds: [{lower_bound:.2f}, {upper_bound:.2f}])"
        elif action == "cap":
            df_copy[column] = numeric_series.clip(lower=lower_bound, upper=upper_bound)
            desc = f"Capped {outlier_count} outlier(s) in '{column}' to bounds [{lower_bound:.2f}, {upper_bound:.2f}]"
        elif action == "replace_null":
            df_copy.loc[outlier_mask, column] = np.nan
            desc = f"Replaced {outlier_count} outlier(s) with NULL in '{column}'"
        elif action == "drop_rows":
            initial_len = len(df_copy)
            df_copy = df_copy[~outlier_mask].reset_index(drop=True)
            desc = f"Dropped {outlier_count} outlier row(s) in '{column}' ({len(df_copy)} rows remaining)"
        else:
            desc = f"Identified {outlier_count} outlier(s) in '{column}'"

        return df_copy, desc

    @classmethod
    def validate_required_fields(
        cls,
        df: pd.DataFrame,
        required_columns: List[str],
        action: str = "flag",
    ) -> Tuple[pd.DataFrame, str]:
        """
        Validates presence of required non-null/non-empty fields.
        Actions:
        - 'flag': adds a boolean column '_missing_required_fields'
        - 'drop': drops rows failing required field presence
        """
        df_copy = df.copy()
        target_cols = [c for c in required_columns if c in df_copy.columns]
        if not target_cols:
            raise ValueError("No valid columns selected for required field validation.")

        # A row is invalid if any required column is NaN or whitespace
        is_invalid = pd.Series(False, index=df_copy.index)
        for col in target_cols:
            is_col_null = df_copy[col].isna() | (df_copy[col].astype(str).str.strip() == "")
            is_invalid = is_invalid | is_col_null

        invalid_count = int(is_invalid.sum())

        if action == "drop":
            df_copy = df_copy[~is_invalid].reset_index(drop=True)
            desc = f"Dropped {invalid_count} row(s) missing required fields [{', '.join(target_cols)}]"
        else:
            flag_col = "has_missing_required"
            df_copy[flag_col] = is_invalid
            desc = f"Flagged {invalid_count} row(s) missing required fields in '{flag_col}'"

        return df_copy, desc
