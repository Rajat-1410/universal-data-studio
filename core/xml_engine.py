"""
Universal XML Customisation Engine & Multi-Format Cross-Converter
Provides hierarchical XML node editing, attribute manipulation, tag search,
syntax validation, Excel-to-XML mapping, and cross-format file conversions.
"""
import io
import json
import re
from typing import Dict, Any, List, Optional, Tuple, Union
import xml.etree.ElementTree as ET
from xml.dom import minidom
import pandas as pd
import numpy as np


class UniversalXmlEditor:
    """Universal XML manipulation engine preserving hierarchy and namespaces."""

    @classmethod
    def validate_xml_syntax(cls, xml_str: str) -> Tuple[bool, Optional[str]]:
        """Validates XML syntax and returns error details if invalid."""
        if not xml_str or not xml_str.strip():
            return False, "XML content is empty."
        try:
            ET.fromstring(xml_str)
            return True, None
        except ET.ParseError as pe:
            return False, f"Syntax Error (Line {pe.code}): {str(pe)}"
        except Exception as e:
            return False, str(e)

    @classmethod
    def clean_tag(cls, tag: str) -> str:
        """Removes XML namespace brackets for display."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    @classmethod
    def search_nodes(
        cls,
        xml_str: str,
        query: str,
        search_by: str = "tag",
    ) -> List[Dict[str, Any]]:
        """
        Searches XML elements by:
        - tag: tag name contains query
        - attribute: element has attribute name or attribute value matching query
        - text: element text contains query
        """
        if not xml_str:
            return []

        try:
            root = ET.fromstring(xml_str)
        except Exception:
            return []

        results = []
        q_clean = query.strip().lower()

        def recurse(element: ET.Element, path: str, parent_tag: Optional[str] = None):
            tag_name = cls.clean_tag(element.tag)
            current_path = f"{path}/{tag_name}"

            text_val = (element.text or "").strip()
            attribs = dict(element.attrib)

            match = False
            if not q_clean:
                match = True
            elif search_by == "tag" and q_clean in tag_name.lower():
                match = True
            elif search_by == "text" and q_clean in text_val.lower():
                match = True
            elif search_by == "attribute":
                attr_str = " ".join([f"{k}={v}" for k, v in attribs.items()]).lower()
                if q_clean in attr_str:
                    match = True

            if match:
                results.append({
                    "path": current_path,
                    "tag": tag_name,
                    "raw_tag": element.tag,
                    "text": text_val,
                    "attributes": attribs,
                    "parent": parent_tag,
                    "children_count": len(list(element)),
                })

            for child in element:
                recurse(child, current_path, tag_name)

        recurse(root, "", None)
        return results

    @classmethod
    def edit_node_text(cls, xml_str: str, target_tag: str, new_text: str, occurrence_idx: int = 0) -> Tuple[str, str]:
        """Edits text content of a specific tag occurrence."""
        root = ET.fromstring(xml_str)
        matched = 0
        updated = False

        for elem in root.iter():
            if cls.clean_tag(elem.tag) == target_tag:
                if matched == occurrence_idx or occurrence_idx == -1:
                    elem.text = new_text
                    updated = True
                matched += 1

        if not updated:
            raise ValueError(f"Tag '<{target_tag}>' not found.")

        result_str = ET.tostring(root, encoding="utf-8").decode("utf-8")
        return result_str, f"Updated text of <{target_tag}> to '{new_text}'"

    @classmethod
    def set_attribute(cls, xml_str: str, target_tag: str, attr_name: str, attr_value: str) -> Tuple[str, str]:
        """Adds or updates an attribute on target elements."""
        root = ET.fromstring(xml_str)
        clean_attr = attr_name.strip()
        if not clean_attr:
            raise ValueError("Attribute name cannot be blank.")
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_\-\.]*$", clean_attr):
            raise ValueError(
                f"Invalid attribute name '{clean_attr}'. Attribute names must start with a letter or underscore and contain only alphanumeric characters, underscores, hyphens, or periods."
            )

        updated_count = 0
        for elem in root.iter():
            if cls.clean_tag(elem.tag) == target_tag:
                elem.set(clean_attr, attr_value)
                updated_count += 1

        if updated_count == 0:
            raise ValueError(f"Tag '<{target_tag}>' not found.")

        result_str = ET.tostring(root, encoding="utf-8").decode("utf-8")
        return result_str, f"Set attribute '{clean_attr}'='{attr_value}' on {updated_count} <{target_tag}> elements"

    @classmethod
    def add_child_element(
        cls,
        xml_str: str,
        parent_tag: str,
        new_tag: str,
        text: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None,
    ) -> Tuple[str, str]:
        """Adds a new child element under specified parent element(s)."""
        root = ET.fromstring(xml_str)
        added_count = 0

        clean_new = new_tag.strip()
        if not clean_new:
            raise ValueError("New tag name cannot be blank.")
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_\-\.]*$", clean_new):
            raise ValueError(
                f"Invalid XML tag name '{clean_new}'. XML tags must start with a letter or underscore and contain only alphanumeric characters, underscores, hyphens, or periods."
            )

        for elem in root.iter():
            if cls.clean_tag(elem.tag) == parent_tag:
                child = ET.SubElement(elem, clean_new, attributes or {})
                if text is not None:
                    child.text = str(text)
                added_count += 1

        if added_count == 0:
            raise ValueError(f"Parent tag '<{parent_tag}>' not found.")

        result_str = ET.tostring(root, encoding="utf-8").decode("utf-8")
        return result_str, f"Added <{clean_new}> under {added_count} <{parent_tag}> elements"

    @classmethod
    def remove_element(cls, xml_str: str, target_tag: str) -> Tuple[str, str]:
        """Removes element(s) matching target_tag from XML document."""
        root = ET.fromstring(xml_str)
        if cls.clean_tag(root.tag) == target_tag:
            raise ValueError(f"Cannot delete the root element <{target_tag}>.")

        removed_count = 0

        def remove_matching(parent: ET.Element):
            nonlocal removed_count
            for child in list(parent):
                if cls.clean_tag(child.tag) == target_tag:
                    parent.remove(child)
                    removed_count += 1
                else:
                    remove_matching(child)

        remove_matching(root)
        if removed_count == 0:
            raise ValueError(f"Tag '<{target_tag}>' not found to delete.")

        result_str = ET.tostring(root, encoding="utf-8").decode("utf-8")
        return result_str, f"Removed {removed_count} <{target_tag}> elements"

    @classmethod
    def rename_tag(cls, xml_str: str, old_tag: str, new_tag: str) -> Tuple[str, str]:
        """Renames all occurrences of an XML tag while preserving attributes and children."""
        root = ET.fromstring(xml_str)
        clean_new = new_tag.strip()
        if not clean_new:
            raise ValueError("New tag name cannot be blank.")
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_\-\.]*$", clean_new):
            raise ValueError(
                f"Invalid XML tag name '{clean_new}'. XML tags must start with a letter or underscore and contain only alphanumeric characters, underscores, hyphens, or periods."
            )

        renamed_count = 0
        for elem in root.iter():
            if cls.clean_tag(elem.tag) == old_tag:
                if "}" in elem.tag:
                    ns = elem.tag.split("}", 1)[0] + "}"
                    elem.tag = f"{ns}{clean_new}"
                else:
                    elem.tag = clean_new
                renamed_count += 1

        if renamed_count == 0:
            raise ValueError(f"Tag '<{old_tag}>' not found to rename.")

        result_str = ET.tostring(root, encoding="utf-8").decode("utf-8")
        return result_str, f"Renamed {renamed_count} occurrences of <{old_tag}> to <{clean_new}>"

    @classmethod
    def get_xml_structural_summary(cls, xml_str: str) -> Dict[str, Any]:
        """Returns deep structural metrics: root, total elements, max depth, repeated tags, attributes."""
        root = ET.fromstring(xml_str)
        total_elements = 0
        tag_counts = {}
        tag_attributes = {}
        tag_children = {}
        max_depth = 1

        def traverse(elem: ET.Element, depth: int):
            nonlocal total_elements, max_depth
            total_elements += 1
            if depth > max_depth:
                max_depth = depth

            clean_t = cls.clean_tag(elem.tag)
            tag_counts[clean_t] = tag_counts.get(clean_t, 0) + 1

            if elem.attrib:
                if clean_t not in tag_attributes:
                    tag_attributes[clean_t] = set()
                tag_attributes[clean_t].update(elem.attrib.keys())

            child_tags = [cls.clean_tag(c.tag) for c in elem]
            if child_tags:
                if clean_t not in tag_children:
                    tag_children[clean_t] = set()
                tag_children[clean_t].update(child_tags)

            for child in elem:
                traverse(child, depth + 1)

        traverse(root, 1)

        tags_summary = []
        for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1]):
            tags_summary.append({
                "Tag": tag,
                "Occurrences": count,
                "Attributes": ", ".join(sorted(tag_attributes.get(tag, []))) or "None",
                "Child Tags": ", ".join(sorted(tag_children.get(tag, []))) or "Leaf",
            })

        return {
            "root_tag": cls.clean_tag(root.tag),
            "total_elements": total_elements,
            "unique_tags": len(tag_counts),
            "max_depth": max_depth,
            "tags_summary": tags_summary,
        }

    @classmethod
    def map_tabular_to_xml(
        cls,
        df: pd.DataFrame,
        root_tag: str = "DATASET",
        record_tag: str = "RECORD",
        mapping: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Maps tabular columns to an XML schema.
        Supports:
        - Flat child tag: 'Col' -> 'CHILD_TAG'
        - Attribute on record: 'Col' -> '@attr_name'
        - Nested paths: 'Col' -> 'PARENT/CHILD' or 'PARENT/@attr'
        """
        clean_root = root_tag.strip() or "DATASET"
        clean_rec = record_tag.strip() or "RECORD"

        root_elem = ET.Element(clean_root)
        col_map = mapping or {c: c for c in df.columns}

        for _, row in df.iterrows():
            rec_elem = ET.SubElement(root_elem, clean_rec)
            for col, target in col_map.items():
                if col not in df.columns:
                    continue
                val = row[col]
                val_str = "" if pd.isna(val) else str(val)
                target_str = target.strip()

                if not target_str:
                    continue

                if target_str.startswith("@"):
                    # Attribute directly on record element
                    attr_name = target_str[1:].strip()
                    rec_elem.set(attr_name, val_str)
                elif "/" in target_str:
                    # Nested path, e.g. "CUSTOMER/NAME" or "ITEM/@id"
                    parts = target_str.split("/")
                    curr_elem = rec_elem
                    for p in parts[:-1]:
                        existing = curr_elem.find(p)
                        if existing is not None:
                            curr_elem = existing
                        else:
                            curr_elem = ET.SubElement(curr_elem, p)
                    leaf = parts[-1]
                    if leaf.startswith("@"):
                        curr_elem.set(leaf[1:].strip(), val_str)
                    else:
                        child_elem = ET.SubElement(curr_elem, leaf)
                        child_elem.text = val_str
                else:
                    child_elem = ET.SubElement(rec_elem, target_str)
                    child_elem.text = val_str

        # Pretty print
        rough_string = ET.tostring(root_elem, "utf-8")
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")


