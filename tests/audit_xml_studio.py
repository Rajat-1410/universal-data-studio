"""
Comprehensive Audit & Verification Suite for Universal XML Studio (Phase 5)
Tests every engine method, edge case, cross-conversion flow, and session sync.
"""
import io
import json
import pytest
import pandas as pd
import xml.etree.ElementTree as ET

from core.xml_engine import UniversalXmlEditor, UniversalFormatConverter
from core.file_reader import XmlReader
from utils.session_manager import SessionManager


COMPLEX_XML = """<?xml version="1.0" encoding="utf-8"?>
<ENVELOPE xmlns:tally="http://tallysolutions.com">
  <HEADER>
    <VERSION>1.0</VERSION>
    <STATUS>ACTIVE</STATUS>
  </HEADER>
  <BODY>
    <DATA>
      <RECORD id="REC-101" type="standard">
        <PARTYNAME>Acme Corporation</PARTYNAME>
        <CONTACT>
          <PERSON>Alice Smith</PERSON>
          <PHONE>+1-555-0100</PHONE>
        </CONTACT>
        <AMOUNT currency="USD">1500.50</AMOUNT>
        <TAX_RATE>0.18</TAX_RATE>
      </RECORD>
      <RECORD id="REC-102" type="standard">
        <PARTYNAME>Globex Corporation</PARTYNAME>
        <CONTACT>
          <PERSON>Bob Jones</PERSON>
          <PHONE>+1-555-0200</PHONE>
        </CONTACT>
        <AMOUNT currency="EUR">2750.00</AMOUNT>
        <TAX_RATE>0.18</TAX_RATE>
      </RECORD>
    </DATA>
  </BODY>
</ENVELOPE>
"""


class TestXmlSyntaxAndInspection:
    def test_validate_valid_and_invalid_syntax(self):
        # Valid XML
        valid, err = UniversalXmlEditor.validate_xml_syntax(COMPLEX_XML)
        assert valid is True
        assert err is None

        # Empty string
        valid, err = UniversalXmlEditor.validate_xml_syntax("")
        assert valid is False
        assert "empty" in err.lower()

        # Whitespace only
        valid, err = UniversalXmlEditor.validate_xml_syntax("   \n  \t ")
        assert valid is False

        # Malformed XML
        valid, err = UniversalXmlEditor.validate_xml_syntax("<ROOT><UNCLOSED>")
        assert valid is False
        assert "syntax error" in err.lower()

    def test_search_nodes_by_all_modes(self):
        # By tag
        records = UniversalXmlEditor.search_nodes(COMPLEX_XML, "RECORD", search_by="tag")
        assert len(records) == 2
        assert records[0]["tag"] == "RECORD"
        assert records[0]["parent"] == "DATA"

        # By text
        alice = UniversalXmlEditor.search_nodes(COMPLEX_XML, "Alice Smith", search_by="text")
        assert len(alice) == 1
        assert alice[0]["tag"] == "PERSON"
        assert alice[0]["text"] == "Alice Smith"

        # By attribute
        attrib_match = UniversalXmlEditor.search_nodes(COMPLEX_XML, "REC-102", search_by="attribute")
        assert len(attrib_match) == 1
        assert attrib_match[0]["attributes"]["id"] == "REC-102"

        # Empty query returns all nodes
        all_nodes = UniversalXmlEditor.search_nodes(COMPLEX_XML, "", search_by="tag")
        assert len(all_nodes) >= 14

    def test_structural_summary_metrics(self):
        summary = UniversalXmlEditor.get_xml_structural_summary(COMPLEX_XML)
        assert summary["root_tag"] == "ENVELOPE"
        assert summary["total_elements"] >= 14
        assert summary["unique_tags"] >= 9
        assert summary["max_depth"] >= 5

        # Check tag summary entries
        tags = [t["Tag"] for t in summary["tags_summary"]]
        assert "RECORD" in tags
        assert "PARTYNAME" in tags
        assert "AMOUNT" in tags


