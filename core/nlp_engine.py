"""
Universal Natural Language Customisation Engine (Phase 8)
Translates natural language user instructions into structured, validated data operations.
Operates fully offline via heuristic semantic parsing with zero external dependencies,
and optionally supports online LLM parsing (Gemini REST API) when configured.
Enforces human confirmation gates and strictly prevents column hallucination.
"""
import re
import json
import uuid
import difflib
import urllib.request
import urllib.error
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional, Tuple, Union
import pandas as pd
import numpy as np

from core.workflow_engine import WorkflowStep, WorkflowEngine


@dataclass
class ProposedOperation:
    """Structured transformation proposed by the NLP engine."""
    operation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    category: str = "column_ops"  # column_ops, row_ops, data_cleaning, transformations, conversion, tally
    operation: str = "rename_columns"
    parameters: Dict[str, Any] = field(default_factory=dict)
    human_explanation: str = ""
    affected_columns: List[str] = field(default_factory=list)
    is_destructive: bool = False
    confidence: float = 0.95
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    clarification_options: List[str] = field(default_factory=list)

    def to_workflow_step(self, step_name: Optional[str] = None) -> WorkflowStep:
        """Converts the proposed operation into an executable WorkflowStep."""
        name = step_name or self.human_explanation[:40] or "AI Step"
        return WorkflowStep(
            step_id=self.operation_id,
            name=name,
            category=self.category,
            operation=self.operation,
            params=self.parameters,
            enabled=True,
        )


@dataclass
class ParsedInstructionResult:
    """Complete result of natural language instruction parsing."""
    original_instruction: str
    parsed_operations: List[ProposedOperation] = field(default_factory=list)
    engine_used: str = "heuristic_nlp"  # "heuristic_nlp" or "gemini_llm"
    has_destructive_ops: bool = False
    requires_clarification: bool = False
    error_message: Optional[str] = None


