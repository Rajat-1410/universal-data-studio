"""
Universal File Reader Engine
Modular, extensible architecture supporting Excel (.xlsx, .xls), CSV/TSV, XML, JSON, TXT, and ZIP.
Generates comprehensive inspection reports for tabular and hierarchical structures.
"""
import io
import os
import json
import uuid
import zipfile
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple, Union
import xml.etree.ElementTree as ET

import pandas as pd
import numpy as np

from utils.format_detector import FormatDetector
from utils.helpers import (
    format_bytes,
    detect_date_inconsistencies,
    compute_column_outliers,
    calculate_dataset_health,
)


class BaseReader(ABC):
    """Abstract base class for all file readers."""

    @abstractmethod
    def read(self, filename: str, raw_bytes: bytes, **kwargs) -> Dict[str, Any]:
        """Parses raw bytes into structured data and inspection reports."""
        pass


class ExcelReader(BaseReader):
    """Universal reader for Excel workbooks (.xlsx, .xls)."""

    def read(self, filename: str, raw_bytes: bytes, sheet_name: Optional[str] = None, header_row: int = 0, **kwargs) -> Dict[str, Any]:
        file_io = io.BytesIO(raw_bytes)
        excel_file = pd.ExcelFile(file_io)
        sheet_names = excel_file.sheet_names

        selected_sheet = sheet_name if sheet_name in sheet_names else sheet_names[0]

        # Read the selected sheet
        df = pd.read_excel(file_io, sheet_name=selected_sheet, header=header_row)

        # Clean column names (strip whitespace, ensure string representation for unnamed)
        df.columns = [str(c).strip() if not str(c).startswith("Unnamed:") else f"Col_{i+1}" for i, c in enumerate(df.columns)]

        # Read summary of all sheets
        sheets_summary = {}
        for s in sheet_names:
            try:
                sheet_df = pd.read_excel(io.BytesIO(raw_bytes), sheet_name=s, nrows=5)
                sheets_summary[s] = {
                    "preview_cols": list(sheet_df.columns),
                    "col_count": len(sheet_df.columns),
                }
            except Exception:
                sheets_summary[s] = {"col_count": 0, "preview_cols": []}

        return {
            "format": "excel",
            "sheets": sheet_names,
            "active_sheet": selected_sheet,
            "data_frames": {selected_sheet: df},
            "active_df": df,
            "sheets_summary": sheets_summary,
            "header_row_used": header_row,
        }


class CsvReader(BaseReader):
    """Universal reader for CSV, TSV, and delimited text files."""

    def read(self, filename: str, raw_bytes: bytes, delimiter: Optional[str] = None, encoding: Optional[str] = None, header_row: int = 0, **kwargs) -> Dict[str, Any]:
        enc = encoding or FormatDetector.detect_encoding(raw_bytes)
        text = raw_bytes.decode(enc, errors="replace")

        delim = delimiter or FormatDetector.sniff_delimiter(text[:4096])

        df = pd.read_csv(io.StringIO(text), sep=delim, header=header_row, on_bad_lines="skip")
        df.columns = [str(c).strip() if not str(c).startswith("Unnamed:") else f"Col_{i+1}" for i, c in enumerate(df.columns)]

        return {
            "format": "csv",
            "active_df": df,
            "data_frames": {"default": df},
            "delimiter_used": delim,
            "encoding_used": enc,
            "raw_text_preview": "\n".join(text.splitlines()[:50]),
        }


class JsonReader(BaseReader):
    """Universal reader for JSON documents (nested, lists, dictionaries)."""

    def read(self, filename: str, raw_bytes: bytes, **kwargs) -> Dict[str, Any]:
        enc = FormatDetector.detect_encoding(raw_bytes)
        text = raw_bytes.decode(enc, errors="replace")
        parsed_json = json.loads(text)

        df = None
        structure_type = "unknown"
        keys_at_root = []

        if isinstance(parsed_json, list):
            structure_type = "list_of_records"
            if len(parsed_json) > 0 and isinstance(parsed_json[0], dict):
                df = pd.json_normalize(parsed_json)
            else:
                df = pd.DataFrame({"value": parsed_json})
        elif isinstance(parsed_json, dict):
            structure_type = "object_dictionary"
            keys_at_root = list(parsed_json.keys())

            # Find candidate array inside dict
            candidate_list_key = None
            max_list_len = 0
            for k, v in parsed_json.items():
                if isinstance(v, list) and len(v) > max_list_len and len(v) > 0:
                    max_list_len = len(v)
                    candidate_list_key = k

            if candidate_list_key and isinstance(parsed_json[candidate_list_key][0], dict):
                df = pd.json_normalize(parsed_json[candidate_list_key])
                structure_type = f"nested_array_in_key: {candidate_list_key}"
            else:
                # Key-value dictionary
                df = pd.json_normalize([parsed_json])

        if df is not None:
            df.columns = [str(c).strip() for c in df.columns]

        return {
            "format": "json",
            "active_df": df if df is not None else pd.DataFrame(),
            "data_frames": {"default": df} if df is not None else {},
            "raw_json": parsed_json,
            "structure_type": structure_type,
            "keys_at_root": keys_at_root,
            "raw_text_preview": json.dumps(parsed_json, indent=2)[:3000],
        }


