"""
Universal Format Detector
Robustly detects file format, encoding, magic signatures, delimiters, and archive structures.
"""
import io
import os
import zipfile
import re
from typing import Dict, Any, Optional, Tuple


class FormatDetector:
    """Universal detector for multi-format data ingestion."""

    MAGIC_SIGNATURES = {
        b"PK\x03\x04": "zip_based",  # Can be ZIP, XLSX, DOCX, JAR
        b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1": "excel_xls",  # OLE2 Compound File (Excel 97-2003)
        b"%PDF": "pdf",
    }

    @classmethod
    def detect_encoding(cls, raw_bytes: bytes) -> str:
        """Heuristically detects character encoding for text-based formats."""
        if not raw_bytes:
            return "utf-8"

        # Check for Byte Order Marks (BOM)
        if raw_bytes.startswith(b"\xef\xbb\xbf"):
            return "utf-8-sig"
        if raw_bytes.startswith(b"\xff\xfe"):
            return "utf-16-le"
        if raw_bytes.startswith(b"\xfe\xff"):
            return "utf-16-be"

        # Try utf-8
        try:
            raw_bytes[:65536].decode("utf-8")
            return "utf-8"
        except UnicodeDecodeError:
            pass

        # Try common western encodings
        for enc in ["cp1252", "latin-1", "iso-8859-1"]:
            try:
                raw_bytes[:65536].decode(enc)
                return enc
            except UnicodeDecodeError:
                continue

        return "utf-8"  # fallback

    @classmethod
    def sniff_delimiter(cls, sample_text: str) -> str:
        """Detects whether text is CSV, TSV, Semicolon-delimited, or Pipe-delimited."""
        if not sample_text:
            return ","

        lines = [line.strip() for line in sample_text.splitlines() if line.strip()][:20]
        if not lines:
            return ","

        candidates = [",", "\t", ";", "|"]
        scores = {}

        for cand in candidates:
            counts = [line.count(cand) for line in lines]
            avg_count = sum(counts) / len(counts)
            # High count and consistent column counts per line
            variance = sum((c - avg_count) ** 2 for c in counts) / len(counts)
            if avg_count >= 1 and variance < 2.0:
                scores[cand] = avg_count * 10 - variance
            elif avg_count >= 1:
                scores[cand] = avg_count

        if scores:
            best = max(scores.items(), key=lambda x: x[1])[0]
            return best

        return ","

    @classmethod
    def is_excel_xlsx_zip(cls, raw_bytes: bytes) -> bool:
        """Checks if a zip archive is actually an OpenXML Excel workbook (.xlsx)."""
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                names = zf.namelist()
                return any("xl/workbook.xml" in name or "[Content_Types].xml" in name and any(n.startswith("xl/") for n in names) for name in names)
        except Exception:
            return False

    @classmethod
    def detect_format(cls, filename: str, raw_bytes: bytes) -> Dict[str, Any]:
        """
        Analyzes filename and binary contents to produce an authoritative format report.
        """
        ext = os.path.splitext(filename)[1].lower() if filename else ""
        header = raw_bytes[:1024] if raw_bytes else b""
        size_bytes = len(raw_bytes)

        detected = {
            "extension": ext,
            "format": "unknown",
            "display_name": "Unknown Format",
            "mime_type": "application/octet-stream",
            "is_archive": False,
            "encoding": "binary",
            "confidence": 0.0,
            "details": {},
        }

        # 1. Check for OLE2 Excel (.xls)
        if header.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1") or ext == ".xls":
            detected["format"] = "excel"
            detected["display_name"] = "Excel Legacy (.xls)"
            detected["mime_type"] = "application/vnd.ms-excel"
            detected["confidence"] = 0.95
            return detected

        # 2. Check for ZIP / XLSX
        if header.startswith(b"PK\x03\x04"):
            if cls.is_excel_xlsx_zip(raw_bytes) or ext in [".xlsx", ".xlsm"]:
                detected["format"] = "excel"
                detected["display_name"] = "Excel Workbook (.xlsx)"
                detected["mime_type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                detected["confidence"] = 0.99
                return detected
            else:
                # Regular ZIP Archive
                detected["format"] = "zip"
                detected["display_name"] = "ZIP Archive (.zip)"
                detected["mime_type"] = "application/zip"
                detected["is_archive"] = True
                detected["confidence"] = 0.95
                try:
                    with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
                        namelist = zf.namelist()
                        detected["details"]["archive_files"] = namelist
                        detected["details"]["file_count"] = len(namelist)
                except Exception as e:
                    detected["details"]["archive_error"] = str(e)
                return detected

        # 3. Check for XML
        # Try decoding preview for text-based analysis
        encoding = cls.detect_encoding(raw_bytes)
        detected["encoding"] = encoding
        try:
            preview_text = raw_bytes[:4096].decode(encoding, errors="replace").strip()
        except Exception:
            preview_text = ""

        if preview_text.startswith("<?xml") or (preview_text.startswith("<") and ">" in preview_text and not preview_text.startswith("<!DOCTYPE html") and ext == ".xml"):
            detected["format"] = "xml"
            detected["display_name"] = "XML Document (.xml)"
            detected["mime_type"] = "application/xml"
            detected["confidence"] = 0.95
            return detected

        # 4. Check for JSON
        stripped = preview_text.lstrip()
        if (stripped.startswith("{") or stripped.startswith("[")) and (ext == ".json" or ext == ""):
            # Check if valid JSON prefix
            detected["format"] = "json"
            detected["display_name"] = "JSON Document (.json)"
            detected["mime_type"] = "application/json"
            detected["confidence"] = 0.90
            return detected

        # 5. Check for CSV / TSV
        if ext in [".csv", ".tsv"]:
            delim = "\t" if ext == ".tsv" else cls.sniff_delimiter(preview_text)
            detected["format"] = "csv"
            detected["display_name"] = "Delimited Text (CSV/TSV)"
            detected["mime_type"] = "text/csv"
            detected["confidence"] = 0.90
            detected["details"]["delimiter"] = delim
            return detected

        # 6. Check for Plain Text (.txt)
        if ext == ".txt":
            delim = cls.sniff_delimiter(preview_text)
            detected["format"] = "txt"
            detected["display_name"] = "Plain / Delimited Text (.txt)"
            detected["mime_type"] = "text/plain"
            detected["confidence"] = 0.85
            detected["details"]["detected_delimiter"] = delim
            return detected

        # 7. Fallback based on extension
        if ext in [".xlsx", ".xls"]:
            detected["format"] = "excel"
            detected["display_name"] = "Excel Spreadsheet"
            detected["mime_type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            detected["confidence"] = 0.70
        elif ext == ".xml":
            detected["format"] = "xml"
            detected["display_name"] = "XML Document"
            detected["mime_type"] = "application/xml"
            detected["confidence"] = 0.70
        elif ext == ".json":
            detected["format"] = "json"
            detected["display_name"] = "JSON Document"
            detected["mime_type"] = "application/json"
            detected["confidence"] = 0.70
        elif ext in [".csv", ".txt"]:
            detected["format"] = "csv" if ext == ".csv" else "txt"
            detected["display_name"] = "Text Document"
            detected["mime_type"] = "text/plain"
            detected["confidence"] = 0.60
            detected["details"]["delimiter"] = cls.sniff_delimiter(preview_text)
        elif ext == ".zip":
            detected["format"] = "zip"
            detected["display_name"] = "ZIP Archive"
            detected["mime_type"] = "application/zip"
            detected["is_archive"] = True
            detected["confidence"] = 0.70

        return detected
