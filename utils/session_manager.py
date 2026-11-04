"""
Session State Manager
Maintains uploaded files, active file context, immutable original copies,
working datasets, undo/redo snapshot history, and workspace settings.
"""
import uuid
import copy
from typing import Dict, Any, Optional, List, Tuple
import pandas as pd
import streamlit as st

from utils.format_detector import FormatDetector
from core.file_reader import FileReaderRegistry, UniversalInspector


class SessionManager:
    """Centralized manager for Streamlit session state and undo/redo history."""

    SESSION_KEYS = {
        "files": {},  # {file_id: FileRecord}
        "active_file_id": None,
        "active_sheet": None,
        "working_df": None,
        "original_df": None,
        "df_snapshots": [],  # List of deep-copied DataFrames for undo/redo
        "change_history": [],  # List of operation records
        "history_index": -1,
        "workflow_steps": [],
        "validation_errors": [],
        "app_settings": {
            "max_preview_rows": 25,
            "show_health_score": True,
            "auto_detect_headers": True,
        },
    }

    @classmethod
    def init_session(cls):
        """Initializes all required session state variables if not already present."""
        for key, default_val in cls.SESSION_KEYS.items():
            if key not in st.session_state:
                st.session_state[key] = copy.deepcopy(default_val)

    @classmethod
    def add_uploaded_file(cls, filename: str, raw_bytes: bytes) -> str:
        """Parses and stores an uploaded file, triggering universal inspection."""
        cls.init_session()

        file_id = str(uuid.uuid4())[:8]
        detector_info = FormatDetector.detect_format(filename, raw_bytes)
        reader = FileReaderRegistry.get_reader(filename, raw_bytes)

        # Execute parse
        try:
            parsed_data = reader.read(filename, raw_bytes)
        except Exception as e:
            parsed_data = {
                "format": detector_info.get("format", "unknown"),
                "error": str(e),
                "active_df": pd.DataFrame(),
                "data_frames": {},
            }

        active_df = parsed_data.get("active_df")
        inspection = None
        if active_df is not None and isinstance(active_df, pd.DataFrame):
            inspection = UniversalInspector.inspect_dataframe(
                active_df,
                filename=filename,
                format_type=detector_info.get("format", "unknown"),
            )

        file_record = {
            "id": file_id,
            "file_id": file_id,
            "filename": filename,
            "format_info": detector_info,
            "format": detector_info.get("format", "unknown"),
            "size_bytes": len(raw_bytes),
            "raw_bytes": raw_bytes,
            "parsed_data": parsed_data,
            "inspection": inspection,
            "active_sheet": parsed_data.get("active_sheet"),
        }

        st.session_state.files[file_id] = file_record

        # If no active file is set, make this the active file
        if st.session_state.active_file_id is None or len(st.session_state.files) == 1:
            cls.set_active_file(file_id)

        return file_id

    @classmethod
    def set_active_file(cls, file_id: str):
        """Sets the active file and initializes working copy and snapshot history without mutating original."""
        cls.init_session()
        if file_id in st.session_state.files:
            st.session_state.active_file_id = file_id
            record = st.session_state.files[file_id]

            parsed = record.get("parsed_data", {})
            df = parsed.get("active_df")

            if df is not None and isinstance(df, pd.DataFrame):
                # Always create clean deep copy for working state
                st.session_state.original_df = df.copy(deep=True)
                st.session_state.working_df = df.copy(deep=True)
                st.session_state.active_sheet = parsed.get("active_sheet")
                st.session_state.df_snapshots = [df.copy(deep=True)]
            else:
                st.session_state.original_df = None
                st.session_state.working_df = None
                st.session_state.df_snapshots = []

            # Reset history for current file
            st.session_state.change_history = [
                {
                    "step": 0,
                    "action": "File Loaded",
                    "description": f"Loaded '{record['filename']}' ({record['format'].upper()})",
                    "rows": len(st.session_state.working_df) if st.session_state.working_df is not None else 0,
                    "columns": len(st.session_state.working_df.columns) if st.session_state.working_df is not None else 0,
                }
            ]
            st.session_state.history_index = 0

    @classmethod
    def switch_excel_sheet(cls, sheet_name: str):
        """Switches worksheet for an active Excel file."""
        cls.init_session()
        active_id = st.session_state.active_file_id
        if not active_id or active_id not in st.session_state.files:
            return

        record = st.session_state.files[active_id]
        if record.get("format") != "excel":
            return

        reader = FileReaderRegistry.get_reader(record["filename"], record["raw_bytes"])
        parsed = reader.read(record["filename"], record["raw_bytes"], sheet_name=sheet_name)
        record["parsed_data"] = parsed
        record["active_sheet"] = sheet_name

        df = parsed.get("active_df")
        if df is not None:
            record["inspection"] = UniversalInspector.inspect_dataframe(
                df, filename=record["filename"], format_type="excel"
            )
            st.session_state.original_df = df.copy(deep=True)
            st.session_state.working_df = df.copy(deep=True)
            st.session_state.df_snapshots = [df.copy(deep=True)]
            st.session_state.active_sheet = sheet_name
            st.session_state.change_history = [
                {
                    "step": 0,
                    "action": "Worksheet Switched",
                    "description": f"Switched to sheet '{sheet_name}' in '{record['filename']}'",
                    "rows": len(df),
                    "columns": len(df.columns),
                }
            ]
            st.session_state.history_index = 0

    @classmethod
    def get_active_file(cls) -> Optional[Dict[str, Any]]:
        """Returns the dictionary record of the currently active file."""
        cls.init_session()
        active_id = st.session_state.active_file_id
        if active_id and active_id in st.session_state.files:
            return st.session_state.files[active_id]
        return None

    @classmethod
    def get_all_files(cls) -> Dict[str, Dict[str, Any]]:
        """Returns all uploaded file records in the current session."""
        cls.init_session()
        return st.session_state.files

    @classmethod
    def get_active_df(cls) -> Optional[pd.DataFrame]:
        """Returns the current working DataFrame."""
        cls.init_session()
        return st.session_state.working_df

    @classmethod
    def update_working_df(cls, new_df: pd.DataFrame, action_name: str, description: str):
        """Updates the working DataFrame, logs to change history, and creates a history snapshot."""
        cls.init_session()
        idx = st.session_state.history_index

        # If user did undo operations previously, slice away forward redo history
        if idx >= 0 and idx < len(st.session_state.df_snapshots) - 1:
            st.session_state.df_snapshots = st.session_state.df_snapshots[: idx + 1]
            st.session_state.change_history = st.session_state.change_history[: idx + 1]

        # Append new snapshot
        st.session_state.df_snapshots.append(new_df.copy(deep=True))
        st.session_state.working_df = new_df.copy(deep=True)

        # Update active file inspection dynamically
        active_file = cls.get_active_file()
        if active_file:
            active_file["inspection"] = UniversalInspector.inspect_dataframe(
                new_df,
                filename=active_file["filename"],
                format_type=active_file["format"],
            )

        step_record = {
            "step": len(st.session_state.change_history),
            "action": action_name,
            "description": description,
            "rows": len(new_df),
            "columns": len(new_df.columns),
        }
        st.session_state.change_history.append(step_record)
        st.session_state.history_index = len(st.session_state.df_snapshots) - 1

    @classmethod
    def can_undo(cls) -> bool:
        """Returns True if there is a previous snapshot available to undo."""
        cls.init_session()
        return st.session_state.history_index > 0

    @classmethod
    def can_redo(cls) -> bool:
        """Returns True if there is a forward snapshot available to redo."""
        cls.init_session()
        return st.session_state.history_index < len(st.session_state.df_snapshots) - 1

    @classmethod
    def undo(cls) -> Tuple[bool, str]:
        """Reverts to the immediately preceding DataFrame snapshot."""
        cls.init_session()
        if not cls.can_undo():
            return False, "No previous actions to undo."

        st.session_state.history_index -= 1
        target_df = st.session_state.df_snapshots[st.session_state.history_index].copy(deep=True)
        st.session_state.working_df = target_df

        active_file = cls.get_active_file()
        if active_file:
            active_file["inspection"] = UniversalInspector.inspect_dataframe(
                target_df,
                filename=active_file["filename"],
                format_type=active_file["format"],
            )

        curr_step = st.session_state.change_history[st.session_state.history_index]
        return True, f"Undid last action. Reverted to Step {curr_step['step']}: {curr_step['action']}"

    @classmethod
    def redo(cls) -> Tuple[bool, str]:
        """Restores the forward DataFrame snapshot."""
        cls.init_session()
        if not cls.can_redo():
            return False, "No forward actions to redo."

        st.session_state.history_index += 1
        target_df = st.session_state.df_snapshots[st.session_state.history_index].copy(deep=True)
        st.session_state.working_df = target_df

        active_file = cls.get_active_file()
        if active_file:
            active_file["inspection"] = UniversalInspector.inspect_dataframe(
                target_df,
                filename=active_file["filename"],
                format_type=active_file["format"],
            )

        curr_step = st.session_state.change_history[st.session_state.history_index]
        return True, f"Redid action. Advanced to Step {curr_step['step']}: {curr_step['action']}"

    @classmethod
    def get_change_history(cls) -> List[Dict[str, Any]]:
        """Returns the list of transformation history steps recorded in session."""
        cls.init_session()
        return st.session_state.get("change_history", [])

    @classmethod
    def reset_working_df(cls):
        """Resets the working DataFrame back to the pristine original dataset."""
        cls.init_session()
        if st.session_state.original_df is not None:
            reset_df = st.session_state.original_df.copy(deep=True)
            cls.update_working_df(reset_df, "Reset Dataset", "Reverted working dataset to pristine baseline copy")

    @classmethod
    def remove_file(cls, file_id: str):
        """Removes a file from the session."""
        cls.init_session()
        if file_id in st.session_state.files:
            del st.session_state.files[file_id]
            if st.session_state.active_file_id == file_id:
                if st.session_state.files:
                    first_key = list(st.session_state.files.keys())[0]
                    cls.set_active_file(first_key)
                else:
                    st.session_state.active_file_id = None
                    st.session_state.working_df = None
                    st.session_state.original_df = None
                    st.session_state.df_snapshots = []
                    st.session_state.change_history = []
                    st.session_state.history_index = -1

    @classmethod
    def clear_all(cls):
        """Clears all session state files and resets workspace."""
        for key, val in cls.SESSION_KEYS.items():
            st.session_state[key] = copy.deepcopy(val)
