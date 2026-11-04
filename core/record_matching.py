"""
Universal Record Matching & Bulk Updating Engine
Performs precise reconciliation between Original and Revised datasets.
Identifies identical, modified, new, deleted/missing, and duplicate records.
Produces side-by-side diff comparisons and executes selective reconciliation.
"""
from typing import Dict, Any, List, Optional, Tuple, Set, Union
import pandas as pd
import numpy as np


class RecordMatchingEngine:
    """Universal record comparison and reconciliation engine."""

    @classmethod
    def _create_composite_key(cls, df: pd.DataFrame, key_cols: List[str]) -> pd.Series:
        """Creates a standardized string composite key from selected key columns."""
        composite = df[key_cols[0]].astype(str).str.strip()
        for col in key_cols[1:]:
            composite = composite + "||" + df[col].astype(str).str.strip()
        return composite

    @classmethod
    def compare_datasets(
        cls,
        original_df: pd.DataFrame,
        revised_df: pd.DataFrame,
        key_columns: Optional[List[str]] = None,
        match_keys: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Deep comparison of Original vs Revised dataset by key columns.
        Returns detailed summary counts, categorized key sets, field deltas, and side-by-side table.
        """
        keys = key_columns if key_columns is not None else match_keys
        if not keys:
            raise ValueError("At least one key column must be selected for matching.")
        key_columns = keys

        for k in keys:
            if k not in original_df.columns:
                raise ValueError(f"Key column '{k}' does not exist in the Original dataset.")
            if k not in revised_df.columns:
                raise ValueError(f"Key column '{k}' does not exist in the Revised dataset.")

        orig_df = original_df.copy()
        rev_df = revised_df.copy()

        # Build composite keys
        orig_keys = cls._create_composite_key(orig_df, keys)
        rev_keys = cls._create_composite_key(rev_df, keys)

        orig_df["_composite_key"] = orig_keys
        rev_df["_composite_key"] = rev_keys

        # Check for duplicate keys within datasets
        orig_dup_mask = orig_df.duplicated(subset=["_composite_key"], keep=False)
        rev_dup_mask = rev_df.duplicated(subset=["_composite_key"], keep=False)

        orig_dup_count = int(orig_dup_mask.sum())
        rev_dup_count = int(rev_dup_mask.sum())

        # Sets of unique keys
        orig_key_set = set(orig_df["_composite_key"].unique())
        rev_key_set = set(rev_df["_composite_key"].unique())

        common_keys = orig_key_set.intersection(rev_key_set)
        new_keys = rev_key_set - orig_key_set
        missing_keys = orig_key_set - rev_key_set

        # Shared non-key columns to compare
        shared_cols = [
            c for c in orig_df.columns
            if c in rev_df.columns and c not in keys and c != "_composite_key"
        ]

        # Map by key for fast lookup (first occurrence if duplicates exist)
        orig_by_key = orig_df.drop_duplicates(subset=["_composite_key"]).set_index("_composite_key")
        rev_by_key = rev_df.drop_duplicates(subset=["_composite_key"]).set_index("_composite_key")

        modified_records = []
        unmodified_records = []
        all_diff_rows = []

        # 1. Compare Common Records
        for k in common_keys:
            r_orig = orig_by_key.loc[k]
            r_rev = rev_by_key.loc[k]

            changed_fields = {}
            row_diff = {"Match_Status": "IDENTICAL", "Key": k}
            for kc in key_columns:
                row_diff[kc] = r_orig[kc]

            for col in shared_cols:
                val_orig = r_orig[col]
                val_rev = r_rev[col]

                # Check equality (handling NaN == NaN)
                is_equal = False
                if pd.isna(val_orig) and pd.isna(val_rev):
                    is_equal = True
                elif isinstance(val_orig, (int, float, np.number)) and isinstance(val_rev, (int, float, np.number)):
                    is_equal = abs(float(val_orig) - float(val_rev)) < 1e-6
                else:
                    is_equal = str(val_orig).strip() == str(val_rev).strip()

                if not is_equal:
                    changed_fields[col] = {
                        "original": val_orig,
                        "revised": val_rev,
                    }
                    row_diff[f"{col} (Orig)"] = val_orig
                    row_diff[f"{col} (Rev)"] = val_rev
                else:
                    row_diff[f"{col} (Orig)"] = val_orig
                    row_diff[f"{col} (Rev)"] = val_rev

            if changed_fields:
                row_diff["Match_Status"] = "MODIFIED"
                row_diff["Changed_Fields"] = ", ".join(changed_fields.keys())
                row_diff["Field_Count"] = len(changed_fields)
                modified_records.append({"key": k, "changes": changed_fields, "details": row_diff})
            else:
                row_diff["Changed_Fields"] = "None"
                row_diff["Field_Count"] = 0
                unmodified_records.append(k)

            all_diff_rows.append(row_diff)

        # 2. Add New Records
        new_records_list = []
        for k in new_keys:
            r_rev = rev_by_key.loc[k]
            row_diff = {"Match_Status": "NEW_IN_REVISED", "Key": k, "Changed_Fields": "ALL (New Record)", "Field_Count": len(rev_df.columns)}
            for kc in key_columns:
                row_diff[kc] = r_rev[kc]
            for col in shared_cols:
                row_diff[f"{col} (Orig)"] = np.nan
                row_diff[f"{col} (Rev)"] = r_rev[col]
            new_records_list.append(row_diff)
            all_diff_rows.append(row_diff)

        # 3. Add Missing / Deleted Records
        missing_records_list = []
        for k in missing_keys:
            r_orig = orig_by_key.loc[k]
            row_diff = {"Match_Status": "MISSING_IN_REVISED", "Key": k, "Changed_Fields": "MISSING (Deleted)", "Field_Count": 0}
            for kc in key_columns:
                row_diff[kc] = r_orig[kc]
            for col in shared_cols:
                row_diff[f"{col} (Orig)"] = r_orig[col]
                row_diff[f"{col} (Rev)"] = np.nan
            missing_records_list.append(row_diff)
            all_diff_rows.append(row_diff)

        # Build comparison DataFrame
        comparison_df = pd.DataFrame(all_diff_rows) if all_diff_rows else pd.DataFrame()

        summary = {
            "total_original": len(orig_df),
            "total_revised": len(rev_df),
            "matched_keys": len(common_keys),
            "modified_count": len(modified_records),
            "unmodified_count": len(unmodified_records),
            "new_count": len(new_keys),
            "missing_count": len(missing_keys),
            "orig_duplicate_keys": orig_dup_count,
            "rev_duplicate_keys": rev_dup_count,
            "shared_columns": shared_cols,
            "key_columns": keys,
        }

        return {
            "summary": summary,
            "comparison_df": comparison_df,
            "modified_records": modified_records,
            "new_keys": list(new_keys),
            "missing_keys": list(missing_keys),
        }

    @classmethod
    def reconcile_datasets(
        cls,
        original_df: pd.DataFrame,
        revised_df: pd.DataFrame,
        key_columns: Optional[Union[List[str], Dict[str, Any]]] = None,
        update_modified: bool = True,
        insert_new: bool = True,
        remove_missing: bool = False,
        columns_to_update: Optional[List[str]] = None,
        match_keys: Optional[List[str]] = None,
        update_existing: Optional[bool] = None,
    ) -> Tuple[pd.DataFrame, str, Dict[str, int]]:
        """
        Executes selective dataset reconciliation based on comparison results.
        Outputs a fresh reconciled dataset without modifying original data.
        """
        # Resolve key columns or match_result dict
        if isinstance(key_columns, dict):
            keys = key_columns.get("summary", {}).get("key_columns", [])
        else:
            keys = key_columns if key_columns is not None else match_keys

        if not keys:
            raise ValueError("No matching key columns provided for reconciliation.")

        if update_existing is not None:
            update_modified = update_existing

        comparison = cls.compare_datasets(original_df, revised_df, keys)
        orig_copy = original_df.copy()
        rev_copy = revised_df.copy()

        orig_copy["_comp_key"] = cls._create_composite_key(orig_copy, keys)
        rev_copy["_comp_key"] = cls._create_composite_key(rev_copy, keys)

        updated_count = 0
        inserted_count = 0
        removed_count = 0

        # Determine target update columns
        shared_cols = comparison["summary"]["shared_columns"]
        target_cols = [c for c in columns_to_update if c in shared_cols] if columns_to_update else shared_cols

        # 1. Update Modified Records
        if update_modified and target_cols:
            rev_lookup = rev_copy.drop_duplicates(subset=["_comp_key"]).set_index("_comp_key")
            for mod in comparison["modified_records"]:
                k = mod["key"]
                if k in rev_lookup.index:
                    mask = orig_copy["_comp_key"] == k
                    for col in target_cols:
                        orig_copy.loc[mask, col] = rev_lookup.loc[k, col]
                    updated_count += 1

        # 2. Remove Missing Records (if enabled)
        if remove_missing and comparison["missing_keys"]:
            missing_set = set(comparison["missing_keys"])
            mask_keep = ~orig_copy["_comp_key"].isin(missing_set)
            removed_count = len(orig_copy) - int(mask_keep.sum())
            orig_copy = orig_copy[mask_keep].reset_index(drop=True)

        # 3. Insert New Records
        if insert_new and comparison["new_keys"]:
            new_set = set(comparison["new_keys"])
            new_rows = rev_copy[rev_copy["_comp_key"].isin(new_set)].copy()

            # Align columns: retain union of columns
            for col in orig_copy.columns:
                if col not in new_rows.columns and col != "_comp_key":
                    new_rows[col] = np.nan

            cols_order = [c for c in orig_copy.columns if c in new_rows.columns]
            orig_copy = pd.concat([orig_copy, new_rows[cols_order]], ignore_index=True)
            inserted_count = len(new_rows)

        # Clean helper column
        if "_comp_key" in orig_copy.columns:
            orig_copy = orig_copy.drop(columns=["_comp_key"])

        counts = {
            "updated": updated_count,
            "inserted": inserted_count,
            "removed": removed_count,
            "final_rows": len(orig_copy),
        }
        desc = (
            f"Reconciliation completed: {updated_count} modified records updated, "
            f"{inserted_count} new records inserted, {removed_count} missing records removed. "
            f"Final row count: {len(orig_copy)}"
        )
        return orig_copy, desc, counts
