"""
Full Application End-to-End Integration Test Suite
Validates the complete pipeline across all phases: Ingestion -> Profiling -> Customisation
-> Cleaning -> Matching -> XML Studio -> TallyPrime Updater -> Undo/Redo & Export.
"""
import io
import json
import pytest
import pandas as pd
import numpy as np

from config import SAMPLES_DIR
from utils.session_manager import SessionManager
from utils.helpers import calculate_dataset_health, detect_date_inconsistencies, compute_column_outliers
from core.file_reader import FileReaderRegistry, UniversalInspector
from core.transformations import ColumnOperations, RowOperations, StructuralTransformationEngine
from core.data_cleaning import DataCleaningEngine
from core.record_matching import RecordMatchingEngine
from core.xml_engine import UniversalXmlEditor, UniversalFormatConverter
from modules.tally import TallyReader, VoucherMatcher, VoucherUpdater, TallyValidator, TallyExporter
from core.workflow_engine import WorkflowDefinition, WorkflowStep, WorkflowEngine
from core.nlp_engine import NaturalLanguageEngine
from core.validation_engine import ValidationEngine


def test_full_application_lifecycle():
    # -------------------------------------------------------------
    # 1. INGESTION TEST ACROSS ALL 6 SUPPORTED FORMATS
    # -------------------------------------------------------------
    SessionManager.clear_all()

    sample_files = [
        "sample_sales.xlsx",
        "sample_customers.csv",
        "sample_data.xml",
        "sample_inventory.json",
        "sample_log.txt",
        "sample_archive.zip",
    ]

    for fname in sample_files:
        fpath = SAMPLES_DIR / fname
        assert fpath.exists(), f"Sample file {fname} not found in {SAMPLES_DIR}"
        with open(fpath, "rb") as f:
            fid = SessionManager.add_uploaded_file(fname, f.read())
            assert fid is not None

    all_files = SessionManager.get_all_files()
    assert len(all_files) == 6

    # -------------------------------------------------------------
    # 2. UNIVERSAL INSPECTION & HEALTH SCORING
    # -------------------------------------------------------------
    sales_file = next(f for f in all_files.values() if f["filename"] == "sample_sales.xlsx")
    SessionManager.set_active_file(sales_file["file_id"])
    active_df = SessionManager.get_active_df()
    assert active_df is not None
    assert len(active_df) > 0

    # Profile active dataset
    health = calculate_dataset_health(active_df)
    assert 0 <= health["score"] <= 100
    assert health["grade"] in ["A+", "A", "B", "C", "D", "F"]

    date_anomalies = detect_date_inconsistencies(active_df["OrderDate"])
    assert isinstance(date_anomalies, dict)

    # -------------------------------------------------------------
    # 3. COLUMN OPERATIONS & FORMULA CALCULATIONS
    # -------------------------------------------------------------
    df_step1, msg = ColumnOperations.calculate_column(
        active_df,
        target_col="AmountWithTax",
        formula="[Amount] * 1.18",
    )
    assert "AmountWithTax" in df_step1.columns
    SessionManager.update_working_df(df_step1, "Calculate Column", msg)

    df_step2, msg = ColumnOperations.rename_columns(
        SessionManager.get_active_df(),
        {"Region": "SalesRegion"},
    )
    assert "SalesRegion" in df_step2.columns
    assert "Region" not in df_step2.columns
    SessionManager.update_working_df(df_step2, "Rename Column", msg)

    # -------------------------------------------------------------
    # 4. ROW OPERATIONS & DEDUPLICATION
    # -------------------------------------------------------------
    df_step3, msg = RowOperations.filter_rows(
        SessionManager.get_active_df(),
        col_name="SalesRegion",
        operator="is_not_null",
    )
    SessionManager.update_working_df(df_step3, "Filter Rows", msg)

    df_step4, msg = RowOperations.sort_records(
        SessionManager.get_active_df(),
        by_columns=["AmountWithTax"],
        ascending=False,
    )
    assert df_step4.iloc[0]["AmountWithTax"] >= df_step4.iloc[-1]["AmountWithTax"]
    SessionManager.update_working_df(df_step4, "Sort Records", msg)

    # -------------------------------------------------------------
    # 5. DATA CLEANING & STANDARDIZATION
    # -------------------------------------------------------------
    df_step5, msg = DataCleaningEngine.standardize_text(
        SessionManager.get_active_df(),
        col_name="SalesRegion",
        operations=["trim", "uppercase"],
    )
    SessionManager.update_working_df(df_step5, "Standardize Text", msg)

    # -------------------------------------------------------------
    # 6. STRUCTURAL TRANSFORMATIONS (GROUP & AGGREGATE)
    # -------------------------------------------------------------
    agg_df, msg = StructuralTransformationEngine.group_and_aggregate(
        SessionManager.get_active_df(),
        group_cols=["SalesRegion"],
        agg_specs={"Amount": "sum"},
    )
    assert len(agg_df) > 0
    assert "Amount" in agg_df.columns

    # -------------------------------------------------------------
    # 7. UNDO / REDO ENGINE VERIFICATION
    # -------------------------------------------------------------
    assert SessionManager.can_undo() is True
    # Undo step 5
    undone_df = SessionManager.undo()
    assert undone_df is not None
    # Redo step 5
    assert SessionManager.can_redo() is True
    redone_df = SessionManager.redo()
    assert redone_df is not None

    # -------------------------------------------------------------
    # 8. RECORD MATCHING & BULK RECONCILIATION
    # -------------------------------------------------------------
    orig_match_path = SAMPLES_DIR / "matching_orders_original.xlsx"
    rev_match_path = SAMPLES_DIR / "matching_orders_revised.xlsx"
    df_orig = pd.read_excel(orig_match_path)
    df_rev = pd.read_excel(rev_match_path)

    match_result = RecordMatchingEngine.compare_datasets(df_orig, df_rev, match_keys=["OrderID"])
    assert match_result["summary"]["total_original"] > 0
    assert match_result["summary"]["modified_count"] > 0
    assert match_result["summary"]["new_count"] > 0

    reconciled_df, log_msg, counts = RecordMatchingEngine.reconcile_datasets(
        df_orig, df_rev, match_result, update_existing=True, insert_new=True, remove_missing=False
    )
    assert len(reconciled_df) >= len(df_orig)

    # -------------------------------------------------------------
    # 9. UNIVERSAL XML STUDIO VERIFICATION
    # -------------------------------------------------------------
    xml_sample_path = SAMPLES_DIR / "sample_data.xml"
    with open(xml_sample_path, "r", encoding="utf-8") as xf:
        raw_xml = xf.read()

    # Syntax & structural summary
    is_valid, _ = UniversalXmlEditor.validate_xml_syntax(raw_xml)
    assert is_valid is True
    summary = UniversalXmlEditor.get_xml_structural_summary(raw_xml)
    assert summary["root_tag"] == "TRANSACTIONS"

    # Search & Edit node text
    nodes = UniversalXmlEditor.search_nodes(raw_xml, "VOUCHERNUMBER", search_by="tag")
    assert len(nodes) > 0

    edited_xml, _ = UniversalXmlEditor.edit_node_text(raw_xml, "PARTYNAME", "Updated Client Ltd", occurrence_idx=0)
    assert "Updated Client Ltd" in edited_xml

    # Tabular mapping with nested elements
    mapped_xml = UniversalXmlEditor.map_tabular_to_xml(
        SessionManager.get_active_df().head(5),
        root_tag="BATCH",
        record_tag="ROW",
        mapping={"OrderID": "@id", "SalesRegion": "GEO/REGION", "AmountWithTax": "FINANCIAL/TOTAL"},
    )
    valid_mapped, _ = UniversalXmlEditor.validate_xml_syntax(mapped_xml)
    assert valid_mapped is True
    assert "<BATCH>" in mapped_xml
    assert "<GEO>" in mapped_xml

    # Cross format conversion
    csv_str = UniversalFormatConverter.excel_to_csv(sales_file["raw_bytes"])
    excel_back = UniversalFormatConverter.csv_to_excel(csv_str)
    assert len(excel_back) > 0

    # -------------------------------------------------------------
    # 10. TALLYPRIME BULK VOUCHER UPDATER (PHASE 6)
    # -------------------------------------------------------------
    tally_xml_path = SAMPLES_DIR / "tally_vouchers_original.xml"
    tally_rev_path = SAMPLES_DIR / "tally_vouchers_revised.xlsx"
    with open(tally_xml_path, "r", encoding="utf-8") as tf:
        tally_raw = tf.read()
    tally_rev_df = pd.read_excel(tally_rev_path)

    # Parse Tally XML
    parsed_tally = TallyReader.parse_tally_xml(tally_raw)
    assert parsed_tally["total_vouchers"] == 4
    assert parsed_tally["company_name"] == "National Trading Co."

    # Match vouchers
    tally_match = VoucherMatcher.match_vouchers(parsed_tally["vouchers"], tally_rev_df, match_by="GUID")
    assert tally_match["stats"]["matched_exact"] == 2
    assert tally_match["stats"]["modified"] == 2

    # Validate accounting double-entry balance
    val_tally = TallyValidator.validate_reconciliation(tally_match)
    assert val_tally["is_valid"] is True
    assert val_tally["can_export"] is True

    # Apply updates with lossless structure preservation
    tally_update = VoucherUpdater.apply_updates(parsed_tally, tally_match, set_alter_action=True)
    assert tally_update["stats"]["vouchers_updated"] == 2
    assert 'ACTION="Alter"' in tally_update["updated_xml_str"]
    assert "7a3c8e92-1b4d-4e5f-9a1c-000000000001" in tally_update["updated_xml_str"]

    # Export XML and Audit Excel workbook
    exported_xml = TallyExporter.export_tally_xml(tally_update["updated_xml_str"])
    assert exported_xml["size_bytes"] > 0

    audit_wb = TallyExporter.export_audit_report(
        company_name=parsed_tally["company_name"],
        matching_result=tally_match,
        validation_result=val_tally,
        updater_result=tally_update,
    )
    assert len(audit_wb) > 0

    # -------------------------------------------------------------
    # 11. CUSTOM WORKFLOW BUILDER PIPELINE (PHASE 7)
    # -------------------------------------------------------------
    pipeline = WorkflowDefinition(name="Sales Order Audit Recipe")
    pipeline.add_step(WorkflowStep(
        name="Clean Region Text",
        category="data_cleaning",
        operation="standardize_text",
        params={"columns": ["SalesRegion"], "operations": ["trim", "uppercase"]},
    ))
    pipeline.add_step(WorkflowStep(
        name="Deduplicate by OrderID",
        category="row_ops",
        operation="remove_duplicates",
        params={"subset_cols": ["OrderID"], "keep_mode": "first"},
    ))
    pipe_res = WorkflowEngine.execute_workflow(SessionManager.get_active_df(), pipeline)
    assert pipe_res.is_success is True
    assert pipe_res.successful_steps == 2
    SessionManager.update_working_df(pipe_res.final_df, "Workflow Pipeline", "Ran 2 steps")

    # -------------------------------------------------------------
    # 12. NATURAL LANGUAGE CUSTOMISATION (PHASE 8)
    # -------------------------------------------------------------
    nl_res = NaturalLanguageEngine.parse_instruction_offline(
        "Rename SalesRegion to FinalRegion",
        df=SessionManager.get_active_df(),
    )
    assert len(nl_res.parsed_operations) == 1
    assert nl_res.parsed_operations[0].operation == "rename_columns"
    assert nl_res.requires_clarification is False

    ai_transformed, ai_logs = NaturalLanguageEngine.execute_proposed_operations(
        SessionManager.get_active_df(), nl_res.parsed_operations
    )
    assert "FinalRegion" in ai_transformed.columns
    SessionManager.update_working_df(ai_transformed, "AI Transformation", ai_logs[0])

    # -------------------------------------------------------------
    # 13. VALIDATION CENTRE & DIAGNOSTIC EXPORT (PHASE 9)
    # -------------------------------------------------------------
    final_df = SessionManager.get_active_df()
    val_rep = ValidationEngine.audit_dataset(
        df=final_df,
        dataset_name="Final Staged Sales",
        required_columns=["OrderID", "FinalRegion"],
        unique_key_columns=["OrderID"],
    )
    assert val_rep.total_records > 0
    assert val_rep.status in ["PASSED", "WARNINGS"]

    st_history = SessionManager.get_change_history()
    audit_excel = ValidationEngine.generate_excel_audit_report(
        report=val_rep,
        df=final_df,
        transformation_history=st_history,
    )
    assert isinstance(audit_excel, bytes)
    assert len(audit_excel) > 0