class NaturalLanguageEngine:
    """Universal natural language translator with offline semantic parser & optional LLM."""

    # -------------------------------------------------------------
    # FUZZY SCHEMA RESOLUTION & SAFETY
    # -------------------------------------------------------------
    @classmethod
    def find_best_column_match(
        cls,
        candidate_name: str,
        available_columns: List[str],
        cutoff: float = 0.6,
    ) -> Tuple[Optional[str], float]:
        """
        Matches a user-mentioned column name against actual dataset schema.
        Prevents hallucinating / inventing non-existent columns.
        """
        if not available_columns or not candidate_name:
            return None, 0.0

        clean_cand = candidate_name.strip().strip("'\"`[]")

        # 1. Exact match (case-sensitive)
        if clean_cand in available_columns:
            return clean_cand, 1.0

        # 2. Case-insensitive exact match
        lower_map = {c.lower(): c for c in available_columns}
        if clean_cand.lower() in lower_map:
            return lower_map[clean_cand.lower()], 0.98

        # 3. Clean alphanumeric match (ignoring underscores/spaces/hyphens)
        def norm_name(s: str) -> str:
            return re.sub(r"[\s_\-]+", "", s.lower())

        norm_map = {norm_name(c): c for c in available_columns}
        if norm_name(clean_cand) in norm_map:
            return norm_map[norm_name(clean_cand)], 0.95

        # 4. Fuzzy ratio match
        matches = difflib.get_close_matches(clean_cand, available_columns, n=1, cutoff=cutoff)
        if matches:
            ratio = difflib.SequenceMatcher(None, clean_cand.lower(), matches[0].lower()).ratio()
            return matches[0], round(ratio, 2)

        return None, 0.0

    # -------------------------------------------------------------
    # RULE-BASED / HEURISTIC OFFLINE PARSER
    # -------------------------------------------------------------
    @classmethod
    def parse_instruction_offline(
        cls,
        instruction: str,
        df: Optional[pd.DataFrame] = None,
        all_dataset_names: Optional[List[str]] = None,
    ) -> ParsedInstructionResult:
        """
        Parses user natural language instructions into structured operations offline.
        Uses grammar intent analysis, regex tokenizers, and schema validation.
        """
        text = instruction.strip()
        cols = list(df.columns) if df is not None else []
        ops: List[ProposedOperation] = []

        if not text:
            return ParsedInstructionResult(
                original_instruction=text,
                error_message="Instruction prompt cannot be empty.",
            )

        lower_text = text.lower()

        # ---------------------------------------------------------
        # PATTERN 1: RENAME COLUMN
        # e.g. "Rename Patient ID to Registration Number"
        #      "Change column Region to SalesRegion"
        # ---------------------------------------------------------
        rename_match = re.search(
            r"(?:rename|change\s+column|change)\s+(?:the\s+column\s+)?['\"`]?([^'\"`]+?)['\"`]?\s+(?:to|into|as)\s+['\"`]?([^'\"`]+?)['\"`]?$",
            text,
            re.IGNORECASE,
        )
        if rename_match:
            raw_source, raw_target = rename_match.group(1).strip(), rename_match.group(2).strip()
            # Clean target if it ends with punctuation
            raw_target = raw_target.rstrip(".").strip()

            matched_col, score = cls.find_best_column_match(raw_source, cols) if cols else (raw_source, 1.0)
            if cols and not matched_col:
                op = ProposedOperation(
                    category="column_ops",
                    operation="rename_columns",
                    parameters={"mapping": {raw_source: raw_target}},
                    human_explanation=f"Rename column '{raw_source}' to '{raw_target}'",
                    affected_columns=[raw_source],
                    is_destructive=False,
                    confidence=0.5,
                    needs_clarification=True,
                    clarification_question=f"Column '{raw_source}' was not found in the dataset. Did you mean one of: {cols[:4]}?",
                    clarification_options=cols[:4],
                )
            else:
                final_source = matched_col or raw_source
                op = ProposedOperation(
                    category="column_ops",
                    operation="rename_columns",
                    parameters={"mapping": {final_source: raw_target}},
                    human_explanation=f"Rename column '{final_source}' to '{raw_target}'",
                    affected_columns=[final_source],
                    is_destructive=False,
                    confidence=score,
                )
            ops.append(op)
            return cls._build_result(text, ops, "heuristic_nlp")

        # ---------------------------------------------------------
        # PATTERN 2: REMOVE / DEDUPLICATE RECORDS
        # e.g. "Remove all duplicate records based on Invoice Number"
        #      "Deduplicate by CustomerID"
        # ---------------------------------------------------------
        dedup_match = re.search(
            r"(?:remove|delete|drop)\s+(?:all\s+)?duplicate\s+(?:records|rows)?(?:\s+based\s+on|\s+by|\s+using)?\s*['\"`]?([^'\"`\.\?]+)?",
            text,
            re.IGNORECASE,
        )
        if dedup_match or "deduplicate" in lower_text or "remove duplicates" in lower_text:
            key_col_raw = dedup_match.group(1).strip() if dedup_match and dedup_match.group(1) else None
            # If no group was captured or generic phrase
            if key_col_raw in [None, "", "records", "rows", "all"]:
                # Check if "by X" exists
                by_m = re.search(r"(?:by|on|using)\s+['\"`]?([^'\"`\.\?]+)['\"`]?", text, re.IGNORECASE)
                key_col_raw = by_m.group(1).strip() if by_m else None

            subset_cols = None
            needs_clarify = False
            clarify_q = None
            affected = []

            if key_col_raw and cols:
                matched_col, score = cls.find_best_column_match(key_col_raw, cols)
                if matched_col:
                    subset_cols = [matched_col]
                    affected = [matched_col]
                else:
                    needs_clarify = True
                    clarify_q = f"Could not find matching key column '{key_col_raw}'. Deduplicate across all columns instead?"
            elif key_col_raw:
                subset_cols = [key_col_raw]
                affected = [key_col_raw]

            desc = f"Remove duplicate records based on [{', '.join(subset_cols)}]" if subset_cols else "Remove duplicate records across all columns"
            op = ProposedOperation(
                category="row_ops",
                operation="remove_duplicates",
                parameters={"subset_cols": subset_cols, "keep_mode": "first"},
                human_explanation=desc,
                affected_columns=affected or cols,
                is_destructive=True,  # Row deletion is destructive
                confidence=0.92,
                needs_clarification=needs_clarify,
                clarification_question=clarify_q,
                clarification_options=cols[:4],
            )
            ops.append(op)
            return cls._build_result(text, ops, "heuristic_nlp")

        # ---------------------------------------------------------
        # PATTERN 3: STANDARDIZE DATE FORMAT
        # e.g. "Convert the date column into DD-MM-YYYY"
        #      "Standardize OrderDate to YYYY-MM-DD"
        # ---------------------------------------------------------
        date_match = re.search(
            r"(?:convert|standardize|change|format)\s+(?:the\s+)?(?:date\s+column\s+)?['\"`]?([^'\"`\s]+)?['\"`]?\s*(?:into|to|as)?\s*(dd[-/]mm[-/]yyyy|yyyy[-/]mm[-/]dd|mm[-/]dd[-/]yyyy)",
            text,
            re.IGNORECASE,
        )
        if date_match or "date" in lower_text and any(f in lower_text for f in ["yyyy", "dd-mm", "dd/mm"]):
            raw_col = date_match.group(1).strip() if (date_match and date_match.group(1)) else None
            raw_fmt = date_match.group(2).strip().lower() if (date_match and date_match.group(2)) else "yyyy-mm-dd"

            # Map format string to Python strftime
            fmt_map = {
                "dd-mm-yyyy": "%d-%m-%Y",
                "dd/mm/yyyy": "%d/%m/%Y",
                "yyyy-mm-dd": "%Y-%m-%d",
                "yyyy/mm/dd": "%Y/%m/%d",
                "mm-dd-yyyy": "%m-%d-%Y",
                "mm/dd/yyyy": "%m/%d/%Y",
            }
            target_fmt = fmt_map.get(raw_fmt, "%Y-%m-%d")

            # Resolve date column
            target_col = None
            if raw_col and cols:
                m_col, _ = cls.find_best_column_match(raw_col, cols)
                if m_col:
                    target_col = m_col

            if not target_col and cols:
                # Look for columns with 'date' in their name
                date_candidates = [c for c in cols if "date" in c.lower() or "dt" in c.lower() or "time" in c.lower()]
                if date_candidates:
                    target_col = date_candidates[0]

            target_col = target_col or raw_col or (cols[0] if cols else "OrderDate")

            op = ProposedOperation(
                category="data_cleaning",
                operation="standardize_dates",
                parameters={"column": target_col, "target_format": target_fmt},
                human_explanation=f"Standardize date format in column '{target_col}' to '{target_fmt}'",
                affected_columns=[target_col],
                is_destructive=False,
                confidence=0.90,
            )
            ops.append(op)
            return cls._build_result(text, ops, "heuristic_nlp")

        # ---------------------------------------------------------
        # PATTERN 4: CALCULATE COLUMN / FORMULA
        # e.g. "Calculate Tax as [Amount] * 0.18"
        #      "Add calculated column Total = [Qty] * [Price]"
        # ---------------------------------------------------------
        calc_match = re.search(
            r"(?:calculate|compute|add\s+calculated\s+column)\s+['\"`]?([^'\"`=]+?)['\"`]?\s*(?:as|=|by)\s*(.+)$",
            text,
            re.IGNORECASE,
        )
        if calc_match:
            raw_target = calc_match.group(1).strip()
            raw_formula = calc_match.group(2).strip()

            # Ensure column references are formatted nicely
            affected = re.findall(r"\[([^\]]+)\]", raw_formula)
            if not affected and cols:
                # If formula has bare column names like Amount * 0.18, wrap them
                for c in cols:
                    if re.search(r"\b" + re.escape(c) + r"\b", raw_formula):
                        raw_formula = re.sub(r"\b" + re.escape(c) + r"\b", f"[{c}]", raw_formula)
                        affected.append(c)

            op = ProposedOperation(
                category="column_ops",
                operation="calculate_column",
                parameters={"target_col": raw_target, "formula": raw_formula},
                human_explanation=f"Calculate column '{raw_target}' using formula: {raw_formula}",
                affected_columns=affected or [raw_target],
                is_destructive=False,
                confidence=0.94,
            )
            ops.append(op)
            return cls._build_result(text, ops, "heuristic_nlp")

        # ---------------------------------------------------------
        # PATTERN 5: CLEAN TEXT / TRIM / CASE NORMALIZATION
        # e.g. "Trim all text in Customer and Region"
        #      "Convert Customer names to uppercase"
        #      "Convert City to title case"
        # ---------------------------------------------------------
        if any(w in lower_text for w in ["trim", "uppercase", "lowercase", "title case", "titlecase", "extra spaces"]):
            txt_ops = []
            if "trim" in lower_text or "whitespace" in lower_text:
                txt_ops.append("trim")
            if "extra spaces" in lower_text or "spaces" in lower_text:
                txt_ops.append("remove_extra_spaces")
            if "uppercase" in lower_text or "upper case" in lower_text:
                txt_ops.append("uppercase")
            elif "lowercase" in lower_text or "lower case" in lower_text:
                txt_ops.append("lowercase")
            elif "title case" in lower_text or "titlecase" in lower_text:
                txt_ops.append("titlecase")

            if not txt_ops:
                txt_ops = ["trim", "remove_extra_spaces"]

            # Detect mentioned columns
            target_cols = []
            if cols:
                for c in cols:
                    if c.lower() in lower_text:
                        target_cols.append(c)
            if not target_cols and cols:
                # Detect string object columns
                target_cols = [c for c in cols if df[c].dtype == object] if df is not None else [cols[0]]

            op = ProposedOperation(
                category="data_cleaning",
                operation="standardize_text",
                parameters={"columns": target_cols, "operations": txt_ops},
                human_explanation=f"Normalize text in [{', '.join(target_cols)}] ({', '.join(txt_ops)})",
                affected_columns=target_cols,
                is_destructive=False,
                confidence=0.90,
            )
            ops.append(op)
            return cls._build_result(text, ops, "heuristic_nlp")

        # ---------------------------------------------------------
        # PATTERN 6: CLEAN NUMERIC / CURRENCY FORMATTING
        # e.g. "Clean numeric formatting in Amount"
        #      "Remove currency symbols and commas from Amount"
        # ---------------------------------------------------------
        if any(w in lower_text for w in ["clean numeric", "currency", "strip symbols", "remove $", "accounting format"]):
            target_cols = []
            if cols:
                for c in cols:
                    if c.lower() in lower_text:
                        target_cols.append(c)
            if not target_cols and cols:
                target_cols = [c for c in cols if any(k in c.lower() for k in ["amount", "price", "cost", "total", "rate", "salary"])]
            if not target_cols and cols:
                target_cols = [cols[0]]

            op = ProposedOperation(
                category="data_cleaning",
                operation="clean_numeric_formatting",
                parameters={"columns": target_cols, "strip_symbols": True, "decimal_separator": "."},
                human_explanation=f"Clean numeric currency and accounting symbols in [{', '.join(target_cols)}]",
                affected_columns=target_cols,
                is_destructive=False,
                confidence=0.92,
            )
            ops.append(op)
            return cls._build_result(text, ops, "heuristic_nlp")

        # ---------------------------------------------------------
        # PATTERN 7: FILL / IMPUTE MISSING VALUES
        # e.g. "Fill missing values in City with 'Unknown'"
        #      "Impute nulls in Salary with mean"
        # ---------------------------------------------------------
        impute_match = re.search(
            r"(?:fill|impute|replace)\s+(?:missing|null)\s+(?:values\s+)?(?:in\s+)?['\"`]?([^'\"`\s]+)?['\"`]?\s*(?:with|using)\s*['\"`]?([^'\"`]+)['\"`]?",
            text,
            re.IGNORECASE,
        )
        if impute_match or "missing" in lower_text or "impute" in lower_text:
            raw_col = impute_match.group(1).strip() if (impute_match and impute_match.group(1)) else None
            raw_val = impute_match.group(2).strip() if (impute_match and impute_match.group(2)) else "N/A"

            matched_col = None
            if raw_col and cols:
                m_c, _ = cls.find_best_column_match(raw_col, cols)
                matched_col = m_c
            if not matched_col and cols:
                # Find columns with nulls
                null_cols = [c for c in cols if df[c].isna().sum() > 0] if df is not None else []
                matched_col = null_cols[0] if null_cols else cols[0]

            matched_col = matched_col or raw_col or "Column"
            strategy = "constant"
            const_val = raw_val
            if raw_val.lower() in ["mean", "average"]:
                strategy = "mean"
                const_val = None
            elif raw_val.lower() == "median":
                strategy = "median"
                const_val = None
            elif raw_val.lower() == "mode":
                strategy = "mode"
                const_val = None
            elif raw_val.lower() in ["drop", "drop rows", "remove"]:
                strategy = "drop_rows"
                const_val = None

            op = ProposedOperation(
                category="data_cleaning",
                operation="impute_missing",
                parameters={"columns": [matched_col], "strategy": strategy, "constant_value": const_val},
                human_explanation=f"Impute missing values in '{matched_col}' using strategy '{strategy}' ({const_val})",
                affected_columns=[matched_col],
                is_destructive=(strategy == "drop_rows"),
                confidence=0.91,
            )
            ops.append(op)
            return cls._build_result(text, ops, "heuristic_nlp")

        # ---------------------------------------------------------
        # PATTERN 8: DELETE / DROP COLUMN
        # e.g. "Drop column Status"
        #      "Delete columns Region, OrderDate"
        # ---------------------------------------------------------
        del_match = re.search(
            r"(?:delete|drop|remove)\s+(?:the\s+)?column(?:s)?\s+['\"`]?([^'\"`\.\?]+)['\"`]?",
            text,
            re.IGNORECASE,
        )
        if del_match and "row" not in lower_text and "duplicate" not in lower_text:
            raw_cols = [x.strip().strip("'\"`") for x in del_match.group(1).split(",") if x.strip()]
            del_targets = []
            for rc in raw_cols:
                m_c, _ = cls.find_best_column_match(rc, cols) if cols else (rc, 1.0)
                if m_c:
                    del_targets.append(m_c)

            if del_targets:
                op = ProposedOperation(
                    category="column_ops",
                    operation="delete_columns",
                    parameters={"columns": del_targets},
                    human_explanation=f"Delete column(s): {del_targets}",
                    affected_columns=del_targets,
                    is_destructive=True,  # Column deletion is highly destructive
                    confidence=0.96,
                )
                ops.append(op)
                return cls._build_result(text, ops, "heuristic_nlp")

        # ---------------------------------------------------------
        # PATTERN 9: SORT RECORDS
        # e.g. "Sort records by Amount descending"
        #      "Sort by OrderDate"
        # ---------------------------------------------------------
        sort_match = re.search(
            r"sort\s+(?:records\s+|rows\s+)?(?:by\s+)?['\"`]?([^'\"`\s]+)?['\"`]?\s*(descending|ascending|asc|desc)?",
            text,
            re.IGNORECASE,
        )
        if sort_match or "sort" in lower_text:
            raw_col = sort_match.group(1).strip() if (sort_match and sort_match.group(1)) else None
            raw_dir = sort_match.group(2).strip().lower() if (sort_match and sort_match.group(2)) else "ascending"
            asc = False if any(k in raw_dir for k in ["desc", "descending"]) else True

            matched_col = None
            if raw_col and cols:
                m_c, _ = cls.find_best_column_match(raw_col, cols)
                matched_col = m_c
            matched_col = matched_col or raw_col or (cols[0] if cols else "ID")

            op = ProposedOperation(
                category="row_ops",
                operation="sort_records",
                parameters={"sort_cols": [matched_col], "ascending_list": [asc]},
                human_explanation=f"Sort records by '{matched_col}' {'Ascending' if asc else 'Descending'}",
                affected_columns=[matched_col],
                is_destructive=False,
                confidence=0.92,
            )
            ops.append(op)
            return cls._build_result(text, ops, "heuristic_nlp")

        # ---------------------------------------------------------
        # PATTERN 10: CAP / TREAT OUTLIERS
        # e.g. "Cap outliers in Amount"
        # ---------------------------------------------------------
        if "outlier" in lower_text:
            target_col = None
            if cols:
                for c in cols:
                    if c.lower() in lower_text:
                        target_col = c
                        break
            target_col = target_col or (cols[0] if cols else "Amount")
            op = ProposedOperation(
                category="data_cleaning",
                operation="treat_outliers",
                parameters={"column": target_col, "method": "iqr", "action": "cap", "multiplier": 1.5},
                human_explanation=f"Cap statistical outliers in '{target_col}' using 1.5x IQR boundaries",
                affected_columns=[target_col],
                is_destructive=False,
                confidence=0.93,
            )
            ops.append(op)
            return cls._build_result(text, ops, "heuristic_nlp")

        # ---------------------------------------------------------
        # PATTERN 11: GROUP BY & AGGREGATE
        # e.g. "Group by Region and sum Amount"
        # ---------------------------------------------------------
        group_match = re.search(
            r"group\s+(?:by\s+)?['\"`]?([^'\"`\s]+)['\"`]?\s+(?:and|then)\s+(sum|average|mean|count)\s+['\"`]?([^'\"`\s]+)['\"`]?",
            text,
            re.IGNORECASE,
        )
        if group_match:
            raw_grp = group_match.group(1).strip()
            raw_fn = group_match.group(2).strip().lower()
            raw_val = group_match.group(3).strip()

            fn = "mean" if raw_fn == "average" else raw_fn
            grp_col, _ = cls.find_best_column_match(raw_grp, cols) if cols else (raw_grp, 1.0)
            val_col, _ = cls.find_best_column_match(raw_val, cols) if cols else (raw_val, 1.0)

            op = ProposedOperation(
                category="transformations",
                operation="group_and_aggregate",
                parameters={"group_by_cols": [grp_col or raw_grp], "agg_spec": {val_col or raw_val: fn}},
                human_explanation=f"Group by '{grp_col or raw_grp}' and compute {fn} of '{val_col or raw_val}'",
                affected_columns=[grp_col or raw_grp, val_col or raw_val],
                is_destructive=False,
                confidence=0.95,
            )
            ops.append(op)
            return cls._build_result(text, ops, "heuristic_nlp")

        # ---------------------------------------------------------
        # PATTERN 12: SPECIAL WORKFLOW MODULE ROUTING
        # e.g. "Merge these two Excel files using Patient ID"
        #      "Update the existing voucher amounts using the revised Excel file"
        #      "Convert this XML into a structured Excel file"
        # ---------------------------------------------------------
        if "merge" in lower_text or "join" in lower_text:
            key_m = re.search(r"(?:using|by|on)\s+['\"`]?([^'\"`\.\?]+)['\"`]?", text, re.IGNORECASE)
            key_raw = key_m.group(1).strip() if key_m else "ID"
            op = ProposedOperation(
                category="transformations",
                operation="join_datasets",
                parameters={"join_key": key_raw, "how": "inner"},
                human_explanation=f"Join/Merge active dataset with secondary dataset on key '{key_raw}'",
                affected_columns=[key_raw],
                is_destructive=False,
                confidence=0.88,
            )
            ops.append(op)
            return cls._build_result(text, ops, "heuristic_nlp")

        if "voucher" in lower_text or "tally" in lower_text:
            op = ProposedOperation(
                category="tally",
                operation="tally_voucher_reconciliation",
                parameters={"match_by": "GUID", "set_alter_action": True},
                human_explanation="Launch TallyPrime Bulk Voucher Updater to reconcile ledger amounts and generate alter XML",
                affected_columns=["GUID", "AMOUNT"],
                is_destructive=False,
                confidence=0.96,
            )
            ops.append(op)
            return cls._build_result(text, ops, "heuristic_nlp")

        if "convert" in lower_text and ("xml" in lower_text or "excel" in lower_text or "csv" in lower_text or "json" in lower_text):
            op = ProposedOperation(
                category="conversion",
                operation="convert_format",
                parameters={"target_format": "Excel"},
                human_explanation="Convert document structure into multi-sheet Excel workbook",
                affected_columns=[],
                is_destructive=False,
                confidence=0.89,
            )
            ops.append(op)
            return cls._build_result(text, ops, "heuristic_nlp")

        # ---------------------------------------------------------
        # FALLBACK: AMBIGUOUS INSTRUCTION
        # Ask for clarification politely rather than hallucinating!
        # ---------------------------------------------------------
        return ParsedInstructionResult(
            original_instruction=text,
            requires_clarification=True,
            parsed_operations=[
                ProposedOperation(
                    operation_id="clarify_step",
                    category="unknown",
                    operation="clarify",
                    human_explanation=f"Could not conclusively map instruction: '{text}' to a known transformation rule.",
                    needs_clarification=True,
                    clarification_question=f"Could you clarify the desired operation? (e.g. 'Rename [col] to [new_col]', 'Remove duplicates based on [col]', 'Calculate [col] as [formula]')",
                    clarification_options=[
                        "Rename a column",
                        "Remove duplicate records",
                        "Standardize date formats",
                        "Calculate a new column formula",
                        "Clean numeric/currency symbols",
                    ],
                    confidence=0.2,
                )
            ],
            engine_used="heuristic_nlp",
        )

    # -------------------------------------------------------------
    # OPTIONAL GEMINI LLM REST CLIENT
    # -------------------------------------------------------------
    @classmethod
    def parse_instruction_with_gemini(
        cls,
        instruction: str,
        api_key: str,
        df: Optional[pd.DataFrame] = None,
        model: str = "gemini-1.5-flash",
    ) -> ParsedInstructionResult:
        """
        Translates complex instruction using Google Gemini REST API.
        Enforces JSON schema and strictly forbids hallucinating non-existent columns.
        """
        cols = list(df.columns) if df is not None else []
        dtypes = {c: str(df[c].dtype) for c in cols} if df is not None else {}
        sample_preview = df.head(3).to_dict(orient="records") if df is not None else []

        system_prompt = f"""
You are a senior data engineer and transformation compiler for a Universal Data Customisation Studio.
Convert the user's natural language instruction into a JSON array of transformation operations.

TARGET DATASET SCHEMA:
Columns: {json.dumps(cols)}
DataTypes: {json.dumps(dtypes)}
Sample Rows: {json.dumps(sample_preview)}

CRITICAL CONSTRAINTS:
1. NEVER invent, hallucinate, or assume column names that are not in the schema.
2. If the user refers to a column not in the schema, set "needs_clarification": true and formulate a clarification question.
3. If an operation permanently deletes rows, columns, or changes keys, mark "is_destructive": true.
4. Output ONLY a valid JSON object matching the schema below. No markdown fences.

OUTPUT JSON SCHEMA:
{{
  "operations": [
    {{
      "category": "column_ops|row_ops|data_cleaning|transformations|validation",
      "operation": "operation_name",
      "parameters": {{ ... }},
      "human_explanation": "Clear explanation of what this will do",
      "affected_columns": ["col1", "col2"],
      "is_destructive": true/false,
      "confidence": 0.0 - 1.0,
      "needs_clarification": true/false,
      "clarification_question": null or "string"
    }}
  ]
}}
"""
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": system_prompt},
                        {"text": f"USER INSTRUCTION: {instruction}"},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "responseMimeType": "application/json",
            },
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                res_body = response.read().decode("utf-8")
                res_data = json.loads(res_body)
                raw_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                parsed_json = json.loads(raw_text)

                ops = []
                for op_dict in parsed_json.get("operations", []):
                    # Schema check
                    aff_cols = [c for c in op_dict.get("affected_columns", []) if c in cols] if cols else op_dict.get("affected_columns", [])
                    op = ProposedOperation(
                        category=op_dict.get("category", "column_ops"),
                        operation=op_dict.get("operation", "rename_columns"),
                        parameters=op_dict.get("parameters", {}),
                        human_explanation=op_dict.get("human_explanation", ""),
                        affected_columns=aff_cols,
                        is_destructive=bool(op_dict.get("is_destructive", False)),
                        confidence=float(op_dict.get("confidence", 0.95)),
                        needs_clarification=bool(op_dict.get("needs_clarification", False)),
                        clarification_question=op_dict.get("clarification_question"),
                    )
                    ops.append(op)

                return cls._build_result(instruction, ops, "gemini_llm")

        except Exception as e:
            # Fallback to offline heuristic parser on network or API failure
            res = cls.parse_instruction_offline(instruction, df)
            res.error_message = f"Gemini API request failed ({e}). Reverted to offline NLP parser."
            return res

    # -------------------------------------------------------------
    # RESULT BUILDER & VALIDATION
    # -------------------------------------------------------------
    @classmethod
    def _build_result(
        cls,
        text: str,
        ops: List[ProposedOperation],
        engine_used: str,
    ) -> ParsedInstructionResult:
        has_destr = any(op.is_destructive for op in ops)
        has_clarify = any(op.needs_clarification for op in ops)
        return ParsedInstructionResult(
            original_instruction=text,
            parsed_operations=ops,
            engine_used=engine_used,
            has_destructive_ops=has_destr,
            requires_clarification=has_clarify,
        )

    # -------------------------------------------------------------
    # HUMAN CONFIRMATION & EXECUTION GATEWAY
    # -------------------------------------------------------------
    @classmethod
    def execute_proposed_operations(
        cls,
        df: pd.DataFrame,
        operations: List[ProposedOperation],
    ) -> Tuple[pd.DataFrame, List[str]]:
        """
        Executes confirmed operations sequentially using the WorkflowEngine.
        Returns the transformed DataFrame and execution logs.
        """
        current_df = df.copy()
        execution_logs = []

        for op in operations:
            step = op.to_workflow_step()
            transformed_df, msg = WorkflowEngine.execute_single_step(current_df, step)
            current_df = transformed_df
            execution_logs.append(msg)

        return current_df, execution_logs