class UniversalFormatConverter:
    """Universal cross-format converter between Excel, CSV, XML, and JSON."""

    @classmethod
    def excel_to_csv(cls, excel_bytes: bytes, sheet_name: Optional[str] = None) -> str:
        f = io.BytesIO(excel_bytes)
        ef = pd.ExcelFile(f)
        sname = sheet_name or ef.sheet_names[0]
        df = pd.read_excel(f, sheet_name=sname)
        return df.to_csv(index=False)

    @classmethod
    def csv_to_excel(cls, csv_str: str, delimiter: str = ",") -> bytes:
        df = pd.read_csv(io.StringIO(csv_str), sep=delimiter)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Data")
        return buf.getvalue()

    @classmethod
    def xml_to_excel(cls, xml_str: str, record_tag: Optional[str] = None) -> bytes:
        root = ET.fromstring(xml_str)
        clean_root_tag = UniversalXmlEditor.clean_tag(root.tag)

        # Candidate tags: count occurrences and child elements
        tag_counts = {}
        tag_child_counts = {}
        for elem in root.iter():
            t = UniversalXmlEditor.clean_tag(elem.tag)
            tag_counts[t] = tag_counts.get(t, 0) + 1
            num_children = len(list(elem))
            if num_children > 0:
                tag_child_counts[t] = tag_child_counts.get(t, 0) + num_children

        target = record_tag.strip() if record_tag and record_tag.strip() else None
        if not target:
            # 1. Prefer repeated tags that HAVE children
            candidates_with_children = [
                t for t, count in tag_counts.items()
                if t != clean_root_tag and count > 1 and t in tag_child_counts
            ]
            if candidates_with_children:
                # Pick candidate with highest total child elements
                candidates_with_children.sort(key=lambda t: tag_child_counts.get(t, 0), reverse=True)
                target = candidates_with_children[0]
            else:
                # 2. Repeated tags != root
                candidates = [t for t, count in tag_counts.items() if t != clean_root_tag and count > 1]
                if candidates:
                    candidates.sort(key=lambda t: tag_counts[t], reverse=True)
                    target = candidates[0]
                else:
                    target = clean_root_tag

        # Helper to recursively flatten an element into a dict
        def flatten_element(elem: ET.Element, prefix: str = "") -> Dict[str, Any]:
            flat = {}
            for k, v in elem.attrib.items():
                flat[f"{prefix}@{k}" if prefix else f"@{k}"] = v

            children = list(elem)
            if not children:
                val = elem.text.strip() if elem.text else ""
                key_name = prefix if prefix else UniversalXmlEditor.clean_tag(elem.tag)
                flat[key_name] = val
            else:
                if elem.text and elem.text.strip():
                    flat[f"{prefix}#text" if prefix else "#text"] = elem.text.strip()
                for child in children:
                    c_tag = UniversalXmlEditor.clean_tag(child.tag)
                    child_prefix = f"{prefix}_{c_tag}" if prefix else c_tag
                    flat.update(flatten_element(child, prefix=child_prefix))
            return flat

        records = []
        for elem in root.iter():
            if UniversalXmlEditor.clean_tag(elem.tag) == target:
                records.append(flatten_element(elem))

        df = pd.DataFrame(records) if records else pd.DataFrame({"XML_Content": [xml_str[:1000]]})
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="XML_Records")
        return buf.getvalue()

    @classmethod
    def excel_to_xml(cls, excel_bytes: bytes, root_tag: str = "DATASET", record_tag: str = "RECORD") -> str:
        df = pd.read_excel(io.BytesIO(excel_bytes))
        return UniversalXmlEditor.map_tabular_to_xml(df, root_tag, record_tag)

    @classmethod
    def json_to_excel(cls, json_str: str) -> bytes:
        data = json.loads(json_str)
        if isinstance(data, list):
            df = pd.json_normalize(data)
        elif isinstance(data, dict):
            # check if dict contains an array
            arr_key = next((k for k, v in data.items() if isinstance(v, list) and v and isinstance(v[0], dict)), None)
            if arr_key:
                df = pd.json_normalize(data[arr_key])
            else:
                df = pd.json_normalize([data])
        else:
            df = pd.DataFrame({"value": [data]})

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="JSON_Data")
        return buf.getvalue()

    @classmethod
    def excel_to_json(cls, excel_bytes: bytes) -> str:
        df = pd.read_excel(io.BytesIO(excel_bytes))
        return df.to_json(orient="records", indent=2)

    @classmethod
    def xml_to_json(cls, xml_str: str) -> str:
        root = ET.fromstring(xml_str)

        def elem_to_dict(elem: ET.Element):
            d = {}
            for k, v in elem.attrib.items():
                d[f"@{k}"] = v
            children = list(elem)
            if not children:
                if elem.text and elem.text.strip():
                    if d:
                        d["#text"] = elem.text.strip()
                    else:
                        return elem.text.strip()
            else:
                for child in children:
                    c_tag = UniversalXmlEditor.clean_tag(child.tag)
                    c_data = elem_to_dict(child)
                    if c_tag in d:
                        if isinstance(d[c_tag], list):
                            d[c_tag].append(c_data)
                        else:
                            d[c_tag] = [d[c_tag], c_data]
                    else:
                        d[c_tag] = c_data
            return d

        clean_root = UniversalXmlEditor.clean_tag(root.tag)
        result_dict = {clean_root: elem_to_dict(root)}
        return json.dumps(result_dict, indent=2)

    @classmethod
    def json_to_xml(cls, json_str: str, root_tag: str = "DATASET", item_tag: str = "RECORD") -> str:
        data = json.loads(json_str)
        root = ET.Element(root_tag)

        def dict_to_elem(d: Dict[str, Any], parent: ET.Element):
            for k, v in d.items():
                safe_tag = re.sub(r"[^\w]", "_", str(k))
                if isinstance(v, dict):
                    child = ET.SubElement(parent, safe_tag)
                    dict_to_elem(v, child)
                elif isinstance(v, list):
                    for item in v:
                        child = ET.SubElement(parent, safe_tag)
                        if isinstance(item, dict):
                            dict_to_elem(item, child)
                        else:
                            child.text = str(item)
                else:
                    child = ET.SubElement(parent, safe_tag)
                    child.text = str(v) if v is not None else ""

        if isinstance(data, list):
            for item in data:
                rec = ET.SubElement(root, item_tag)
                if isinstance(item, dict):
                    dict_to_elem(item, rec)
                else:
                    rec.text = str(item)
        elif isinstance(data, dict):
            dict_to_elem(data, root)

        rough_string = ET.tostring(root, "utf-8")
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
