"""
Universal File Writer
Serializes dataframes and trees into Excel (.xlsx), CSV, XML, JSON, and TXT.
"""
import io
import json
import pandas as pd
from typing import Dict, Any, Optional


class UniversalFileWriter:
    """Handles multi-format exports with formatting options."""

    @classmethod
    def to_excel(cls, df: pd.DataFrame, sheet_name: str = "Sheet1") -> bytes:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name=sheet_name, index=False)
        return buf.getvalue()

    @classmethod
    def to_csv(cls, df: pd.DataFrame, delimiter: str = ",") -> bytes:
        return df.to_csv(sep=delimiter, index=False).encode("utf-8")

    @classmethod
    def to_json(cls, df: pd.DataFrame, orient: str = "records", indent: int = 2) -> bytes:
        return df.to_json(orient=orient, indent=indent).encode("utf-8")

    @classmethod
    def to_xml(cls, df: pd.DataFrame, root_name: str = "data", row_name: str = "row") -> bytes:
        xml_str = df.to_xml(index=False, root_name=root_name, row_name=row_name)
        return xml_str.encode("utf-8")

    @classmethod
    def to_txt(cls, df: pd.DataFrame, delimiter: str = "|") -> bytes:
        return df.to_csv(sep=delimiter, index=False).encode("utf-8")
