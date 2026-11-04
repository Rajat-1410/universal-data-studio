"""
Universal Data Transformations & Customisation Engine
Implements comprehensive, safe, and modular Column and Row operations for Phase 2.
"""
import re
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
import numpy as np


class ColumnOperations:
    """Universal column transformation operations."""

    @classmethod
    def rename_columns(cls, df: pd.DataFrame, rename_dict: Dict[str, str]) -> Tuple[pd.DataFrame, str]:
        """Renames one or multiple columns with collision checking."""
        df_copy = df.copy()
        clean_renames = {old.strip(): new.strip() for old, new in rename_dict.items() if old.strip() and new.strip()}

        if not clean_renames:
            raise ValueError("No valid column renames provided.")

        # Check existing collisions
        existing = set(df_copy.columns)
        for old_col, new_col in clean_renames.items():
            if old_col not in existing:
                raise ValueError(f"Column '{old_col}' does not exist in dataset.")
            if new_col in existing and new_col != old_col:
                raise ValueError(f"Target column name '{new_col}' already exists in dataset.")

        df_copy = df_copy.rename(columns=clean_renames)
        details = ", ".join([f"'{k}' -> '{v}'" for k, v in clean_renames.items()])
        return df_copy, f"Renamed column(s): {details}"

    @classmethod
    def add_column(
        cls,
        df: pd.DataFrame,
        col_name: str,
        value_type: str = "constant",
        value: Any = None,
        source_col: Optional[str] = None,
    ) -> Tuple[pd.DataFrame, str]:
        """Adds a new column (constant value, sequential number, copy of existing column, or null)."""
        df_copy = df.copy()
        clean_name = col_name.strip()
        if not clean_name:
            raise ValueError("Column name cannot be blank.")
        if clean_name in df_copy.columns:
            raise ValueError(f"Column '{clean_name}' already exists.")

        total_rows = len(df_copy)

        if value_type == "constant":
            df_copy[clean_name] = value
            desc = f"Added column '{clean_name}' with constant value '{value}'"
        elif value_type == "sequence":
            start_num = int(value) if value is not None and str(value).isdigit() else 1
            df_copy[clean_name] = range(start_num, start_num + total_rows)
            desc = f"Added sequential column '{clean_name}' starting from {start_num}"
        elif value_type == "copy_col":
            if not source_col or source_col not in df_copy.columns:
                raise ValueError(f"Source column '{source_col}' not found.")
            df_copy[clean_name] = df_copy[source_col].copy()
            desc = f"Added column '{clean_name}' copied from '{source_col}'"
        elif value_type == "null":
            df_copy[clean_name] = np.nan
            desc = f"Added empty/null column '{clean_name}'"
        else:
            df_copy[clean_name] = value
            desc = f"Added column '{clean_name}'"

        return df_copy, desc

    @classmethod
    def delete_columns(cls, df: pd.DataFrame, col_names: List[str]) -> Tuple[pd.DataFrame, str]:
        """Deletes one or more columns ensuring dataset is not emptied entirely."""
        df_copy = df.copy()
        to_drop = [c for c in col_names if c in df_copy.columns]
        if not to_drop:
            raise ValueError("None of the specified columns exist in dataset.")
        if len(to_drop) >= len(df_copy.columns):
            raise ValueError("Cannot delete all columns. At least one column must remain.")

        df_copy = df_copy.drop(columns=to_drop)
        return df_copy, f"Deleted column(s): {', '.join(to_drop)}"

    @classmethod
    def reorder_columns(cls, df: pd.DataFrame, new_order: List[str]) -> Tuple[pd.DataFrame, str]:
        """Reorders columns according to specified ordering."""
        df_copy = df.copy()
        if set(new_order) != set(df_copy.columns):
            raise ValueError("Column list must contain all existing columns without duplicates.")

        df_copy = df_copy[new_order]
        return df_copy, f"Reordered columns to: {', '.join(new_order[:5])}..."

    @classmethod
    def merge_columns(
        cls,
        df: pd.DataFrame,
        source_cols: List[str],
        target_col: str,
        delimiter: str = " ",
        drop_sources: bool = False,
    ) -> Tuple[pd.DataFrame, str]:
        """Merges multiple columns into a single column using a specified delimiter."""
        df_copy = df.copy()
        if len(source_cols) < 2:
            raise ValueError("Must select at least two columns to merge.")
        for sc in source_cols:
            if sc not in df_copy.columns:
                raise ValueError(f"Source column '{sc}' does not exist.")

        clean_target = target_col.strip()
        if not clean_target:
            raise ValueError("Target column name cannot be empty.")
        if clean_target in df_copy.columns and clean_target not in source_cols:
            raise ValueError(f"Target column '{clean_target}' already exists.")

        merged_series = df_copy[source_cols[0]].astype(str).fillna("")
        for sc in source_cols[1:]:
            merged_series = merged_series + delimiter + df_copy[sc].astype(str).fillna("")

        df_copy[clean_target] = merged_series

        if drop_sources:
            cols_to_drop = [c for c in source_cols if c != clean_target]
            df_copy = df_copy.drop(columns=cols_to_drop)
            desc = f"Merged [{', '.join(source_cols)}] into '{clean_target}' (dropped sources)"
        else:
            desc = f"Merged [{', '.join(source_cols)}] into '{clean_target}'"

        return df_copy, desc

    @classmethod
    def split_column(
        cls,
        df: pd.DataFrame,
        source_col: str,
        delimiter: str,
        new_cols: List[str],
        drop_source: bool = False,
        max_split: int = -1,
    ) -> Tuple[pd.DataFrame, str]:
        """Splits a column by delimiter into multiple designated columns."""
        df_copy = df.copy()
        if source_col not in df_copy.columns:
            raise ValueError(f"Source column '{source_col}' not found.")
        if not delimiter:
            raise ValueError("Delimiter cannot be empty.")
        if not new_cols:
            raise ValueError("At least one target column name must be provided.")

        clean_new_cols = [c.strip() for c in new_cols if c.strip()]
        for nc in clean_new_cols:
            if nc in df_copy.columns and nc != source_col:
                raise ValueError(f"Target column name '{nc}' already exists.")

        n_splits = len(clean_new_cols) - 1 if max_split == -1 else max_split
        split_df = df_copy[source_col].astype(str).str.split(delimiter, n=n_splits, expand=True)

        for i, col_name in enumerate(clean_new_cols):
            if i < split_df.shape[1]:
                df_copy[col_name] = split_df[i]
            else:
                df_copy[col_name] = ""

        if drop_source and source_col not in clean_new_cols:
            df_copy = df_copy.drop(columns=[source_col])
            desc = f"Split '{source_col}' into [{', '.join(clean_new_cols)}] (dropped source)"
        else:
            desc = f"Split '{source_col}' into [{', '.join(clean_new_cols)}]"

        return df_copy, desc

    @classmethod
    def cast_column_type(
        cls,
        df: pd.DataFrame,
        col_name: str,
        target_type: str,
        date_format: Optional[str] = None,
        errors: str = "coerce",
    ) -> Tuple[pd.DataFrame, str]:
        """Safely casts a column to Integer, Float, String, Datetime, or Boolean."""
        df_copy = df.copy()
        if col_name not in df_copy.columns:
            raise ValueError(f"Column '{col_name}' does not exist.")

        series = df_copy[col_name]

        if target_type in ["integer", "int"]:
            num_series = pd.to_numeric(series, errors=errors)
            # Use pandas nullable integer to preserve NaNs
            df_copy[col_name] = num_series.astype("Int64")
        elif target_type in ["float", "numeric"]:
            df_copy[col_name] = pd.to_numeric(series, errors=errors)
        elif target_type in ["string", "text"]:
            df_copy[col_name] = series.astype(str)
        elif target_type in ["datetime", "date"]:
            if date_format:
                df_copy[col_name] = pd.to_datetime(series, format=date_format, errors=errors)
            else:
                df_copy[col_name] = pd.to_datetime(series, errors=errors)
        elif target_type in ["boolean", "bool"]:
            # Robust boolean conversion
            def parse_bool(v):
                if pd.isna(v):
                    return np.nan
                s = str(v).strip().lower()
                if s in ["true", "1", "t", "y", "yes"]:
                    return True
                elif s in ["false", "0", "f", "n", "no"]:
                    return False
                return np.nan

            df_copy[col_name] = series.apply(parse_bool).astype("boolean")
        else:
            raise ValueError(f"Unsupported target type '{target_type}'.")

        return df_copy, f"Converted column '{col_name}' to {target_type}"

    @classmethod
    def replace_values(
        cls,
        df: pd.DataFrame,
        col_name: Optional[str],
        find_val: str,
        replace_val: str,
        match_mode: str = "exact",
        use_regex: bool = False,
    ) -> Tuple[pd.DataFrame, str]:
        """Replaces values within a column or across the whole DataFrame."""
        df_copy = df.copy()
        target_cols = [col_name] if col_name and col_name in df_copy.columns else list(df_copy.columns)

        replaced_count = 0

        for col in target_cols:
            if match_mode == "exact":
                # Handle special null search
                if find_val == "[NULL]" or find_val == "null":
                    mask = df_copy[col].isna()
                    df_copy.loc[mask, col] = replace_val
                    replaced_count += int(mask.sum())
                else:
                    mask = df_copy[col].astype(str) == find_val
                    df_copy.loc[mask, col] = replace_val
                    replaced_count += int(mask.sum())
            elif match_mode == "contains":
                mask = df_copy[col].astype(str).str.contains(re.escape(find_val), na=False)
                df_copy[col] = df_copy[col].astype(str).str.replace(find_val, replace_val, regex=False)
                replaced_count += int(mask.sum())
            elif match_mode == "regex":
                mask = df_copy[col].astype(str).str.contains(find_val, regex=True, na=False)
                df_copy[col] = df_copy[col].astype(str).str.replace(find_val, replace_val, regex=True)
                replaced_count += int(mask.sum())

        target_desc = f"column '{col_name}'" if col_name else "all columns"
        return df_copy, f"Replaced '{find_val}' with '{replace_val}' in {target_desc} ({replaced_count} matches)"

    @classmethod
    def calculate_column(
        cls,
        df: pd.DataFrame,
        target_col: str,
        formula: str,
    ) -> Tuple[pd.DataFrame, str]:
        """
        Safely evaluates mathematical or string expressions between columns.
        Supports:
        - Column tokens in brackets: e.g. [Price] * [Quantity], [Subtotal] + [Tax]
        - Built-in functions: round, abs, upper, lower, strip
        """
        df_copy = df.copy()
        clean_target = target_col.strip()
        if not clean_target:
            raise ValueError("Target column name cannot be empty.")

        # Replace [ColumnName] syntax with safe variable references
        expr = formula.strip()
        cols_in_brackets = re.findall(r"\[(.*?)\]", expr)

        # Build local evaluation namespace
        local_dict = {}
        transformed_expr = expr

        for i, col in enumerate(cols_in_brackets):
            if col not in df_copy.columns:
                raise ValueError(f"Column '{col}' referenced in formula does not exist.")
            var_name = f"_col_{i}"
            transformed_expr = transformed_expr.replace(f"[{col}]", var_name)
            local_dict[var_name] = df_copy[col]

        # Allowed safe built-ins
        safe_builtins = {
            "round": round,
            "abs": abs,
            "min": min,
            "max": max,
            "np": np,
            "pd": pd,
        }

        try:
            # Safe evaluation using pandas/numpy vectorized series
            result = eval(transformed_expr, {"__builtins__": safe_builtins}, local_dict)
            if isinstance(result, (pd.Series, np.ndarray, list)):
                df_copy[clean_target] = result
            else:
                # Constant scalar result
                df_copy[clean_target] = result
        except Exception as e:
            raise ValueError(f"Formula evaluation failed: {str(e)}")

        return df_copy, f"Created calculated column '{clean_target}' = {formula}"

    @classmethod
    def map_column_values(
        cls,
        df: pd.DataFrame,
        source_col: str,
        target_col: str,
        mapping: Dict[str, Any],
        default_val: Optional[Any] = None,
    ) -> Tuple[pd.DataFrame, str]:
        """Maps values from source_col to target_col using a dictionary lookup."""
        df_copy = df.copy()
        if source_col not in df_copy.columns:
            raise ValueError(f"Source column '{source_col}' not found.")

        clean_target = target_col.strip()
        if not clean_target:
            raise ValueError("Target column name cannot be empty.")

        # Clean string keys in mapping
        str_mapping = {str(k).strip(): v for k, v in mapping.items()}

        def apply_map(val):
            val_str = str(val).strip()
            if val_str in str_mapping:
                return str_mapping[val_str]
            elif default_val is not None:
                return default_val
            return val

        df_copy[clean_target] = df_copy[source_col].apply(apply_map)
        return df_copy, f"Mapped '{source_col}' into '{clean_target}' ({len(mapping)} lookup rules)"