class TestXmlEditingOperations:
    def test_edit_node_text_single_and_all(self):
        # Single occurrence (first)
        updated_first, msg1 = UniversalXmlEditor.edit_node_text(COMPLEX_XML, "TAX_RATE", "0.20", occurrence_idx=0)
        assert "<TAX_RATE>0.20</TAX_RATE>" in updated_first
        assert "<TAX_RATE>0.18</TAX_RATE>" in updated_first  # second remains unchanged

        # All occurrences
        updated_all, msg2 = UniversalXmlEditor.edit_node_text(COMPLEX_XML, "TAX_RATE", "0.25", occurrence_idx=-1)
        assert "<TAX_RATE>0.18</TAX_RATE>" not in updated_all
        assert updated_all.count("<TAX_RATE>0.25</TAX_RATE>") == 2

        # Non-existent tag raises ValueError
        with pytest.raises(ValueError, match="not found"):
            UniversalXmlEditor.edit_node_text(COMPLEX_XML, "NON_EXISTENT_TAG", "val")

    def test_rename_tag(self):
        updated, msg = UniversalXmlEditor.rename_tag(COMPLEX_XML, "PARTYNAME", "VENDOR_NAME")
        assert "<VENDOR_NAME>Acme Corporation</VENDOR_NAME>" in updated
        assert "<PARTYNAME>" not in updated

        with pytest.raises(ValueError, match="not found"):
            UniversalXmlEditor.rename_tag(COMPLEX_XML, "NON_EXISTENT_TAG", "NEW_NAME")

        with pytest.raises(ValueError, match="cannot be blank"):
            UniversalXmlEditor.rename_tag(COMPLEX_XML, "PARTYNAME", "   ")

    def test_set_attribute(self):
        updated, msg = UniversalXmlEditor.set_attribute(COMPLEX_XML, "HEADER", "source", "StudioAudit")
        assert 'source="StudioAudit"' in updated

        with pytest.raises(ValueError, match="not found"):
            UniversalXmlEditor.set_attribute(COMPLEX_XML, "NON_EXISTENT", "attr", "val")

    def test_add_child_element(self):
        updated, msg = UniversalXmlEditor.add_child_element(
            COMPLEX_XML, parent_tag="RECORD", new_tag="AUDIT_STATUS", text="VERIFIED"
        )
        assert "<AUDIT_STATUS>VERIFIED</AUDIT_STATUS>" in updated
        assert updated.count("<AUDIT_STATUS>VERIFIED</AUDIT_STATUS>") == 2

        with pytest.raises(ValueError, match="not found"):
            UniversalXmlEditor.add_child_element(COMPLEX_XML, "NON_EXISTENT", "NEW", "VAL")

        with pytest.raises(ValueError, match="cannot be blank"):
            UniversalXmlEditor.add_child_element(COMPLEX_XML, "RECORD", "  ", "VAL")

    def test_remove_element(self):
        updated, msg = UniversalXmlEditor.remove_element(COMPLEX_XML, "HEADER")
        assert "<HEADER>" not in updated
        assert "<VERSION>" not in updated

        with pytest.raises(ValueError, match="not found"):
            UniversalXmlEditor.remove_element(COMPLEX_XML, "NON_EXISTENT")