class XmlReader(BaseReader):
    """Universal hierarchical XML reader and inspector."""

    def read(self, filename: str, raw_bytes: bytes, record_tag: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        try:
            from modules.tally.tally_reader import TallyReader
            root, text = TallyReader.decode_and_sanitize_xml(raw_bytes)
            enc = FormatDetector.detect_encoding(raw_bytes)
        except Exception:
            enc = FormatDetector.detect_encoding(raw_bytes)
            text = raw_bytes.decode(enc, errors="replace")
            # Parse XML tree
            root = ET.fromstring(text)

        # Inspect hierarchical structure
        structure_info = self._analyze_xml_tree(root)

        # If user did not supply record tag, use candidate repeated element
        target_tag = record_tag or structure_info.get("primary_repeated_tag")

        # Attempt tabular extraction of repeated elements
        df = self._extract_tabular_data(root, target_tag)

        return {
            "format": "xml",
            "root_tag": self._clean_tag(root.tag),
            "xml_root": root,
            "xml_structure": structure_info,
            "target_record_tag": target_tag,
            "active_df": df,
            "data_frames": {target_tag or "records": df} if df is not None else {},
            "raw_text_preview": text[:4000],
            "encoding_used": enc,
        }

    def _clean_tag(self, tag: str) -> str:
        """Strips XML namespaces from tag name for readability."""
        if "}" in tag:
            return tag.split("}", 1)[1]
        return tag

    def _analyze_xml_tree(self, root: ET.Element) -> Dict[str, Any]:
        """Performs deep structural scan of XML tree."""
        tag_counts = {}
        tag_parents = {}
        tag_depths = {}
        tag_attributes = {}
        tag_has_children = {}

        max_depth = 0

        def traverse(element: ET.Element, depth: int, parent_tag: Optional[str] = None):
            nonlocal max_depth
            if depth > max_depth:
                max_depth = depth

            clean = self._clean_tag(element.tag)
            tag_counts[clean] = tag_counts.get(clean, 0) + 1

            if parent_tag and clean not in tag_parents:
                tag_parents[clean] = parent_tag

            if clean not in tag_depths:
                tag_depths[clean] = depth

            if element.attrib:
                if clean not in tag_attributes:
                    tag_attributes[clean] = set()
                tag_attributes[clean].update(element.attrib.keys())

            children = list(element)
            tag_has_children[clean] = len(children) > 0

            for child in children:
                traverse(child, depth + 1, clean)

        traverse(root, 1, None)

        # Convert attributes set to list
        attributes_serializable = {k: list(v) for k, v in tag_attributes.items()}

        # Identify candidate repeated elements (frequency > 1 and has children or fields)
        repeated_tags = [
            {"tag": tag, "count": count, "parent": tag_parents.get(tag, "ROOT"), "depth": tag_depths.get(tag, 1), "attributes": attributes_serializable.get(tag, [])}
            for tag, count in tag_counts.items()
            if count > 1
        ]
        repeated_tags.sort(key=lambda x: x["count"], reverse=True)

        primary_repeated_tag = repeated_tags[0]["tag"] if repeated_tags else None

        return {
            "root_tag": self._clean_tag(root.tag),
            "total_elements": sum(tag_counts.values()),
            "unique_tags_count": len(tag_counts),
            "max_tree_depth": max_depth,
            "tag_counts": tag_counts,
            "tag_parents": tag_parents,
            "tag_attributes": attributes_serializable,
            "repeated_elements": repeated_tags,
            "primary_repeated_tag": primary_repeated_tag,
        }

    def _extract_tabular_data(self, root: ET.Element, target_tag: Optional[str]) -> Optional[pd.DataFrame]:
        """Flattens elements with target_tag into a DataFrame while preserving child attributes."""
        if not target_tag:
            return None

        records = []

        def find_elements(elem: ET.Element):
            if self._clean_tag(elem.tag) == target_tag:
                record = {}
                # Add attributes
                for k, v in elem.attrib.items():
                    record[f"@{k}"] = v
                # Add child text
                for child in elem:
                    child_tag = self._clean_tag(child.tag)
                    if len(list(child)) == 0:
                        record[child_tag] = child.text.strip() if child.text else ""
                    else:
                        # Nested child: summarize or keep json-like dict
                        record[child_tag] = ET.tostring(child, encoding="unicode", method="text").strip()
                # If element has text itself and no children
                if elem.text and elem.text.strip() and not record:
                    record["value"] = elem.text.strip()
                records.append(record)
            for child in elem:
                find_elements(child)

        find_elements(root)

        if records:
            return pd.DataFrame(records)
        return None


class TxtReader(BaseReader):
    """Universal reader for plain text and raw logs."""

    def read(self, filename: str, raw_bytes: bytes, **kwargs) -> Dict[str, Any]:
        enc = FormatDetector.detect_encoding(raw_bytes)
        text = raw_bytes.decode(enc, errors="replace")
        lines = text.splitlines()

        # Check if text is delimited
        delim = FormatDetector.sniff_delimiter("\n".join(lines[:30]))
        df = None
        try:
            df = pd.read_csv(io.StringIO(text), sep=delim, on_bad_lines="skip")
            df.columns = [str(c).strip() for c in df.columns]
        except Exception:
            df = pd.DataFrame({"Line": lines})

        return {
            "format": "txt",
            "active_df": df,
            "data_frames": {"default": df},
            "line_count": len(lines),
            "encoding_used": enc,
            "detected_delimiter": delim,
            "raw_text_preview": "\n".join(lines[:100]),
        }


class ZipReader(BaseReader):
    """Universal reader for ZIP archives containing supported data files."""

    def read(self, filename: str, raw_bytes: bytes, selected_file: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            infolist = zf.infolist()
            archive_files = []
            supported_files = []

            for info in infolist:
                if info.is_dir():
                    continue
                ext = os.path.splitext(info.filename)[1].lower()
                is_supported = ext in [".xlsx", ".xls", ".csv", ".tsv", ".xml", ".json", ".txt"]
                entry = {
                    "filename": info.filename,
                    "size_bytes": info.file_size,
                    "compressed_size": info.compress_size,
                    "extension": ext,
                    "is_supported": is_supported,
                }
                archive_files.append(entry)
                if is_supported:
                    supported_files.append(info.filename)

            # If user selected a file or default to first supported file
            inner_result = None
            target_file = selected_file if selected_file in supported_files else (supported_files[0] if supported_files else None)

            if target_file:
                inner_bytes = zf.read(target_file)
                inner_reader = FileReaderRegistry.get_reader(target_file, inner_bytes)
                inner_result = inner_reader.read(target_file, inner_bytes)

        return {
            "format": "zip",
            "archive_files": archive_files,
            "supported_files": supported_files,
            "selected_file": target_file,
            "inner_result": inner_result,
            "active_df": inner_result.get("active_df") if inner_result else pd.DataFrame(),
            "data_frames": inner_result.get("data_frames") if inner_result else {},
        }


class FileReaderRegistry:
    """Registry coordinating format detection and reader delegation."""

    _readers = {
        "excel": ExcelReader,
        "csv": CsvReader,
        "json": JsonReader,
        "xml": XmlReader,
        "txt": TxtReader,
        "zip": ZipReader,
    }

    @classmethod
    def register(cls, format_key: str, reader_class: type):
        cls._readers[format_key.lower()] = reader_class

    @classmethod
    def get_reader(cls, filename: str, raw_bytes: bytes) -> BaseReader:
        detected = FormatDetector.detect_format(filename, raw_bytes)
        fmt = detected.get("format", "txt")
        reader_cls = cls._readers.get(fmt, TxtReader)
        return reader_cls()


class UniversalInspector:
    """Computes end-to-end diagnostics and inspection metrics on any loaded dataset."""

    @classmethod
    def inspect_dataframe(cls, df: pd.DataFrame, filename: str, format_type: str) -> Dict[str, Any]:
        """Generates comprehensive inspection report for a DataFrame."""
        if df is None:
            return {"is_valid": False, "error": "No DataFrame supplied"}

        total_rows, total_cols = df.shape
        total_cells = df.size
        memory_usage_bytes = int(df.memory_usage(deep=True).sum())

        # Duplicate detection (safeguarded against unhashable nested types like list/dict from JSON)
        try:
            # Check if any columns contain unhashable types
            has_unhashable = any(
                df[c].dtype == object and df[c].apply(lambda v: isinstance(v, (list, dict, set))).any()
                for c in df.columns
            )
            if has_unhashable:
                dedup_df = df.apply(lambda col: col.astype(str) if col.dtype == object else col)
                duplicate_rows_count = int(dedup_df.duplicated().sum()) if total_rows > 0 else 0
            else:
                duplicate_rows_count = int(df.duplicated().sum()) if total_rows > 0 else 0
        except Exception:
            duplicate_rows_count = 0
        duplicate_percentage = round((duplicate_rows_count / total_rows) * 100, 2) if total_rows > 0 else 0.0

        # Missing values detection
        missing_by_col = df.isna().sum().to_dict()
        total_missing = int(sum(missing_by_col.values()))
        overall_missing_pct = round((total_missing / total_cells) * 100, 2) if total_cells > 0 else 0.0

        # Columns classification
        numeric_cols = []
        categorical_cols = []
        datetime_cols = []
        boolean_cols = []
        column_profiles = []

        date_inconsistencies_summary = {}

        for col_name in df.columns:
            series = df[col_name]
            dtype_str = str(series.dtype)
            col_missing = int(series.isna().sum())
            col_missing_pct = round((col_missing / total_rows) * 100, 2) if total_rows > 0 else 0.0
            try:
                unique_count = int(series.nunique(dropna=True))
            except TypeError:
                unique_count = int(series.astype(str).nunique(dropna=True))

            # Sample distinct values
            sample_vals = series.dropna().head(3).tolist()

            is_numeric = pd.api.types.is_numeric_dtype(series)
            is_datetime = pd.api.types.is_datetime64_any_dtype(series)
            is_bool = pd.api.types.is_bool_dtype(series)

            profile = {
                "name": col_name,
                "dtype": dtype_str,
                "missing_count": col_missing,
                "missing_pct": col_missing_pct,
                "unique_count": unique_count,
                "sample_values": sample_vals,
                "is_numeric": is_numeric,
                "is_datetime": is_datetime,
                "is_bool": is_bool,
                "outliers": None,
                "date_diagnostics": None,
                "numeric_stats": None,
            }

            if is_numeric and not is_bool:
                numeric_cols.append(col_name)
                # Compute outlier metrics
                outlier_info = compute_column_outliers(series)
                profile["outliers"] = outlier_info

                num_clean = pd.to_numeric(series, errors="coerce").dropna()
                if not num_clean.empty:
                    profile["numeric_stats"] = {
                        "min": float(num_clean.min()),
                        "max": float(num_clean.max()),
                        "mean": round(float(num_clean.mean()), 2),
                        "median": round(float(num_clean.median()), 2),
                        "std": round(float(num_clean.std()), 2) if len(num_clean) > 1 else 0.0,
                    }
            elif is_datetime:
                datetime_cols.append(col_name)
            elif is_bool:
                boolean_cols.append(col_name)
            else:
                categorical_cols.append(col_name)
                # Check for date inconsistency in string column
                date_diag = detect_date_inconsistencies(series)
                if date_diag.get("has_dates"):
                    profile["date_diagnostics"] = date_diag
                    if date_diag.get("is_inconsistent"):
                        date_inconsistencies_summary[col_name] = date_diag

            column_profiles.append(profile)

        # Data health score
        health = calculate_dataset_health(df)

        return {
            "is_valid": True,
            "filename": filename,
            "format": format_type,
            "rows": total_rows,
            "columns": total_cols,
            "total_cells": total_cells,
            "memory_usage_bytes": memory_usage_bytes,
            "memory_formatted": format_bytes(memory_usage_bytes),
            "duplicate_rows": duplicate_rows_count,
            "duplicate_percentage": duplicate_percentage,
            "total_missing_cells": total_missing,
            "missing_percentage": overall_missing_pct,
            "numeric_columns": numeric_cols,
            "categorical_columns": categorical_cols,
            "datetime_columns": datetime_cols,
            "boolean_columns": boolean_cols,
            "column_profiles": column_profiles,
            "date_inconsistencies": date_inconsistencies_summary,
            "health_score": health,
        }