class RowOperations:
    """Universal row transformation operations."""

    @classmethod
    def filter_rows(
        cls,
        df: pd.DataFrame,
        col_name: str,
        operator: str,
        target_val: Any = None,
        action: str = "keep",
    ) -> Tuple[pd.DataFrame, str]:
        """Filters rows based on dynamic conditions (keep or drop matching)."""
        df_copy = df.copy()
        if col_name not in df_copy.columns:
            raise ValueError(f"Column '{col_name}' does not exist.")

        series = df_copy[col_name]

        if operator == "equals":
            mask = series.astype(str) == str(target_val)
        elif operator == "not_equals":
            mask = series.astype(str) != str(target_val)
        elif operator == "contains":
            mask = series.astype(str).str.contains(re.escape(str(target_val)), case=False, na=False)
        elif operator == "not_contains":
            mask = ~series.astype(str).str.contains(re.escape(str(target_val)), case=False, na=False)
        elif operator == "starts_with":
            mask = series.astype(str).str.startswith(str(target_val), na=False)
        elif operator == "ends_with":
            mask = series.astype(str).str.endswith(str(target_val), na=False)
        elif operator in ["greater_than", ">"]:
            num_s = pd.to_numeric(series, errors="coerce")
            num_v = float(target_val)
            mask = num_s > num_v
        elif operator in ["greater_equal", ">="]:
            num_s = pd.to_numeric(series, errors="coerce")
            num_v = float(target_val)
            mask = num_s >= num_v
        elif operator in ["less_than", "<"]:
            num_s = pd.to_numeric(series, errors="coerce")
            num_v = float(target_val)
            mask = num_s < num_v
        elif operator in ["less_equal", "<="]:
            num_s = pd.to_numeric(series, errors="coerce")
            num_v = float(target_val)
            mask = num_s <= num_v
        elif operator == "is_null":
            mask = series.isna() | (series.astype(str).str.strip() == "")
        elif operator == "is_not_null":
            mask = series.notna() & (series.astype(str).str.strip() != "")
        elif operator == "in_list":
            items = [str(x).strip() for x in str(target_val).split(",") if str(x).strip()]
            mask = series.astype(str).isin(items)
        else:
            raise ValueError(f"Unsupported operator '{operator}'.")

        initial_len = len(df_copy)
        if action == "keep":
            filtered_df = df_copy[mask].reset_index(drop=True)
            desc = f"Kept rows where '{col_name}' {operator} '{target_val}' ({len(filtered_df)} of {initial_len} retained)"
        else:  # drop
            filtered_df = df_copy[~mask].reset_index(drop=True)
            desc = f"Dropped rows where '{col_name}' {operator} '{target_val}' ({len(filtered_df)} of {initial_len} remaining)"

        return filtered_df, desc

    @classmethod
    def delete_rows_by_indices(cls, df: pd.DataFrame, indices: List[int]) -> Tuple[pd.DataFrame, str]:
        """Deletes rows by explicit positional indices and resets index."""
        df_copy = df.copy()
        valid_indices = [idx for idx in indices if 0 <= idx < len(df_copy)]
        if not valid_indices:
            raise ValueError("No valid row indices specified for deletion.")

        df_copy = df_copy.drop(index=valid_indices).reset_index(drop=True)
        return df_copy, f"Deleted {len(valid_indices)} row(s)"

    @classmethod
    def remove_duplicates(
        cls,
        df: pd.DataFrame,
        subset_cols: Optional[List[str]] = None,
        keep_mode: str = "first",
    ) -> Tuple[pd.DataFrame, str]:
        """Removes duplicate rows across all columns or a subset of key columns."""
        df_copy = df.copy()
        initial_len = len(df_copy)

        subset = [c for c in subset_cols if c in df_copy.columns] if subset_cols else None
        keep_arg = False if keep_mode == "none" else keep_mode

        df_copy = df_copy.drop_duplicates(subset=subset, keep=keep_arg).reset_index(drop=True)
        dropped_count = initial_len - len(df_copy)

        target_desc = f"based on key(s) [{', '.join(subset)}]" if subset else "across all columns"
        return df_copy, f"Removed {dropped_count} duplicate row(s) {target_desc} (kept '{keep_mode}')"

    @classmethod
    def sort_records(
        cls,
        df: pd.DataFrame,
        sort_cols: Optional[List[str]] = None,
        ascending_list: Optional[Union[List[bool], bool]] = None,
        na_position: str = "last",
        by_columns: Optional[List[str]] = None,
        ascending: Optional[Union[List[bool], bool]] = None,
    ) -> Tuple[pd.DataFrame, str]:
        """Sorts DataFrame by one or multiple columns with flexible parameter aliases."""
        df_copy = df.copy()
        raw_cols = sort_cols if sort_cols is not None else by_columns
        if raw_cols is None:
            raise ValueError("No sort columns specified.")
        if isinstance(raw_cols, str):
            raw_cols = [raw_cols]

        valid_cols = [c for c in raw_cols if c in df_copy.columns]
        if not valid_cols:
            raise ValueError("No valid sort columns specified.")

        asc_input = ascending_list if ascending_list is not None else (ascending if ascending is not None else True)
        if isinstance(asc_input, bool):
            asc_list = [asc_input] * len(valid_cols)
        else:
            asc_list = list(asc_input)
            if len(asc_list) != len(valid_cols):
                asc_list = [asc_list[0]] * len(valid_cols)

        df_copy = df_copy.sort_values(by=valid_cols, ascending=asc_list, na_position=na_position).reset_index(drop=True)
        order_desc = ", ".join([f"{c} ({'ASC' if a else 'DESC'})" for c, a in zip(valid_cols, asc_list)])
        return df_copy, f"Sorted records by: {order_desc}"

    @classmethod
    def select_records(cls, df: pd.DataFrame, mode: str = "head", count: int = 10) -> Tuple[pd.DataFrame, str]:
        """Selects a subset of records (head, tail, random sample)."""
        df_copy = df.copy()
        if mode == "head":
            res = df_copy.head(count).reset_index(drop=True)
            desc = f"Selected first {count} rows"
        elif mode == "tail":
            res = df_copy.tail(count).reset_index(drop=True)
            desc = f"Selected last {count} rows"
        elif mode == "random":
            k = min(count, len(df_copy))
            res = df_copy.sample(k, random_state=42).reset_index(drop=True)
            desc = f"Selected random sample of {k} rows"
        else:
            res = df_copy
            desc = "Dataset unchanged"

        return res, desc

    @classmethod
    def insert_row(
        cls,
        df: pd.DataFrame,
        row_data: Dict[str, Any],
        position: str = "bottom",
        index_pos: int = 0,
    ) -> Tuple[pd.DataFrame, str]:
        """Inserts a new row with given column values."""
        df_copy = df.copy()
        # Build series matching df columns
        new_row = {c: row_data.get(c, np.nan) for c in df_copy.columns}
        row_df = pd.DataFrame([new_row])

        if position == "bottom":
            df_copy = pd.concat([df_copy, row_df], ignore_index=True)
            desc = f"Appended new row at index {len(df_copy)-1}"
        elif position == "top":
            df_copy = pd.concat([row_df, df_copy], ignore_index=True)
            desc = "Inserted new row at index 0 (top)"
        else:
            idx = max(0, min(index_pos, len(df_copy)))
            top_part = df_copy.iloc[:idx]
            bottom_part = df_copy.iloc[idx:]
            df_copy = pd.concat([top_part, row_df, bottom_part], ignore_index=True)
            desc = f"Inserted new row at index {idx}"

        return df_copy, desc

    @classmethod
    def update_records_by_key(
        cls,
        df: pd.DataFrame,
        key_col: str,
        key_value: Any,
        target_col: str,
        new_value: Any,
    ) -> Tuple[pd.DataFrame, str]:
        """Updates specific cell(s) where key_col matches key_value."""
        df_copy = df.copy()
        if key_col not in df_copy.columns:
            raise ValueError(f"Key column '{key_col}' does not exist.")
        if target_col not in df_copy.columns:
            raise ValueError(f"Target column '{target_col}' does not exist.")

        mask = df_copy[key_col].astype(str) == str(key_value)
        matched_count = int(mask.sum())
        if matched_count == 0:
            return df_copy, f"No matching records found where '{key_col}' == '{key_value}' (0 updated)"

        df_copy.loc[mask, target_col] = new_value
        return df_copy, f"Updated '{target_col}' = '{new_value}' where '{key_col}' == '{key_value}' ({matched_count} rows updated)"

    @classmethod
    def update_records_by_condition(
        cls,
        df: pd.DataFrame,
        condition_col: str,
        operator: str,
        condition_val: Any,
        target_col: str,
        new_val: Any,
    ) -> Tuple[pd.DataFrame, str]:
        """Updates target_col for records satisfying a condition."""
        df_copy = df.copy()
        if condition_col not in df_copy.columns or target_col not in df_copy.columns:
            raise ValueError("Condition or target column does not exist.")

        # Re-use filter mask logic
        series = df_copy[condition_col]
        if operator == "equals":
            mask = series.astype(str) == str(condition_val)
        elif operator == "contains":
            mask = series.astype(str).str.contains(re.escape(str(condition_val)), case=False, na=False)
        elif operator in ["greater_than", ">"]:
            mask = pd.to_numeric(series, errors="coerce") > float(condition_val)
        elif operator in ["less_than", "<"]:
            mask = pd.to_numeric(series, errors="coerce") < float(condition_val)
        elif operator == "is_null":
            mask = series.isna()
        else:
            mask = series.astype(str) == str(condition_val)

        matched_count = int(mask.sum())
        if matched_count > 0:
            df_copy.loc[mask, target_col] = new_val

        return df_copy, f"Updated '{target_col}' = '{new_val}' where '{condition_col}' {operator} '{condition_val}' ({matched_count} rows updated)"