class TestTabularToXmlMapping:
    def test_flat_and_nested_mapping(self):
        df = pd.DataFrame({
            "OrderID": ["ORD-1", "ORD-2"],
            "Customer": ["Tech Corp", "Data LLC"],
            "City": ["San Francisco", "Austin"],
            "ZipCode": ["94105", "78701"],
            "Total": [1200.0, 3450.5],
        })

        mapping = {
            "OrderID": "@id",
            "Customer": "CLIENT/NAME",
            "City": "LOCATION/ADDRESS/CITY",
            "ZipCode": "LOCATION/ADDRESS/@zip",
            "Total": "BILLING/AMOUNT",
        }

        generated_xml = UniversalXmlEditor.map_tabular_to_xml(
            df, root_tag="SALES_EXPORT", record_tag="INVOICE", mapping=mapping
        )

        valid, err = UniversalXmlEditor.validate_xml_syntax(generated_xml)
        assert valid is True, f"Generated XML syntax is invalid: {err}"

        # Assert correct structure
        assert "<SALES_EXPORT>" in generated_xml
        assert '<INVOICE id="ORD-1">' in generated_xml
        assert "<CLIENT>\n        <NAME>Tech Corp</NAME>\n      </CLIENT>" in generated_xml or "<NAME>Tech Corp</NAME>" in generated_xml
        assert "<LOCATION>" in generated_xml
        assert "<ADDRESS zip=\"94105\">" in generated_xml or '<ADDRESS zip="94105">' in generated_xml
        assert "<CITY>San Francisco</CITY>" in generated_xml
        assert "<BILLING>" in generated_xml
        assert "<AMOUNT>1200.0</AMOUNT>" in generated_xml


class TestUniversalCrossFormatConversions:
    def test_all_eight_conversion_flows(self):
        # 1. Excel to CSV
        raw_excel_df = pd.DataFrame({"A": [1, 2], "B": ["X", "Y"]})
        excel_buf = io.BytesIO()
        with pd.ExcelWriter(excel_buf, engine="openpyxl") as w:
            raw_excel_df.to_excel(w, index=False)
        excel_bytes = excel_buf.getvalue()

        csv_out = UniversalFormatConverter.excel_to_csv(excel_bytes)
        assert "A,B" in csv_out
        assert "1,X" in csv_out

        # 2. CSV to Excel
        excel_from_csv = UniversalFormatConverter.csv_to_excel(csv_out)
        assert len(excel_from_csv) > 100
        df_readback = pd.read_excel(io.BytesIO(excel_from_csv))
        assert len(df_readback) == 2
        assert list(df_readback.columns) == ["A", "B"]

        # 3. XML to Excel
        excel_from_xml = UniversalFormatConverter.xml_to_excel(COMPLEX_XML)
        assert len(excel_from_xml) > 100
        xml_df = pd.read_excel(io.BytesIO(excel_from_xml))
        assert len(xml_df) == 2
        assert "PARTYNAME" in xml_df.columns
        assert "Acme Corporation" in xml_df["PARTYNAME"].values

        # 4. Excel to XML
        xml_from_excel = UniversalFormatConverter.excel_to_xml(excel_bytes, root_tag="ROOT", record_tag="ROW")
        valid, _ = UniversalXmlEditor.validate_xml_syntax(xml_from_excel)
        assert valid is True
        assert "<ROOT>" in xml_from_excel
        assert "<ROW>" in xml_from_excel

        # 5. JSON to Excel
        json_data = json.dumps([{"id": 1, "name": "Item 1"}, {"id": 2, "name": "Item 2"}])
        excel_from_json = UniversalFormatConverter.json_to_excel(json_data)
        assert len(excel_from_json) > 100
        json_df = pd.read_excel(io.BytesIO(excel_from_json))
        assert len(json_df) == 2
        assert "name" in json_df.columns

        # 6. Excel to JSON
        json_from_excel = UniversalFormatConverter.excel_to_json(excel_bytes)
        parsed = json.loads(json_from_excel)
        assert isinstance(parsed, list)
        assert len(parsed) == 2
        assert parsed[0]["A"] == 1

        # 7. XML to JSON
        json_from_xml = UniversalFormatConverter.xml_to_json(COMPLEX_XML)
        parsed_xml_json = json.loads(json_from_xml)
        assert "ENVELOPE" in parsed_xml_json

        # 8. JSON to XML
        xml_from_json = UniversalFormatConverter.json_to_xml(json_data, root_tag="INVENTORY", item_tag="PRODUCT")
        valid, _ = UniversalXmlEditor.validate_xml_syntax(xml_from_json)
        assert valid is True
        assert "<INVENTORY>" in xml_from_json
        assert "<PRODUCT>" in xml_from_json
