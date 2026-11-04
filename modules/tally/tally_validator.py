"""
Tally Accounting Validator (Phase 6)
Validates double-entry accounting integrity, debit/credit totals,
ledger existence, and prevents destructive overwrites on ambiguous voucher matches.
"""
from typing import Dict, Any, List, Optional
import pandas as pd


class TallyValidator:
    """Validates accounting rules and structural safety for Tally voucher updates."""

    @classmethod
    def validate_reconciliation(
        cls,
        matching_result: Dict[str, Any],
        tolerance: float = 0.01,
    ) -> Dict[str, Any]:
        """
        Performs comprehensive accounting validation:
        1. Debit / Credit balance per voucher
        2. Missing ledgers detection
        3. Ambiguous duplicate voucher match prevention
        """
        reconciled_vouchers = matching_result.get("reconciled_vouchers", [])
        duplicate_keys = matching_result.get("duplicate_tally_keys", {})

        errors = []
        warnings = []
        balance_rows = []

        # 1. Check for Duplicate Keys in Tally XML
        if duplicate_keys:
            dup_details = ", ".join([f"'{k}' ({cnt} vouchers)" for k, cnt in duplicate_keys.items()])
            errors.append(
                f"Duplicate Voucher Keys detected in Tally XML: {dup_details}. "
                f"Cannot update vouchers by ambiguous keys. Switch match strategy to 'GUID'."
            )

        # 2. Per-Voucher Balance Verification
        total_balanced = 0
        total_unbalanced = 0

        for r_vch in reconciled_vouchers:
            t_vch = r_vch["tally_voucher"]
            vch_num = t_vch["voucher_number"] or t_vch["guid"]

            # Missing ledger check
            if r_vch.get("has_missing_ledger"):
                missing_names = [l["ledger_name"] for l in r_vch["ledger_updates"] if l.get("is_missing")]
                errors.append(
                    f"Voucher '{vch_num}' references unknown ledger(s) not in original Tally XML: {', '.join(missing_names)}"
                )

            # Build projected ledger amounts
            updates_by_ledger = {
                l["ledger_name"].strip().lower(): l["revised_amount"]
                for l in r_vch["ledger_updates"]
                if not l.get("is_missing")
            }

            projected_amounts = []
            projected_debits = 0.0
            projected_credits = 0.0

            for entry in t_vch["ledger_entries"]:
                l_key = entry["ledger_name"].strip().lower()
                amt = updates_by_ledger.get(l_key, entry["amount"])
                projected_amounts.append(amt)

                is_pos = entry["is_deemed_positive"]
                if is_pos == "Yes" or amt < 0:
                    projected_debits += abs(amt)
                else:
                    projected_credits += abs(amt)

            # Check Tally algebraic sum (Debit is negative, Credit is positive -> sum = 0)
            algebraic_sum = sum(projected_amounts)
            debit_credit_diff = abs(projected_debits - projected_credits)

            # Considered balanced if algebraic sum == 0 or sum(debits) == sum(credits)
            is_balanced = (abs(algebraic_sum) <= tolerance) or (debit_credit_diff <= tolerance)

            variance = min(abs(algebraic_sum), debit_credit_diff)

            if is_balanced:
                total_balanced += 1
                status_str = "✅ Balanced"
            else:
                total_unbalanced += 1
                status_str = f"❌ Unbalanced (Diff: {variance:.2f})"
                errors.append(
                    f"Accounting Imbalance in Voucher '{vch_num}': Total Debit ({projected_debits:.2f}) "
                    f"does not match Total Credit ({projected_credits:.2f}). Variance: {variance:.2f}"
                )

            balance_rows.append({
                "VoucherNumber": vch_num,
                "GUID": t_vch["guid"],
                "ProjectedDebit": projected_debits,
                "ProjectedCredit": projected_credits,
                "Variance": variance,
                "Status": status_str,
                "HasChanges": "Yes" if r_vch.get("has_changes") else "No",
            })

        balance_df = pd.DataFrame(balance_rows) if balance_rows else pd.DataFrame(
            columns=["VoucherNumber", "GUID", "ProjectedDebit", "ProjectedCredit", "Variance", "Status", "HasChanges"]
        )

        can_export = (len(errors) == 0) and (total_balanced > 0 or len(reconciled_vouchers) == 0)

        return {
            "is_valid": len(errors) == 0,
            "can_export": can_export,
            "errors": errors,
            "warnings": warnings,
            "balance_df": balance_df,
            "stats": {
                "total_vouchers_checked": len(reconciled_vouchers),
                "balanced_count": total_balanced,
                "unbalanced_count": total_unbalanced,
                "error_count": len(errors),
                "warning_count": len(warnings),
            },
        }
