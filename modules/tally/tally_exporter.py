"""
Tally Exporter (Phase 6)
Serializes import-ready TallyPrime XML documents and creates multi-tab Excel audit reports.
"""
import io
from typing import Dict, Any, Optional
import xml.etree.ElementTree as ET
import pandas as pd


class TallyExporter:
    """Exports compliant Tally XML import files and comprehensive reconciliation audit workbooks."""

    @classmethod
    def export_tally_xml(
        cls,
        xml_str: str,
        filename_prefix: str = "tally_import_ready",
    ) -> Dict[str, Any]:
        """
        Validates syntax and formats XML ready for TallyPrime import.
        """
        if not xml_str or not xml_str.strip():
            raise ValueError("XML content is empty.")

        # Validate syntax
        try:
            ET.fromstring(xml_str)
        except ET.ParseError as pe:
            raise ValueError(f"XML export validation failed: {str(pe)}")

        # Ensure XML declaration
        clean_xml = xml_str.strip()
        if not clean_xml.startswith("<?xml"):
            clean_xml = '<?xml version="1.0" encoding="utf-8"?>\n' + clean_xml

        xml_bytes = clean_xml.encode("utf-8")
        filename = f"{filename_prefix}.xml"

        return {
            "filename": filename,
            "xml_str": clean_xml,
            "xml_bytes": xml_bytes,
            "size_bytes": len(xml_bytes),
        }

    @classmethod
    def export_audit_report(
        cls,
        company_name: str,
        matching_result: Dict[str, Any],
        validation_result: Dict[str, Any],
        updater_result: Dict[str, Any],
    ) -> bytes:
        """
        Creates an executive audit workbook in Excel format containing:
        - Sheet 1: Summary KPI metrics
        - Sheet 2: Voucher Balance Verification
        - Sheet 3: Ledger Modifications Audit Log
        - Sheet 4: Full Reconciliation Diff
        """
        buf = io.BytesIO()

        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            # 1. Summary Sheet
            m_stats = matching_result.get("stats", {})
            v_stats = validation_result.get("stats", {})
            u_stats = updater_result.get("stats", {})

            summary_rows = [
                {"Metric": "Company Name", "Value": company_name},
                {"Metric": "Effective Matching Strategy", "Value": matching_result.get("effective_match_by", "GUID")},
                {"Metric": "Total Tally Vouchers in XML", "Value": m_stats.get("total_tally_vouchers", 0)},
                {"Metric": "Matched Vouchers", "Value": m_stats.get("matched_exact", 0)},
                {"Metric": "Modified Vouchers", "Value": m_stats.get("modified", 0)},
                {"Metric": "Identical Vouchers (No Change)", "Value": m_stats.get("identical", 0)},
                {"Metric": "Unmatched Revised Rows", "Value": m_stats.get("unmatched_revised", 0)},
                {"Metric": "Untouched Tally Vouchers", "Value": m_stats.get("unmatched_tally", 0)},
                {"Metric": "Duplicate Key Conflicts", "Value": m_stats.get("duplicate_tally_matches", 0)},
                {"Metric": "Missing Ledgers Detected", "Value": m_stats.get("missing_ledgers", 0)},
                {"Metric": "Accounting Balance Status", "Value": "Balanced (100%)" if validation_result.get("is_valid") else "Imbalanced"},
                {"Metric": "Total Vouchers Updated in XML", "Value": u_stats.get("vouchers_updated", 0)},
                {"Metric": "Total Ledger Lines Updated in XML", "Value": u_stats.get("ledgers_updated", 0)},
            ]
            pd.DataFrame(summary_rows).to_excel(writer, index=False, sheet_name="Audit_Summary")

            # 2. Voucher Balances Sheet
            bal_df = validation_result.get("balance_df")
            if bal_df is not None and not bal_df.empty:
                bal_df.to_excel(writer, index=False, sheet_name="Voucher_Balances")

            # 3. Ledger Modifications Sheet
            audit_log = updater_result.get("audit_log", [])
            if audit_log:
                pd.DataFrame(audit_log).to_excel(writer, index=False, sheet_name="Ledger_Modifications")
            else:
                pd.DataFrame({"Message": ["No ledger modifications performed."]}).to_excel(
                    writer, index=False, sheet_name="Ledger_Modifications"
                )

            # 4. Full Reconciliation Diff Sheet
            comp_df = matching_result.get("comparison_df")
            if comp_df is not None and not comp_df.empty:
                comp_df.to_excel(writer, index=False, sheet_name="Reconciliation_Diff")

        return buf.getvalue()
