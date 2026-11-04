"""
Universal Data Customisation & Automation Studio
Global Configuration and Constants
"""
import os
from pathlib import Path

# Application metadata
APP_TITLE = "Universal Data Customisation & Automation Studio"
APP_SUBTITLE = "Enterprise Multi-Format Data Ingestion, Inspection, Transformation & Automation Platform"
APP_VERSION = "9.0.0 (Production Ready - Universal Studio Complete)"
AUTHOR = "Antigravity Engineering"

# Root paths
BASE_DIR = Path(__file__).resolve().parent
CORE_DIR = BASE_DIR / "core"
PAGES_DIR = BASE_DIR / "pages"
UTILS_DIR = BASE_DIR / "utils"
MODULES_DIR = BASE_DIR / "modules"
SAMPLES_DIR = BASE_DIR / "samples"
WORKFLOWS_DIR = BASE_DIR / "workflows"

# Supported Formats
SUPPORTED_INPUT_EXTENSIONS = {
    ".xlsx": "Excel Workbook",
    ".xls": "Excel Legacy",
    ".csv": "Comma-Separated Values",
    ".tsv": "Tab-Separated Values",
    ".xml": "Extensible Markup Language",
    ".json": "JavaScript Object Notation",
    ".txt": "Plain / Delimited Text",
    ".zip": "ZIP Archive (contains supported files)",
}

SUPPORTED_OUTPUT_FORMATS = [
    "Excel (.xlsx)",
    "CSV (.csv)",
    "XML (.xml)",
    "JSON (.json)",
    "TXT (.txt)",
]

# File Size Limits
MAX_UPLOAD_SIZE_MB = 200
SAMPLE_PREVIEW_DEFAULT_ROWS = 25
SAMPLE_PREVIEW_MAX_ROWS = 1000

# Inspection Thresholds
DATE_INCONSISTENCY_SAMPLE_SIZE = 500
OUTLIER_IQR_MULTIPLIER = 1.5
HIGH_MISSINGNESS_THRESHOLD = 0.30  # 30% or more missing flags warning
DUPLICATE_SAMPLE_LIMIT = 50000
