"""
Tally Voucher Matcher (Phase 6)
Matches existing vouchers between Tally XML and revised Excel data.
Preserves GUID identity, detects duplicate matches, and flags missing ledgers.
"""
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
import numpy as np


class VoucherMatcher:
    """Reconciles vouchers between Tally XML and revised Excel datasets."""

    @classmethod
    def match_vouchers(
        cls,
        tally_vouchers: List[Dict[str, Any]],
        revised_df: pd.DataFrame,
        match_by: str = "Auto",
        guid_col: Optional[str] = None,
        vch_num_col: Optional[str] = None,
        date_col: Optional[str] = None,
        ledger_col: Optional[str] = None,
        amount_col: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Reconciles vouchers and identifies modified, identical, unmatched, and ambiguous records.
        """
        if not tally_vouchers:
            raise ValueError("No Tally vouchers provided for matching.")
        if revised_df is None or revised_df.empty:
            raise ValueError("Revised Excel dataset is empty.")

        # Resolve column names in revised_df case-insensitively
        col_map_lower = {str(c).lower().replace(" ", "").replace("_", ""): c for c in revised_df.columns}

        resolved_guid_col = guid_col or col_map_lower.get("guid")
        resolved_vch_col = vch_num_col or col_map_lower.get("vouchernumber") or col_map_lower.get("voucherno") or col_map_lower.get("vchnum") or col_map_lower.get("invoicenumber")
        resolved_date_col = date_col or col_map_lower.get("date") or col_map_lower.get("voucherdate")
        resolved_ledger_col = ledger_col or col_map_lower.get("ledgername") or col_map_lower.get("ledger") or col_map_lower.get("account") or col_map_lower.get("particulars")
        resolved_amt_col = amount_col or col_map_lower.get("revisedamount") or col_map_lower.get("amount") or col_map_lower.get("newamount") or col_map_lower.get("total")

        if not resolved_ledger_col:
            raise ValueError("Could not find a Ledger Name column in revised Excel. Please specify ledger column.")
        if not resolved_amt_col:
            raise ValueError("Could not find an Amount column in revised Excel. Please specify amount column.")

        # Determine effective match strategy
        if match_by == "Auto":
            if resolved_guid_col and revised_df[resolved_guid_col].dropna().nunique() > 0:
                effective_match_by = "GUID"
            elif resolved_vch_col:
                effective_match_by = "VoucherNumber"
            else:
                raise ValueError("Could not find GUID or VoucherNumber column in revised Excel for matching.")
        else:
            effective_match_by = match_by

        # Build Tally Lookup Index
        tally_index: Dict[str, List[Dict[str, Any]]] = {}
        for v in tally_vouchers:
            if effective_match_by == "GUID":
                k = str(v["guid"]).strip()
            elif effective_match_by == "VoucherNumber + Date":
                k = f"{str(v['voucher_number']).strip().upper()}|{str(v['date']).strip()}"
            else:
                k = str(v["voucher_number"]).strip().upper()

            if k:
                if k not in tally_index:
                    tally_index[k] = []
                tally_index[k].append(v)

        # Detect Duplicate Keys in Tally XML
        duplicate_tally_keys = {k: len(v_list) for k, v_list in tally_index.items() if len(v_list) > 1}

        # Index revised Excel rows by match key
        revised_records_by_key: Dict[str, List[Dict[str, Any]]] = {}
        for _, row in revised_df.iterrows():
            if effective_match_by == "GUID" and resolved_guid_col:
                k = str(row[resolved_guid_col]).strip() if pd.notna(row[resolved_guid_col]) else ""
            elif effective_match_by == "VoucherNumber + Date" and resolved_vch_col and resolved_date_col:
                v_num = str(row[resolved_vch_col]).strip().upper() if pd.notna(row[resolved_vch_col]) else ""
                v_date = str(row[resolved_date_col]).strip() if pd.notna(row[resolved_date_col]) else ""
                k = f"{v_num}|{v_date}"
            elif resolved_vch_col:
                k = str(row[resolved_vch_col]).strip().upper() if pd.notna(row[resolved_vch_col]) else ""
            else:
                k = ""

            if not k:
                continue

            ledger_name = str(row[resolved_ledger_col]).strip() if pd.notna(row[resolved_ledger_col]) else ""
            try:
                amt = float(row[resolved_amt_col]) if pd.notna(row[resolved_amt_col]) else 0.0
            except ValueError:
                amt = 0.0

            if k not in revised_records_by_key:
                revised_records_by_key[k] = []
            revised_records_by_key[k].append({
                "ledger_name": ledger_name,
                "revised_amount": amt,
                "raw_row": row.to_dict(),
            })

        # Match and Categorize
        reconciled_vouchers = []
        comparison_rows = []
        matched_tally_keys = set()

        stats = {
            "total_tally_vouchers": len(tally_vouchers),
            "total_revised_groups": len(revised_records_by_key),
            "matched_exact": 0,
            "modified": 0,
            "identical": 0,
            "missing_ledgers": 0,
            "unmatched_revised": 0,
            "unmatched_tally": 0,
            "duplicate_tally_matches": len(duplicate_tally_keys),
        }

        # 1. Process Revised Keys
        for key, rev_entries in revised_records_by_key.items():
            if key not in tally_index:
                stats["unmatched_revised"] += 1
                for r in rev_entries:
                    comparison_rows.append({
                        "MatchKey": key,
                        "VoucherNumber": r["raw_row"].get(resolved_vch_col, key),
                        "Status": "❌ Unmatched in Tally",
                        "LedgerName": r["ledger_name"],
                        "TallyAmount": np.nan,
                        "RevisedAmount": r["revised_amount"],
                        "Difference": np.nan,
                        "Notes": "Voucher not found in Tally XML export",
                    })
                continue

            tally_matches = tally_index[key]

            # Ambiguous identity safety check
            if len(tally_matches) > 1:
                for r in rev_entries:
                    comparison_rows.append({
                        "MatchKey": key,
                        "VoucherNumber": r["raw_row"].get(resolved_vch_col, key),
                        "Status": "⚠️ Ambiguous Match (Duplicate)",
                        "LedgerName": r["ledger_name"],
                        "TallyAmount": np.nan,
                        "RevisedAmount": r["revised_amount"],
                        "Difference": np.nan,
                        "Notes": f"Safety Stop: {len(tally_matches)} vouchers share this key in Tally XML. Use GUID matching.",
                    })
                continue

            # Exact Single Voucher Match
            matched_tally_keys.add(key)
            tally_voucher = tally_matches[0]
            existing_ledgers = {l["ledger_name"].strip().lower(): l for l in tally_voucher["ledger_entries"]}

            voucher_has_changes = False
            voucher_has_missing_ledger = False
            ledger_updates = []

            for r in rev_entries:
                r_l_clean = r["ledger_name"].strip().lower()
                r_amt = r["revised_amount"]

                if r_l_clean in existing_ledgers:
                    orig_entry = existing_ledgers[r_l_clean]
                    orig_amt = orig_entry["amount"]
                    diff = r_amt - orig_amt

                    is_modified = abs(diff) > 0.001
                    if is_modified:
                        voucher_has_changes = True

                    ledger_updates.append({
                        "ledger_name": orig_entry["ledger_name"],
                        "original_amount": orig_amt,
                        "revised_amount": r_amt,
                        "difference": diff,
                        "is_modified": is_modified,
                        "is_missing": False,
                    })

                    comparison_rows.append({
                        "MatchKey": key,
                        "VoucherNumber": tally_voucher["voucher_number"],
                        "Status": "✏️ Modified" if is_modified else "✅ Identical",
                        "LedgerName": orig_entry["ledger_name"],
                        "TallyAmount": orig_amt,
                        "RevisedAmount": r_amt,
                        "Difference": diff,
                        "Notes": f"Delta: {diff:+.2f}" if is_modified else "Match confirmed",
                    })
                else:
                    voucher_has_missing_ledger = True
                    stats["missing_ledgers"] += 1
                    ledger_updates.append({
                        "ledger_name": r["ledger_name"],
                        "original_amount": np.nan,
                        "revised_amount": r_amt,
                        "difference": np.nan,
                        "is_modified": False,
                        "is_missing": True,
                    })
                    comparison_rows.append({
                        "MatchKey": key,
                        "VoucherNumber": tally_voucher["voucher_number"],
                        "Status": "⚠️ Missing Ledger in Tally",
                        "LedgerName": r["ledger_name"],
                        "TallyAmount": np.nan,
                        "RevisedAmount": r_amt,
                        "Difference": np.nan,
                        "Notes": "Ledger does not exist in original voucher",
                    })

            if voucher_has_changes:
                stats["modified"] += 1
            else:
                stats["identical"] += 1
            stats["matched_exact"] += 1

            reconciled_vouchers.append({
                "tally_voucher": tally_voucher,
                "key": key,
                "has_changes": voucher_has_changes,
                "has_missing_ledger": voucher_has_missing_ledger,
                "ledger_updates": ledger_updates,
                "can_update": not voucher_has_missing_ledger,
            })

        # 2. Check Untouched Tally Vouchers
        for v in tally_vouchers:
            if effective_match_by == "GUID":
                k = str(v["guid"]).strip()
            elif effective_match_by == "VoucherNumber + Date":
                k = f"{str(v['voucher_number']).strip().upper()}|{str(v['date']).strip()}"
            else:
                k = str(v["voucher_number"]).strip().upper()

            if k not in matched_tally_keys and k not in duplicate_tally_keys:
                stats["unmatched_tally"] += 1
                for l in v["ledger_entries"]:
                    comparison_rows.append({
                        "MatchKey": k,
                        "VoucherNumber": v["voucher_number"],
                        "Status": "⚪ Untouched in Tally",
                        "LedgerName": l["ledger_name"],
                        "TallyAmount": l["amount"],
                        "RevisedAmount": np.nan,
                        "Difference": 0.0,
                        "Notes": "No update in revised Excel (preserved intact)",
                    })

        comparison_df = pd.DataFrame(comparison_rows) if comparison_rows else pd.DataFrame(
            columns=["MatchKey", "VoucherNumber", "Status", "LedgerName", "TallyAmount", "RevisedAmount", "Difference", "Notes"]
        )

        return {
            "effective_match_by": effective_match_by,
            "reconciled_vouchers": reconciled_vouchers,
            "comparison_df": comparison_df,
            "stats": stats,
            "duplicate_tally_keys": duplicate_tally_keys,
            "resolved_columns": {
                "guid": resolved_guid_col,
                "voucher_number": resolved_vch_col,
                "date": resolved_date_col,
                "ledger_name": resolved_ledger_col,
                "amount": resolved_amt_col,
            },
        }
