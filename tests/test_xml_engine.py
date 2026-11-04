"""
Unit Tests for Universal XML Customisation Engine & File Conversion (Phase 5)
"""
import pytest
import pandas as pd
import json

from core.xml_engine import UniversalXmlEditor, UniversalFormatConverter


SAMPLE_XML = """<?xml version="1.0" encoding="utf-8"?>
<TRANSACTIONS version="1.0">
  <RECORD id="REC-1">
    <PARTYNAME>Client A</PARTYNAME>
    <AMOUNT>1500.0</AMOUNT>
  </RECORD>
  <RECORD id="REC-2">
    <PARTYNAME>Client B</PARTYNAME>
    <AMOUNT>2500.0</AMOUNT>
  </RECORD>
</TRANSACTIONS>
"""


def test_validate_xml_syntax():
    assert UniversalXmlEditor.validate_xml_syntax(SAMPLE_XML)[0] is True
    assert UniversalXmlEditor.validate_xml_syntax("<BROKEN><UNCLOSED>")[0] is False


def test_search_nodes():
    nodes = UniversalXmlEditor.search_nodes(SAMPLE_XML, query="PARTYNAME", search_by="tag")
    assert len(nodes) == 2
    assert nodes[0]["tag"] == "PARTYNAME"

    # Search by text
    text_nodes = UniversalXmlEditor.search_nodes(SAMPLE_XML, query="Client A", search_by="text")
    assert len(text_nodes) == 1
    assert text_nodes[0]["text"] == "Client A"


def test_edit_node_text():
    updated_xml, msg = UniversalXmlEditor.edit_node_text(SAMPLE_XML, target_tag="PARTYNAME", new_text="Renamed Client", occurrence_idx=0)
    assert "Renamed Client" in updated_xml
    assert UniversalXmlEditor.validate_xml_syntax(updated_xml)[0] is True


def test_set_attribute():
    updated_xml, msg = UniversalXmlEditor.set_attribute(SAMPLE_XML, target_tag="RECORD", attr_name="status", attr_value="verified")
    assert 'status="verified"' in updated_xml
    assert UniversalXmlEditor.validate_xml_syntax(updated_xml)[0] is True


def test_add_child_element():
    updated_xml, msg = UniversalXmlEditor.add_child_element(
        SAMPLE_XML, parent_tag="RECORD", new_tag="CURRENCY", text="USD"
    )
    assert "<CURRENCY>USD</CURRENCY>" in updated_xml
    assert UniversalXmlEditor.validate_xml_syntax(updated_xml)[0] is True


def test_remove_element():
    updated_xml, msg = UniversalXmlEditor.remove_element(SAMPLE_XML, target_tag="AMOUNT")
    assert "<AMOUNT>" not in updated_xml
    assert UniversalXmlEditor.validate_xml_syntax(updated_xml)[0] is True


def test_rename_tag():
    updated_xml, msg = UniversalXmlEditor.rename_tag(SAMPLE_XML, old_tag="PARTYNAME", new_tag="CLIENT")
    assert "<CLIENT>Client A</CLIENT>" in updated_xml
    assert "<PARTYNAME>" not in updated_xml
    assert UniversalXmlEditor.validate_xml_syntax(updated_xml)[0] is True


def test_get_xml_structural_summary():
    summary = UniversalXmlEditor.get_xml_structural_summary(SAMPLE_XML)
    assert summary["root_tag"] == "TRANSACTIONS"
    assert summary["total_elements"] >= 7
    assert summary["unique_tags"] >= 4
    assert len(summary["tags_summary"]) >= 4


def test_map_tabular_to_xml():
    df = pd.DataFrame({
        "ID": [101, 102],
        "Customer": ["Acme", "Globex"],
        "City": ["New York", "London"],
        "Amount": [500.0, 750.0],
    })
    mapping = {
        "ID": "@id",
        "Customer": "CLIENT_NAME",
        "City": "LOCATION/CITY",
        "Amount": "TOTAL_AMT",
    }
    xml_str = UniversalXmlEditor.map_tabular_to_xml(df, root_tag="ERP", record_tag="ENTRY", mapping=mapping)

    assert '<ERP>' in xml_str
    assert '<ENTRY id="101">' in xml_str or '<ENTRY id="101.0">' in xml_str
    assert '<CLIENT_NAME>Acme</CLIENT_NAME>' in xml_str
    assert '<LOCATION>' in xml_str
    assert '<CITY>New York</CITY>' in xml_str
    assert '<TOTAL_AMT>500.0</TOTAL_AMT>' in xml_str
    assert UniversalXmlEditor.validate_xml_syntax(xml_str)[0] is True


def test_cross_format_conversions():
    # CSV to Excel and back
    csv_sample = "ID,Name,Value\n1,Alpha,100\n2,Beta,200\n"
    excel_bytes = UniversalFormatConverter.csv_to_excel(csv_sample)
    assert len(excel_bytes) > 0

    csv_roundtrip = UniversalFormatConverter.excel_to_csv(excel_bytes)
    assert "Alpha" in csv_roundtrip

    # XML to JSON and back
    json_from_xml = UniversalFormatConverter.xml_to_json(SAMPLE_XML)
    parsed_json = json.loads(json_from_xml)
    assert "TRANSACTIONS" in parsed_json

    xml_from_json = UniversalFormatConverter.json_to_xml(json_from_xml, root_tag="ROOT", item_tag="ITEM")
    assert UniversalXmlEditor.validate_xml_syntax(xml_from_json)[0] is True
