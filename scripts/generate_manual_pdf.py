"""
Universal Data Customisation & Automation Studio
Official Documentation & User Manual PDF Generator
Generates a comprehensive, enterprise-grade multi-page PDF user manual using ReportLab.
"""
import os
import sys
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable,
)
from reportlab.pdfgen import canvas

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PDF_PATH = BASE_DIR / "Universal_Data_Studio_User_Manual.pdf"


class NumberedCanvas(canvas.Canvas):
    """Two-pass canvas to dynamically compute and draw 'Page X of Y' footers and top headers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        # Skip header and footer on cover page
        if self._pageNumber == 1:
            return

        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))

        # Top Running Header
        self.drawString(54, 752, "Universal Data Customisation & Automation Studio — Official User Manual")
        self.drawRightString(558, 752, "Production Release v9.0.0")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 746, 558, 746)

        # Bottom Running Footer
        self.line(54, 45, 558, 45)
        self.drawString(54, 32, "Confidential & Enterprise Proprietary — Antigravity Engineering")
        page_str = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 32, page_str)
        self.restoreState()


def build_manual_pdf(output_path: Path):
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )

    styles = getSampleStyleSheet()

    # Custom typography styles
    cover_title_style = ParagraphStyle(
        "CoverTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=24,
        leading=30,
        textColor=colors.HexColor("#0F172A"),
        alignment=0,
        spaceAfter=10,
    )

    cover_subtitle_style = ParagraphStyle(
        "CoverSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#2563EB"),
        alignment=0,
        spaceAfter=25,
    )

    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#0F172A"),
        spaceBefore=16,
        spaceAfter=8,
        keepWithNext=True,
    )

    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=12,
        leading=16,
        textColor=colors.HexColor("#1E3A8A"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True,
    )

    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#334155"),
        spaceAfter=6,
    )

    bullet_style = ParagraphStyle(
        "Bullet_Custom",
        parent=body_style,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=3,
    )

    code_callout_style = ParagraphStyle(
        "Callout_Custom",
        parent=styles["Normal"],
        fontName="Courier",
        fontSize=8.5,
        leading=11.5,
        textColor=colors.HexColor("#0F172A"),
        backColor=colors.HexColor("#F1F5F9"),
        borderPadding=8,
        spaceBefore=4,
        spaceAfter=8,
    )

    story = []

    # =========================================================================
    # 1. COVER PAGE
    # =========================================================================
    story.append(Spacer(1, 40))
    story.append(Paragraph("UNIVERSAL DATA CUSTOMISATION &amp; AUTOMATION STUDIO", cover_title_style))
    story.append(Paragraph("Enterprise Multi-Format Ingestion, Inspection, Reconciliation, Transformation &amp; Automation Platform", cover_subtitle_style))
    story.append(HRFlowable(width="100%", thickness=3, color=colors.HexColor("#2563EB"), spaceAfter=20))

    meta_table_data = [
        [Paragraph("<b>Release Version:</b>", body_style), Paragraph("v9.0.0 (Production Stable)", body_style)],
        [Paragraph("<b>Platform Engine:</b>", body_style), Paragraph("Python 3.13 / Streamlit Multi-Page Architecture", body_style)],
        [Paragraph("<b>Author / Architecture:</b>", body_style), Paragraph("Antigravity Engineering Team", body_style)],
        [Paragraph("<b>Supported Formats:</b>", body_style), Paragraph("Excel (.xlsx, .xls), CSV, XML, JSON, TXT, ZIP", body_style)],
        [Paragraph("<b>Target Audience:</b>", body_style), Paragraph("Data Analysts, Accountants, Operations Engineers, System Architects", body_style)],
        [Paragraph("<b>Live URL:</b>", body_style), Paragraph("<code>http://localhost:8505</code> / Streamlit Community Cloud", body_style)],
    ]
    meta_table = Table(meta_table_data, colWidths=[140, 360])
    meta_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
        ("BOX", (0, 0), (-1, -1), 1, colors.HexColor("#E2E8F0")),
        ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
        ("PADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(meta_table)

    story.append(Spacer(1, 30))
    story.append(Paragraph("<b>EXECUTIVE DOCUMENTATION ABSTRACT:</b>", h2_style))
    story.append(Paragraph(
        "This official manual provides end-to-end operational instructions, technical architecture blueprints, "
        "and step-by-step practical workflows for the Universal Data Customisation & Automation Studio. "
        "The application is engineered to eliminate friction when handling disparate file formats, non-standard schemas, "
        "data quality defects, ERP ledger updates (TallyPrime), and complex multi-step transformation pipelines without "
        "writing code or compromising data safety.",
        body_style,
    ))

    story.append(PageBreak())

    # =========================================================================
    # 2. TABLE OF CONTENTS & ARCHITECTURE
    # =========================================================================
    story.append(Paragraph("Table of Contents &amp; System Navigation", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=12))

    toc_data = [
        ["Section 1", "System Architecture & Core Design Principles", "Page 2"],
        ["Section 2", "Module 1 & 2: Dashboard & Universal File Upload", "Page 3"],
        ["Section 3", "Module 3: Universal File Inspector & Automated Profiling", "Page 4"],
        ["Section 4", "Module 4: Data Customisation Studio (Tabs A - F)", "Page 5"],
        ["Section 5", "Module 5: Advanced Record Matching & Bulk Reconciliation", "Page 6"],
        ["Section 6", "Module 6: Universal XML Studio & Format Conversion", "Page 7"],
        ["Section 7", "Module 7: Dedicated TallyPrime Bulk Voucher Updater", "Page 8"],
        ["Section 8", "Module 8: Custom Workflow Builder ('Build My Workflow')", "Page 9"],
        ["Section 9", "Module 9 & 10: Validation Centre & Multi-Format Export", "Page 10"],
        ["Section 10", "Module 11 & 12: Saved Recipes, Settings & AI Copilot", "Page 11"],
        ["Section 11", "Practical Step-by-Step Tutorials (Sales, Tally, Pipelines)", "Page 12"],
        ["Section 12", "Cloud Deployment Guide (Streamlit Community Cloud & Public Sharing)", "Page 13"],
    ]
    toc_table = Table([[Paragraph(c, body_style) for c in row] for row in toc_data], colWidths=[80, 360, 60])
    toc_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFFFFF")),
        ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.HexColor("#F1F5F9")),
        ("PADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(toc_table)

    story.append(Spacer(1, 15))
    story.append(Paragraph("1. System Architecture &amp; Core Design Principles", h1_style))
    story.append(Paragraph(
        "The studio is built on four core principles to guarantee enterprise reliability and zero data loss:",
        body_style,
    ))
    story.append(Paragraph("• <b>Strict Baseline Immutability:</b> Uploaded original files are stored in read-only memory and never overwritten automatically. All operations execute on staged working copies.", bullet_style))
    story.append(Paragraph("• <b>Session Undo / Redo Engine:</b> Every transformation is logged in an in-memory chronological snapshot stack, allowing full backward and forward traversal.", bullet_style))
    story.append(Paragraph("• <b>Anti-Hallucination Guardrails:</b> The AI Copilot and NLP engine fuzzy-match against actual dataset schemas; columns and values are never invented or assumed.", bullet_style))
    story.append(Paragraph("• <b>Format Independence & Decoupling:</b> Specialized modules (such as TallyPrime ERP) are decoupled from the generic tabular engine so universal tasks remain clean and unencumbered.", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # 3. MODULE 1 & 2: DASHBOARD & FILE UPLOAD
    # =========================================================================
    story.append(Paragraph("2. Modules 1 &amp; 2: Dashboard &amp; File Ingestion", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    story.append(Paragraph("Module 1: Studio Dashboard (<code>pages/dashboard.py</code>)", h2_style))
    story.append(Paragraph(
        "The Dashboard serves as the central command console. It displays the active dataset badge, "
        "a visual 9-phase architecture roadmap showing module completion, quick metric cards "
        "(Total Datasets in Memory, Total Processed Records, and Overall Data Health Index), "
        "and an in-memory loaded datasets inspector.",
        body_style,
    ))

    story.append(Paragraph("Module 2: Upload Files (<code>pages/upload.py</code>)", h2_style))
    story.append(Paragraph(
        "Supports universal ingestion up to 200MB per file with automatic format sniffing and structure parsing:",
        body_style,
    ))

    formats_data = [
        ["Format", "File Extension", "Internal Engine", "Key Parsing Capabilities"],
        ["Excel", ".xlsx, .xls", "openpyxl / xlrd", "Multi-sheet discovery, dynamic header detection, active sheet switcher."],
        ["CSV / TSV", ".csv, .tsv", "pandas C-engine", "Automatic delimiter detection (comma, tab, semicolon, pipe)."],
        ["XML", ".xml", "ElementTree / lxml", "Lossless tree parsing, tag hierarchies, attribute retention."],
        ["JSON", ".json", "json / pandas", "Record arrays, nested objects, tabular normalization."],
        ["Plain Text", ".txt", "built-in / pandas", "Delimited text, fixed-width parsing, log streams."],
        ["ZIP Archive", ".zip", "zipfile", "Automated unzipping and cataloging of contained supported files."],
    ]
    fmt_table = Table([[Paragraph(f"<b>{c}</b>" if idx == 0 else c, body_style) for c in row] for idx, row in enumerate(formats_data)], colWidths=[70, 80, 110, 240])
    fmt_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(fmt_table)

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Bundled Test Samples:</b> Users can immediately load built-in sample datasets (Sales Orders, Customer Records, Multi-Voucher Tally XML, Inventory JSON, and Archives) with 1 click to test features without uploading their own data.", body_style))

    story.append(PageBreak())

    # =========================================================================
    # 4. MODULE 3: FILE INSPECTOR & AUTOMATED PROFILING
    # =========================================================================
    story.append(Paragraph("3. Module 3: Universal File Inspector &amp; Profiling", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    story.append(Paragraph(
        "Immediately upon file upload, the Universal Inspector runs automated telemetry across the dataset:",
        body_style,
    ))

    story.append(Paragraph("• <b>Schema &amp; Type Invariants:</b> Infers true logical data types (numeric, datetime, boolean, string) and highlights type conflicts (e.g. currency strings stored in numeric fields).", bullet_style))
    story.append(Paragraph("• <b>Missing Value Distribution:</b> Identifies null counts and percentages per column, flagging columns exceeding the 30% missingness threshold.", bullet_style))
    story.append(Paragraph("• <b>Duplicate Record Detection:</b> Computes exact duplicate rows across all columns or composite keys with safety protections for unhashable JSON types.", bullet_style))
    story.append(Paragraph("• <b>Date Inconsistency Scanner:</b> Detects mixed, non-standard date representations (e.g. <code>2026-01-15</code> mixed with <code>15/01/2026</code> or compact Tally <code>20260115</code>).", bullet_style))
    story.append(Paragraph("• <b>Statistical Outliers (IQR):</b> Identifies values outside <code>[Q1 - 1.5*IQR, Q3 + 1.5*IQR]</code> for numeric metrics.", bullet_style))
    story.append(Paragraph("• <b>Interactive XML Visualizer:</b> For XML files, generates an interactive hierarchical tree display showing parent-child relationships, repeat counts, attributes, and element paths.", bullet_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Data Health Scoring Formula (0 - 100 Index):", h2_style))
    story.append(Paragraph(
        "<code>Health Score = 100 - min(40, Missing% * 1.5) - min(30, Duplicate% * 1.5) - DateFlags * 10 - OutlierFlags * 5</code>",
        code_callout_style,
    ))
    story.append(Paragraph("Letter grades are automatically assigned: <b>A+</b> (95-100), <b>A</b> (85-94), <b>B</b> (75-84), <b>C</b> (65-74), <b>D</b> (55-64), and <b>F</b> (&lt;55).", body_style))

    story.append(PageBreak())

    # =========================================================================
    # 5. MODULE 4: DATA CUSTOMISATION STUDIO
    # =========================================================================
    story.append(Paragraph("4. Module 4: Data Customisation &amp; Transformation Studio", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    story.append(Paragraph(
        "Located at <code>pages/customisation.py</code>, this is the primary interactive data workbench. "
        "It features 6 tabs providing comprehensive manipulation tools:",
        body_style,
    ))

    tab_desc_data = [
        ["Tab", "Feature Area", "Key Tools & Capabilities"],
        ["Tab 1", "🤖 AI Copilot", "Translates English prompts into proposed operations, sandbox preview, confirmation gate."],
        ["Tab 2", "🔤 Column Operations", "Rename, Add (constant/sequence/copy), Delete, Reorder, Merge, Split, Cast types, Find & Replace, Formulas (e.g. [Amount]*1.18), Value mapping dictionaries."],
        ["Tab 3", "🔢 Row Operations", "Dynamic filtering (equals, contains, >, <, is_null), Delete row by index, Deduplication (subset keys, keep first/last), Multi-column sorting, Row sampling."],
        ["Tab 4", "🧼 Data Cleaning", "Impute nulls (mean, median, mode, constant, ffill, bfill), Text standardization (trim, spaces, upper, lower, titlecase), Multi-format date standardizer, Currency cleanup, Outlier capping."],
        ["Tab 5", "🔀 Reshape & Multi-Data", "Append datasets, Joins (inner, left, right, outer), Pivot tables with aggregations, Unpivot (melt) wide data into tall normalized format."],
        ["Tab 6", "📜 Change History", "Complete step-by-step audit log, snapshot indices, instant Undo, Redo, and Reset to Baseline."],
    ]
    t_table = Table([[Paragraph(f"<b>{c}</b>" if idx == 0 else c, body_style) for c in row] for idx, row in enumerate(tab_desc_data)], colWidths=[60, 120, 320])
    t_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_table)

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>The Human Confirmation Gate:</b> Destructive transformations (such as permanently deleting columns or dropping records) always trigger a prominent yellow warning banner requiring explicit human confirmation before executing against the dataset.", body_style))

    story.append(PageBreak())

    # =========================================================================
    # 6. MODULE 5: RECORD MATCHING & BULK RECONCILIATION
    # =========================================================================
    story.append(Paragraph("5. Module 5: Advanced Record Matching &amp; Reconciliation", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    story.append(Paragraph(
        "Located at <code>pages/matching.py</code>, this module reconciles an <b>Original Dataset</b> against a <b>Revised Dataset</b> "
        "(e.g. matching updated ERP vouchers against bank statements or revised order registers).",
        body_style,
    ))

    story.append(Paragraph("Reconciliation Workflow:", h2_style))
    story.append(Paragraph("<b>Step 1: Dataset Selection:</b> Select the baseline Original dataset and target Revised dataset from memory.", bullet_style))
    story.append(Paragraph("<b>Step 2: Key Resolution:</b> Select single or composite matching keys (e.g. <code>OrderID</code>, <code>VoucherNumber + Date</code>, <code>Customer_Tax_ID</code>).", bullet_style))
    story.append(Paragraph("<b>Step 3: Deep Comparison:</b> The engine classifies all records into 4 mutual categories:", bullet_style))

    match_cat_data = [
        ["Match Status", "Definition", "System Behavior"],
        ["IDENTICAL", "Key exists in both; all compared attributes match exactly.", "No action required; preserved as pristine."],
        ["MODIFIED", "Key exists in both; one or more cell values differ.", "Displays side-by-side diff table highlighting modified cells."],
        ["NEW_IN_REVISED", "Key exists only in revised dataset.", "Identified as new additions staged for insertion."],
        ["MISSING_IN_ORIGINAL", "Key exists only in original; omitted in revised.", "Identified as omitted/deleted records."],
    ]
    mc_table = Table([[Paragraph(f"<b>{c}</b>" if idx == 0 else c, body_style) for c in row] for idx, row in enumerate(match_cat_data)], colWidths=[110, 190, 200])
    mc_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(mc_table)

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Step 4: Selective Reconciliation Controls:</b> Users choose whether to: (1) Update modified records, (2) Insert new records, and/or (3) Remove missing records. A fresh reconciled DataFrame is produced with 0 mutation of original files.", body_style))

    story.append(PageBreak())

    # =========================================================================
    # 7. MODULE 6: UNIVERSAL XML STUDIO
    # =========================================================================
    story.append(Paragraph("6. Module 6: Universal XML Studio &amp; Conversions", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    story.append(Paragraph(
        "Located at <code>pages/xml_studio.py</code>, this module provides an enterprise IDE for inspecting, searching, "
        "editing, mapping, and converting XML documents without losing namespaces, attributes, or encodings.",
        body_style,
    ))

    story.append(Paragraph("Core XML Capabilities:", h2_style))
    story.append(Paragraph("• <b>Hierarchical Node Search:</b> Search for nodes by tag name, text value, or attribute across deeply nested XML structures.", bullet_style))
    story.append(Paragraph("• <b>Lossless In-Place Mutation:</b> Edit element text, update attributes, add child elements, or delete specific elements while preserving comments and namespaces.", bullet_style))
    story.append(Paragraph("• <b>Tabular-to-XML Mapping Engine:</b> Map flat Excel or CSV columns to custom nested XML tags (e.g. mapping <code>OrderID</code> to <code>&lt;ROW id='...'&gt;</code> and <code>Amount</code> to <code>&lt;FINANCIAL/TOTAL&gt;</code>).", bullet_style))
    story.append(Paragraph("• <b>Cross-Format Conversions:</b> 1-click lossless conversions between Excel, CSV, XML, and JSON with syntax validation before export.", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # 8. MODULE 7: TALLYPRIME BULK VOUCHER UPDATER
    # =========================================================================
    story.append(Paragraph("7. Module 7: Dedicated TallyPrime Bulk Voucher Updater", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    story.append(Paragraph(
        "Located at <code>pages/tally_updater.py</code>, this is a decoupled accounting module engineered specifically "
        "for TallyPrime ERP bulk voucher modifications.",
        body_style,
    ))

    story.append(Paragraph("Why a Dedicated Tally Module is Critical:", h2_style))
    story.append(Paragraph(
        "Tally XML vouchers are highly complex, containing GST tax breakdowns, inventory details, bill allocations, "
        "cost centres, and bank ledger records. Modifying them naively destroys nested structures and breaks Tally import. "
        "Our engine guarantees 100% preservation of all untouched nodes.",
        body_style,
    ))

    story.append(Paragraph("Four-Step Voucher Updating Wizard:", h2_style))
    story.append(Paragraph("<b>Step 1: Upload Baseline Tally XML &amp; Revised Excel:</b> Ingests exported Tally XML and an Excel workbook containing revised ledger amounts.", bullet_style))
    story.append(Paragraph("<b>Step 2: Match Existing Vouchers:</b> Matches records by <code>GUID</code> or <code>VoucherNumber + Date</code>. Halts immediately if duplicate keys are detected in the Tally XML.", bullet_style))
    story.append(Paragraph("<b>Step 3: Double-Entry Balance Verification:</b> Audits that <code>Total Debit == Total Credit</code> across every voucher. Flags imbalances down to the penny.", bullet_style))
    story.append(Paragraph("<b>Step 4: Generate Alter XML &amp; 4-Sheet Audit Workbook:</b> Generates validated import-ready XML stamped with <code>ACTION='Alter'</code>, plus a 4-sheet reconciliation Excel report (<code>Audit_Summary</code>, <code>Voucher_Balances</code>, <code>Ledger_Modifications</code>, <code>Reconciliation_Diff</code>).", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # 9. MODULE 8: CUSTOM WORKFLOW BUILDER
    # =========================================================================
    story.append(Paragraph("8. Module 8: Custom Workflow Builder ('Build My Workflow')", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    story.append(Paragraph(
        "Located at <code>pages/workflow_builder.py</code>, this module allows users to assemble, configure, reorder, "
        "and execute sequential data processing pipelines (recipes).",
        body_style,
    ))

    story.append(Paragraph("Pipeline Architecture:", h2_style))
    story.append(Paragraph("• <b>Sequential Step Chaining:</b> The output DataFrame of Step <i>N</i> automatically becomes the input to Step <i>N+1</i>.", bullet_style))
    story.append(Paragraph("• <b>Intermediate State Inspection:</b> Expandable preview tables allow inspecting the intermediate DataFrame snapshot after each step.", bullet_style))
    story.append(Paragraph("• <b>Interactive Step Reordering:</b> Move steps up or down, toggle individual steps on/off, or delete steps directly from the visual canvas.", bullet_style))
    story.append(Paragraph("• <b>Recipe Serialization:</b> Save custom workflows as portable <code>.json</code> recipe files to replay against incoming datasets in the future.", bullet_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Pre-Bundled Production Recipes:", h2_style))
    story.append(Paragraph("1. <b>🧹 Comprehensive Audit &amp; Deduplicate:</b> Normalize text $\\rightarrow$ Standardize dates $\\rightarrow$ Deduplicate $\\rightarrow$ Validate non-empty.", bullet_style))
    story.append(Paragraph("2. <b>📊 Sales Tax Calculation &amp; Regional Aggregation:</b> Clean currency $\\rightarrow$ Compute 18% tax $\\rightarrow$ Standardize region $\\rightarrow$ Group &amp; sum.", bullet_style))
    story.append(Paragraph("3. <b>📇 CRM Contact Sanitation:</b> TitleCase names $\\rightarrow$ Impute missing city $\\rightarrow$ Deduplicate by Customer ID.", bullet_style))
    story.append(Paragraph("4. <b>🎯 Statistical Outlier Suppression (IQR):</b> Clean numeric fields $\\rightarrow$ Cap 1.5x IQR outliers $\\rightarrow$ Sort descending.", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # 10. MODULE 9 & 10: VALIDATION & EXPORT CENTRE
    # =========================================================================
    story.append(Paragraph("9. Modules 9 &amp; 10: Validation &amp; Multi-Format Export", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    story.append(Paragraph("Module 9: Validation &amp; Quality Centre (<code>pages/validation.py</code>)", h2_style))
    story.append(Paragraph(
        "Provides comprehensive data auditing against custom business rules and generates a downloadable 5-sheet OpenXML audit workbook:",
        body_style,
    ))
    story.append(Paragraph("• <b>Custom Constraint Checks:</b> Enforce mandatory non-null columns, 100% unique primary keys, and non-negative numbers.", bullet_style))
    story.append(Paragraph("• <b>Categorized Issue Severity:</b> Categorizes findings as <code>🔴 CRITICAL</code> (schema violations, missing mandatory keys), <code>🟡 WARNING</code> (mixed dates, duplicates), or <code>🔵 INFO</code> (outliers).", bullet_style))
    story.append(Paragraph("• <b>1-Click Auto-Remediation:</b> Automatically deduplicates records and imputes nulls with mode or constant in one click.", bullet_style))
    story.append(Paragraph("• <b>Downloadable 5-Sheet Excel Audit Workbook:</b> Exports <code>Executive_Summary</code>, <code>Data_Quality_Findings</code>, <code>Rule_Validation_Results</code>, <code>Transformation_History</code>, and <code>Problematic_Records</code>.", bullet_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Module 10: Multi-Format Export Centre (<code>pages/export.py</code>)", h2_style))
    story.append(Paragraph("Supports exporting clean datasets into 5 distinct enterprise formats or an all-in-one ZIP package:", body_style))

    exp_table_data = [
        ["Export Target", "Configuration Parameters", "Use Cases"],
        ["📗 Excel (.xlsx)", "Sheet title, include audit log sheet, frozen header row.", "Executive reports, management review, openpyxl pipelines."],
        ["📄 CSV (.csv)", "Delimiters (comma, semicolon, tab, pipe), encodings (utf-8, utf-8-sig).", "Data warehouse ingestion (BigQuery, Snowflake), analytics."],
        ["🌲 XML (.xml)", "Custom root tag (&lt;DATASET&gt;), custom record tag (&lt;ROW&gt;).", "ERP and legacy system integrations, SOAP/XML web services."],
        ["🗄️ JSON (.json)", "Orientations (records, split, index), pretty indentation.", "Web applications, MongoDB/NoSQL ingestion, REST APIs."],
        ["📝 Delimited TXT", "Custom delimiter, header inclusion.", "Mainframe, legacy payroll, fixed batch jobs."],
        ["📦 Executive ZIP", "Packages all 5 formats + 5-sheet Excel Quality Report + JSON manifest.", "One-click complete archive distribution."],
    ]
    exp_table = Table([[Paragraph(f"<b>{c}</b>" if idx == 0 else c, body_style) for c in row] for idx, row in enumerate(exp_table_data)], colWidths=[90, 210, 200])
    exp_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E2E8F0")),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(exp_table)

    story.append(PageBreak())

    # =========================================================================
    # 11. MODULE 11 & 12: SAVED WORKFLOWS & SETTINGS
    # =========================================================================
    story.append(Paragraph("10. Modules 11 &amp; 12: Recipes, Settings &amp; AI Copilot", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    story.append(Paragraph("Module 11: Saved Workflows Catalog (<code>pages/saved_workflows.py</code>)", h2_style))
    story.append(Paragraph(
        "A centralized library of pre-bundled and custom-built workflow recipes. "
        "Allows users to: (1) <b>Apply to Active Data</b> in 1 click, (2) <b>Open in Builder</b> to modify steps, "
        "(3) <b>Export Recipe (.json)</b> to disk, and (4) <b>Import Recipe (.json)</b> from external sources.",
        body_style,
    ))

    story.append(Paragraph("Module 12: Settings &amp; AI Configuration (<code>pages/settings.py</code>)", h2_style))
    story.append(Paragraph(
        "Configure runtime parameters, data preview row limits, session cache cleanup, and AI engine preferences:",
        body_style,
    ))
    story.append(Paragraph("• <b>Universal Semantic NLP (Offline Mode - Active Default):</b> Operates 100% locally on your machine with 0 network calls, 0 API keys, zero latency, and strict schema validation.", bullet_style))
    story.append(Paragraph("• <b>Google Gemini API (Cloud LLM Mode - Optional):</b> Enter your Google Gemini API key to enable cloud LLM interpretation of complex open-ended instructions with automatic schema grounding.", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # 12. STEP-BY-STEP PRACTICAL TUTORIALS
    # =========================================================================
    story.append(Paragraph("11. Practical Step-by-Step Tutorials", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    story.append(Paragraph("Tutorial A: Cleaning &amp; Standardizing a Dirty Sales Register", h2_style))
    story.append(Paragraph("<b>Goal:</b> Clean currency symbols from Amount, compute 18% GST tax, standardize dates, and deduplicate.", body_style))
    story.append(Paragraph("1. Open <b>2. Upload Files</b> and load <code>sample_sales.xlsx</code>.", bullet_style))
    story.append(Paragraph("2. Navigate to <b>4. Data Customisation</b> $\\rightarrow$ <b>🧼 Data Cleaning</b>. Select <code>Amount</code> and click <i>Clean Numeric Formatting</i>.", bullet_style))
    story.append(Paragraph("3. Go to <b>🔤 Column Operations</b> $\\rightarrow$ <i>Calculate Column / Formula</i>. Enter target <code>TotalWithTax</code> and formula <code>[Amount] * 1.18</code>.", bullet_style))
    story.append(Paragraph("4. Go to <b>🔢 Row Operations</b> $\\rightarrow$ <i>Remove Duplicates</i> based on <code>OrderID</code>.", bullet_style))
    story.append(Paragraph("5. Open <b>10. Export Centre</b> and click <i>Download Excel</i> or <i>Download CSV</i>.", bullet_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Tutorial B: Reconciling Bank Excel Statements with Tally XML", h2_style))
    story.append(Paragraph("<b>Goal:</b> Reconcile revised ledger balances, verify accounting debits and credits, and produce import XML.", body_style))
    story.append(Paragraph("1. Navigate to <b>7. TallyPrime Updater</b>.", bullet_style))
    story.append(Paragraph("2. Under Step 1, click <i>Load Bundled Tally Samples</i> (loads original XML and revised Excel).", bullet_style))
    story.append(Paragraph("3. Under Step 2, select Matching Strategy: <code>GUID</code> and click <i>Match Vouchers</i>.", bullet_style))
    story.append(Paragraph("4. Under Step 3, review the Double-Entry Balance Audit (ensuring Difference = 0.00).", bullet_style))
    story.append(Paragraph("5. Under Step 4, click <i>Generate Updated Tally XML</i> and download both the XML and the 4-sheet Reconciliation Excel Workbook.", bullet_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Tutorial C: Using Natural Language Instructions", h2_style))
    story.append(Paragraph("<b>Goal:</b> Execute transformations using plain English prompts.", body_style))
    story.append(Paragraph("1. In <b>4. Data Customisation</b>, open the <b>🤖 AI Natural Language Copilot</b> tab.", bullet_style))
    story.append(Paragraph("2. Type: <code>Rename Region to SalesRegion and calculate Tax as [Amount] * 0.18</code>.", bullet_style))
    story.append(Paragraph("3. Click <i>🔍 Parse &amp; Propose Transformation</i>.", bullet_style))
    story.append(Paragraph("4. Review the Proposed Action Card and Live Sandbox Preview.", bullet_style))
    story.append(Paragraph("5. Click <i>✅ Confirm &amp; Execute Transformation</i>.", bullet_style))

    story.append(PageBreak())

    # =========================================================================
    # 13. CLOUD DEPLOYMENT GUIDE (STREAMLIT COMMUNITY CLOUD)
    # =========================================================================
    story.append(Paragraph("12. Cloud Deployment Guide: Streamlit for Public Use", h1_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#CBD5E1"), spaceAfter=10))

    story.append(Paragraph(
        "To deploy this application to the public internet using Streamlit Community Cloud (free hosting), "
        "follow these simple instructions:",
        body_style,
    ))

    story.append(Paragraph("Phase 1: Initialize Git &amp; Push to GitHub", h2_style))
    story.append(Paragraph("In your terminal, navigate to the project directory and run:", body_style))
    story.append(Paragraph(
        "git init\n"
        "git add .\n"
        "git commit -m 'Initial commit: Universal Data Studio v9.0.0'\n"
        "git branch -M main\n"
        "git remote add origin https://github.com/&lt;YOUR-GITHUB-USERNAME&gt;/&lt;REPO-NAME&gt;.git\n"
        "git push -u origin main",
        code_callout_style,
    ))

    story.append(Paragraph("Phase 2: Deploy on Streamlit Community Cloud", h2_style))
    story.append(Paragraph("1. Open your browser and navigate to <b>share.streamlit.io</b> (sign in with GitHub).", bullet_style))
    story.append(Paragraph("2. Click the <b>'New app'</b> button in the top right corner.", bullet_style))
    story.append(Paragraph("3. In the deployment configuration form, fill in:", bullet_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• <b>Repository:</b> <code>&lt;YOUR-GITHUB-USERNAME&gt;/&lt;REPO-NAME&gt;</code>", bullet_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• <b>Branch:</b> <code>main</code>", bullet_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• <b>Main file path:</b> <code>app.py</code>", bullet_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;• <b>App URL (optional):</b> customize your public subdomain (e.g. <code>universal-data-studio.streamlit.app</code>)", bullet_style))
    story.append(Paragraph("4. Click <b>'Deploy!'</b>. Streamlit Cloud will automatically install dependencies from <code>requirements.txt</code>, configure the theme from <code>.streamlit/config.toml</code>, and launch the app online.", bullet_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Phase 3: Immediate Local Network Public Sharing", h2_style))
    story.append(Paragraph("To immediately share the app with colleagues on your local Wi-Fi / LAN network right now:", body_style))
    story.append(Paragraph(
        "streamlit run app.py --server.port 8505 --server.address 0.0.0.0",
        code_callout_style,
    ))
    story.append(Paragraph("Colleagues on the same network can access it directly via <code>http://&lt;YOUR-IP-ADDRESS&gt;:8505</code>.", body_style))

    # Build PDF
    doc.build(story, canvasmaker=NumberedCanvas)
    return output_path


if __name__ == "__main__":
    out_pdf = build_manual_pdf(OUTPUT_PDF_PATH)
    print(f"User manual generated successfully at: {out_pdf} (Size: {out_pdf.stat().st_size} bytes)")
