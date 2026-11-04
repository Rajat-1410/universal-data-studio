# ⚡ Universal Data Customisation & Automation Studio

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://share.streamlit.io)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Tests: 92 Passed](https://img.shields.io/badge/tests-92%20passed-brightgreen.svg)](tests/)

An enterprise-grade, multi-format data ingestion, structural inspection, customisation, reconciliation, XML editing, TallyPrime ERP voucher updating, pipeline automation, and export platform built with Streamlit and Python.

---

## 🌟 Key Features & Architecture

- **Universal Multi-Format Ingestion:** Excel (`.xlsx`, `.xls`), CSV, XML, JSON, TXT, and ZIP archives up to 200MB.
- **Automated Data Profiling & Health Index:** Real-time schema inference, missingness analysis, duplicate detection, mixed date pattern discovery, IQR outliers, and letter-grade scoring (A+ to F).
- **Comprehensive Customisation Workspace:**
  - **Column Operations:** Rename, add, delete, reorder, merge, split, cast types, find & replace, formulas (`[Amount] * 1.18`), and value mapping.
  - **Row Operations:** Conditional filtering, positional deletion, deduplication, multi-column sorting, and sampling.
  - **Data Cleaning:** Impute nulls (mean, median, mode, constant), text standardization (trim, case, spaces), date format standardization, currency/numeric cleaning, and statistical outlier treatment.
  - **Structural Transformations:** Dataset appending, joins (inner, left, right, outer), pivot tables, and unpivoting (melting).
- **Advanced Record Matching & Bulk Reconciliation:** Compare original vs. revised datasets across composite keys with side-by-side cell delta tables and selective reconciliation.
- **Universal XML Studio:** Hierarchical node search, in-place tree editing, attribute manipulation, and tabular Excel-to-XML mapping.
- **Dedicated TallyPrime Bulk Voucher Updater:** Decoupled ERP module with GUID matching, double-entry balance validation (`Total Debit == Total Credit`), alter stamping (`ACTION="Alter"`), and multi-sheet audit Excel report generation.
- **Custom Workflow Builder ("Build My Workflow"):** Sequential pipeline chaining ($N \rightarrow N+1$), intermediate step previews, pre-bundled presets, and JSON recipe export/import.
- **Natural Language Customisation & AI Copilot:** Plain English prompt compilation with anti-hallucination guardrails, human confirmation gates, live sandbox previews, 100% offline semantic parsing, and optional Google Gemini Cloud LLM integration.
- **Validation & Quality Centre:** Multi-criteria data auditing with custom business constraints and downloadable 5-sheet OpenXML audit report.
- **Multi-Format Export Centre:** Export to Excel, CSV, XML, JSON, TXT, and an all-in-one Executive ZIP Package.

---

## 🚀 Quickstart & Local Installation

### 1. Clone the Repository
```bash
git clone https://github.com/<YOUR-USERNAME>/universal-data-studio.git
cd universal-data-studio
```

### 2. Set Up Virtual Environment & Install Dependencies
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Launch the Application
```bash
streamlit run app.py
```
Open **`http://localhost:8501`** (or configured port) in your web browser.

---

## 🌐 Deploy to Streamlit Community Cloud (Public Use)

You can deploy this application for free public use on **Streamlit Community Cloud**:

### Step 1: Push Code to GitHub
```bash
git init
git add .
git commit -m "Initial commit: Universal Data Customisation Studio v9.0.0"
git branch -M main
git remote add origin https://github.com/<YOUR-USERNAME>/<YOUR-REPO-NAME>.git
git push -u origin main
```

### Step 2: Deploy on Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with your GitHub account.
2. Click **"New app"**.
3. Select your repository: `<YOUR-USERNAME>/<YOUR-REPO-NAME>`.
4. Branch: `main`.
5. Main file path: `app.py`.
6. App URL: Customize your desired subdomain (e.g. `universal-data-studio.streamlit.app`).
7. Click **"Deploy!"**.

Streamlit Cloud will automatically install dependencies from `requirements.txt` and make your application accessible worldwide at your custom URL.

---

## 📖 Documentation & User Manual
A complete 13-section official User Manual with step-by-step practical tutorials is available as a downloadable PDF in the root directory:
👉 **`Universal_Data_Studio_User_Manual.pdf`**

To regenerate the PDF manual:
```bash
python scripts/generate_manual_pdf.py
```

---

## 🧪 Testing Suite
Run the comprehensive test suite across all 12 modules:
```bash
python -m pytest tests/ -v
```
All 92 unit and integration tests validate 100% test pass rate.

---

## 📄 License
Released under the MIT License. Built by Antigravity Engineering.