class StructuralTransformationEngine:
    """Universal structural transformations: Join, Append, Pivot, Unpivot, Aggregate."""

    @classmethod
    def append_datasets(
        cls,
        df1: pd.DataFrame,
        df2: pd.DataFrame,
        source1_name: str = "Source_1",
        source2_name: str = "Source_2",
        add_source_tag: bool = True,
    ) -> Tuple[pd.DataFrame, str]:
        """Appends/stacks two datasets vertically, reconciling column differences."""
        d1 = df1.copy()
        d2 = df2.copy()
        if add_source_tag:
            d1["_source_dataset"] = source1_name
            d2["_source_dataset"] = source2_name

        combined = pd.concat([d1, d2], ignore_index=True)
        return combined, f"Appended datasets: {len(d1)} rows + {len(d2)} rows = {len(combined)} rows"

    @classmethod
    def join_datasets(
        cls,
        left_df: pd.DataFrame,
        right_df: pd.DataFrame,
        left_on: str,
        right_on: str,
        how: str = "inner",
        suffixes: Tuple[str, str] = ("_left", "_right"),
    ) -> Tuple[pd.DataFrame, str]:
        """Joins two datasets on specified key columns."""
        if left_on not in left_df.columns:
            raise ValueError(f"Join key '{left_on}' not found in primary dataset.")
        if right_on not in right_df.columns:
            raise ValueError(f"Join key '{right_on}' not found in secondary dataset.")

        d1 = left_df.copy()
        d2 = right_df.copy()
        d1["__join_key_l"] = d1[left_on].astype(str)
        d2["__join_key_r"] = d2[right_on].astype(str)

        merged = pd.merge(
            d1,
            d2,
            left_on="__join_key_l",
            right_on="__join_key_r",
            how=how,
            suffixes=suffixes,
        )
        merged = merged.drop(columns=["__join_key_l", "__join_key_r"])
        return merged, f"Joined datasets using '{how}' join ({len(merged)} records matched)"

    @classmethod
    def pivot_dataset(
        cls,
        df: pd.DataFrame,
        index_cols: List[str],
        columns_col: str,
        values_col: str,
        aggfunc: str = "sum",
    ) -> Tuple[pd.DataFrame, str]:
        """Pivots tabular dataset from long to wide format and flattens column hierarchy."""
        if not index_cols:
            raise ValueError("Must specify at least one index column.")
        if columns_col not in df.columns or values_col not in df.columns:
            raise ValueError("Pivot column or values column does not exist.")

        df_copy = df.copy()
        if aggfunc in ["sum", "mean", "median", "std"]:
            df_copy[values_col] = pd.to_numeric(df_copy[values_col], errors="coerce")

        pivoted = pd.pivot_table(
            df_copy,
            index=index_cols,
            columns=columns_col,
            values=values_col,
            aggfunc=aggfunc,
        ).reset_index()

        if isinstance(pivoted.columns, pd.MultiIndex):
            pivoted.columns = [
                "_".join([str(c) for c in col if str(c) != ""]).strip()
                for col in pivoted.columns
            ]
        else:
            pivoted.columns = [str(c).strip() for c in pivoted.columns]

        return pivoted, f"Pivoted dataset on '{columns_col}' aggregating '{values_col}' by {aggfunc} ({len(pivoted)} rows, {len(pivoted.columns)} cols)"

    @classmethod
    def unpivot_dataset(
        cls,
        df: pd.DataFrame,
        id_vars: List[str],
        value_vars: List[str],
        var_name: str = "Attribute",
        value_name: str = "Value",
    ) -> Tuple[pd.DataFrame, str]:
        """Unpivots (melts) wide data into long format."""
        if not value_vars:
            raise ValueError("Must select at least one value column to unpivot.")
        melted = pd.melt(
            df.copy(),
            id_vars=id_vars,
            value_vars=value_vars,
            var_name=var_name,
            value_name=value_name,
        )
        return melted, f"Unpivoted {len(value_vars)} column(s) into long format ({len(melted)} rows)"

    @classmethod
    def group_and_aggregate(
        cls,
        df: pd.DataFrame,
        group_by_cols: Optional[List[str]] = None,
        agg_spec: Optional[Dict[str, str]] = None,
        group_cols: Optional[List[str]] = None,
        agg_specs: Optional[Dict[str, str]] = None,
    ) -> Tuple[pd.DataFrame, str]:
        """Groups data by specified fields and computes column aggregations."""
        target_group = group_by_cols if group_by_cols is not None else group_cols
        target_agg = agg_spec if agg_spec is not None else agg_specs

        if not target_group:
            raise ValueError("Must specify at least one group-by column.")
        if not target_agg:
            raise ValueError("Must specify at least one column aggregation.")

        df_copy = df.copy()
        for col, fn in target_agg.items():
            if fn in ["sum", "mean", "median", "std", "min", "max"]:
                df_copy[col] = pd.to_numeric(df_copy[col], errors="coerce")

        grouped = df_copy.groupby(target_group, as_index=False).agg(target_agg)
        return grouped, f"Grouped by [{', '.join(target_group)}] with {len(target_agg)} aggregations ({len(grouped)} rows)"
