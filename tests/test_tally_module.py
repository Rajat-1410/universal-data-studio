"""
Unit Tests for Dedicated TallyPrime Bulk Voucher Updater Module (Phase 6)
"""
import io
import pytest
import pandas as pd
from pathlib import Path
import xml.etree.ElementTree as ET

from modules.tally import (
    TallyReader,
    VoucherMatcher,
    VoucherUpdater,
    TallyValidator,
    TallyExporter,
)
from config import SAMPLES_DIR


@pytest.fixture
def original_tally_xml():
    xml_path = SAMPLES_DIR / "tally_vouchers_original.xml"
    with open(xml_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def revised_excel_df():
    excel_path = SAMPLES_DIR / "tally_vouchers_revised.xlsx"
    return pd.read_excel(excel_path)


def test_tally_reader_parsing(original_tally_xml):
    result = TallyReader.parse_tally_xml(original_tally_xml)

    assert result["company_name"] == "National Trading Co."
    assert result["total_vouchers"] == 4
    assert len(result["vouchers"]) == 4

    # Verify first voucher
    v1 = result["vouchers"][0]
    assert v1["voucher_number"] == "SALES/26-27/001"
    assert v1["guid"] == "7a3c8e92-1b4d-4e5f-9a1c-000000000001"
    assert v1["voucher_type"] == "Sales"
    assert v1["party_name"] == "Apex Solutions Pvt Ltd"
    assert len(v1["ledger_entries"]) == 3

    # Check ledger details and bill allocations
    l1 = v1["ledger_entries"][0]
    assert l1["ledger_name"] == "Apex Solutions Pvt Ltd"
    assert l1["amount"] == -59000.00
    assert l1["is_deemed_positive"] == "Yes"
    assert len(l1["bill_allocations"]) == 1
    assert l1["bill_allocations"][0]["name"] == "SALES/26-27/001"

    # Verify voucher 4 has cost centre
    v4 = result["vouchers"][3]
    assert v4["voucher_number"] == "PMT/26-27/001"
    assert len(v4["ledger_entries"][0]["cost_centres"]) == 1


def test_voucher_matcher_guid_strategy(original_tally_xml, revised_excel_df):
    parsed = TallyReader.parse_tally_xml(original_tally_xml)
    match_res = VoucherMatcher.match_vouchers(
        tally_vouchers=parsed["vouchers"],
        revised_df=revised_excel_df,
        match_by="GUID",
    )

    stats = match_res["stats"]
    assert stats["total_tally_vouchers"] == 4
    assert stats["matched_exact"] == 2  # Voucher 1 and Voucher 2 matched
    assert stats["modified"] == 2       # Both have modified amounts
    assert stats["unmatched_revised"] == 1  # SALES/26-27/099
    assert stats["unmatched_tally"] == 2    # Voucher 3 and Voucher 4 untouched

    # Verify comparison dataframe
    comp_df = match_res["comparison_df"]
    assert len(comp_df) > 0
    modified_rows = comp_df[comp_df["Status"] == "✏️ Modified"]
    assert len(modified_rows) >= 5


def test_voucher_matcher_voucher_number_strategy(original_tally_xml, revised_excel_df):
    parsed = TallyReader.parse_tally_xml(original_tally_xml)
    match_res = VoucherMatcher.match_vouchers(
        tally_vouchers=parsed["vouchers"],
        revised_df=revised_excel_df,
        match_by="VoucherNumber",
    )
    assert match_res["stats"]["matched_exact"] == 2


def test_tally_validator_balanced(original_tally_xml, revised_excel_df):
    parsed = TallyReader.parse_tally_xml(original_tally_xml)
    match_res = VoucherMatcher.match_vouchers(
        tally_vouchers=parsed["vouchers"],
        revised_df=revised_excel_df,
        match_by="GUID",
    )

    val_res = TallyValidator.validate_reconciliation(match_res)
    assert val_res["is_valid"] is True
    assert val_res["can_export"] is True
    assert len(val_res["errors"]) == 0
    assert val_res["stats"]["balanced_count"] == 2
    assert val_res["stats"]["unbalanced_count"] == 0


def test_tally_validator_detects_imbalance(original_tally_xml):
    parsed = TallyReader.parse_tally_xml(original_tally_xml)

    # Intentionally unbalanced revised data (Debit != Credit)
    bad_revised_df = pd.DataFrame([
        {
            "GUID": "7a3c8e92-1b4d-4e5f-9a1c-000000000001",
            "VoucherNumber": "SALES/26-27/001",
            "LedgerName": "Apex Solutions Pvt Ltd",
            "RevisedAmount": -99999.00,  # Unbalanced
        },
        {
            "GUID": "7a3c8e92-1b4d-4e5f-9a1c-000000000001",
            "VoucherNumber": "SALES/26-27/001",
            "LedgerName": "Sales - Hardware",
            "RevisedAmount": 50000.00,
        },
    ])

    match_res = VoucherMatcher.match_vouchers(parsed["vouchers"], bad_revised_df, match_by="GUID")
    val_res = TallyValidator.validate_reconciliation(match_res)

    assert val_res["is_valid"] is False
    assert val_res["can_export"] is False
    assert val_res["stats"]["unbalanced_count"] == 1
    assert any("Accounting Imbalance" in err for err in val_res["errors"])


def test_tally_validator_detects_missing_ledger(original_tally_xml):
    parsed = TallyReader.parse_tally_xml(original_tally_xml)

    # Unknown ledger name
    bad_ledger_df = pd.DataFrame([
        {
            "GUID": "7a3c8e92-1b4d-4e5f-9a1c-000000000001",
            "VoucherNumber": "SALES/26-27/001",
            "LedgerName": "Non Existent Ledger 123",
            "RevisedAmount": -1000.00,
        }
    ])

    match_res = VoucherMatcher.match_vouchers(parsed["vouchers"], bad_ledger_df, match_by="GUID")
    val_res = TallyValidator.validate_reconciliation(match_res)

    assert val_res["is_valid"] is False
    assert any("unknown ledger" in err.lower() for err in val_res["errors"])


def test_voucher_updater_mutation(original_tally_xml, revised_excel_df):
    parsed = TallyReader.parse_tally_xml(original_tally_xml)
    match_res = VoucherMatcher.match_vouchers(parsed["vouchers"], revised_excel_df, match_by="GUID")

    update_res = VoucherUpdater.apply_updates(parsed, match_res, set_alter_action=True)

    assert update_res["stats"]["vouchers_updated"] == 2
    assert update_res["stats"]["ledgers_updated"] >= 5
    assert len(update_res["audit_log"]) >= 5

    updated_xml = update_res["updated_xml_str"]

    # Verify updated amount appears in XML
    assert "70800.00" in updated_xml
    assert "60000.00" in updated_xml
    assert "10800.00" in updated_xml

    # Verify ACTION="Alter" was set on modified vouchers
    assert 'ACTION="Alter"' in updated_xml

    # Verify original GUIDs and structure are 100% intact
    assert "7a3c8e92-1b4d-4e5f-9a1c-000000000001" in updated_xml
    assert "7a3c8e92-1b4d-4e5f-9a1c-000000000004" in updated_xml
    assert "Head Office Mumbai" in updated_xml  # Untouched cost centre

    # Verify re-parsing the updated XML yields exact new values
    reparsed = TallyReader.parse_tally_xml(updated_xml)
    assert reparsed["total_vouchers"] == 4
    v1_updated = reparsed["vouchers"][0]
    apex_ledger = [l for l in v1_updated["ledger_entries"] if l["ledger_name"] == "Apex Solutions Pvt Ltd"][0]
    assert apex_ledger["amount"] == -70800.00


def test_tally_exporter_outputs(original_tally_xml, revised_excel_df):
    parsed = TallyReader.parse_tally_xml(original_tally_xml)
    match_res = VoucherMatcher.match_vouchers(parsed["vouchers"], revised_excel_df, match_by="GUID")
    val_res = TallyValidator.validate_reconciliation(match_res)
    update_res = VoucherUpdater.apply_updates(parsed, match_res)

    # 1. XML export
    xml_export = TallyExporter.export_tally_xml(update_res["updated_xml_str"])
    assert xml_export["filename"].endswith(".xml")
    assert xml_export["size_bytes"] > 0
    assert xml_export["xml_str"].startswith("<?xml")

    # 2. Excel Audit Workbook
    audit_excel_bytes = TallyExporter.export_audit_report(
        company_name=parsed["company_name"],
        matching_result=match_res,
        validation_result=val_res,
        updater_result=update_res,
    )
    assert len(audit_excel_bytes) > 1000

    # Verify audit sheets
    excel_file = pd.ExcelFile(io.BytesIO(audit_excel_bytes))
    assert "Audit_Summary" in excel_file.sheet_names
    assert "Voucher_Balances" in excel_file.sheet_names
    assert "Ledger_Modifications" in excel_file.sheet_names
    assert "Reconciliation_Diff" in excel_file.sheet_names
