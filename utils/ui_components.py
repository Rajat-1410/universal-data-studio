"""
Enterprise UI Components and Custom Styling
Provides clean aesthetics, metric cards, status pills, health score gauges,
and active file contextual selectors.
"""
import streamlit as st
import pandas as pd
from typing import Optional, Dict, Any

from utils.helpers import format_bytes


def inject_custom_css():
    """Injects high-end, responsive enterprise dashboard CSS and browser compatibility polyfills."""
    try:
        if hasattr(st, "html"):
            st.html(
                """
                <script>
                (function() {
                    if (typeof Array.prototype.toSorted !== 'function') {
                        Array.prototype.toSorted = function(compareFn) {
                            var copy = this.slice();
                            return copy.sort(compareFn);
                        };
                    }
                    if (typeof Array.prototype.toReversed !== 'function') {
                        Array.prototype.toReversed = function() {
                            var copy = this.slice();
                            return copy.reverse();
                        };
                    }
                    if (typeof Array.prototype.toSpliced !== 'function') {
                        Array.prototype.toSpliced = function() {
                            var copy = this.slice();
                            Array.prototype.splice.apply(copy, arguments);
                            return copy;
                        };
                    }
                    if (typeof Array.prototype.with !== 'function') {
                        Array.prototype.with = function(index, value) {
                            var copy = this.slice();
                            copy[index] = value;
                            return copy;
                        };
                    }
                })();
                </script>
                """,
                unsafe_allow_javascript=True,
            )
    except Exception:
        pass

    st.markdown(
        """
        <style>
        /* Base typography and smooth layout */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

        html, body, [class*="css"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        }

        code, pre {
            font-family: 'JetBrains+Mono', monospace !important;
        }

        /* Metric cards */
        .metric-card {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 16px 20px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
            transition: transform 0.2s ease, border-color 0.2s ease;
        }
        .metric-card:hover {
            border-color: rgba(59, 130, 246, 0.4);
            transform: translateY(-2px);
        }
        .metric-label {
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #94A3B8;
            margin-bottom: 6px;
            font-weight: 600;
        }
        .metric-value {
            font-size: 1.6rem;
            font-weight: 700;
            color: #F8FAFC;
            letter-spacing: -0.02em;
        }
        .metric-sub {
            font-size: 0.75rem;
            color: #64748B;
            margin-top: 4px;
        }

        /* Pills & Badges */
        .badge {
            display: inline-flex;
            align-items: center;
            padding: 3px 10px;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.02em;
        }
        .badge-excel { background-color: rgba(16, 185, 129, 0.2); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.4); }
        .badge-csv { background-color: rgba(59, 130, 246, 0.2); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.4); }
        .badge-xml { background-color: rgba(245, 158, 11, 0.2); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.4); }
        .badge-json { background-color: rgba(168, 85, 247, 0.2); color: #C084FC; border: 1px solid rgba(168, 85, 247, 0.4); }
        .badge-txt { background-color: rgba(148, 163, 184, 0.2); color: #CBD5E1; border: 1px solid rgba(148, 163, 184, 0.4); }
        .badge-zip { background-color: rgba(236, 72, 153, 0.2); color: #F472B6; border: 1px solid rgba(236, 72, 153, 0.4); }
        .badge-warning { background-color: rgba(239, 68, 68, 0.2); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.4); }
        .badge-clean { background-color: rgba(16, 185, 129, 0.15); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.3); }

        /* Banner Container */
        .page-header {
            margin-bottom: 24px;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        }
        .page-title {
            font-size: 1.75rem;
            font-weight: 700;
            color: #F8FAFC;
            letter-spacing: -0.02em;
            margin: 0;
        }
        .page-desc {
            font-size: 0.95rem;
            color: #94A3B8;
            margin-top: 4px;
        }

        /* Callout Box */
        .callout-info {
            background: rgba(37, 99, 235, 0.1);
            border-left: 4px solid #3B82F6;
            border-radius: 6px;
            padding: 12px 16px;
            margin: 12px 0;
            color: #CBD5E1;
            font-size: 0.88rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_page_header(title: str, description: str, badge: Optional[str] = None):
    """Renders a standardized executive page header."""
    badge_html = ""
    if badge:
        badge_html = f"<span class='badge badge-csv' style='margin-left: 10px; vertical-align: middle;'>{badge}</span>"

    st.markdown(
        f"""
        <div class="page-header">
            <h1 class="page-title">{title} {badge_html}</h1>
            <p class="page-desc">{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: str, sub: str = "", col=None, color: Optional[str] = None):
    """Renders a styled dark-glass metric card with flexible container and accent color support."""
    accent_color = "#38BDF8"
    target = st

    if col is not None:
        if isinstance(col, str):
            accent_color = col
        elif hasattr(col, "markdown"):
            target = col

    if color:
        accent_color = color

    target.markdown(
        f"""
        <div class="metric-card" style="border-left: 3px solid {accent_color};">
            <div class="metric-label">{label}</div>
            <div class="metric-value" style="color: #F8FAFC;">{value}</div>
            <div class="metric-sub" style="color: #94A3B8;">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_active_file_banner():
    """Renders a sticky contextual banner indicating the current active file and its format."""
    files = st.session_state.get("files", {})
    active_id = st.session_state.get("active_file_id")

    if not files or not active_id or active_id not in files:
        st.info("ℹ️ No file currently loaded. Please upload a dataset in **Upload Files** or inspect samples to get started.")
        return None

    active_file = files[active_id]
    fname = active_file["filename"]
    fmt = active_file["format"].upper()
    size = format_bytes(active_file["size_bytes"])

    # Determine badge style
    badge_class = f"badge-{active_file['format'].lower()}"

    cols = st.columns([4, 2, 2])
    with cols[0]:
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 10px; padding: 8px 12px; background: rgba(30, 41, 59, 0.5); border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.08);">
                <span style="font-size: 1.2rem;">📁</span>
                <div>
                    <div style="font-weight: 600; font-size: 0.9rem; color: #F8FAFC;">Active: {fname}</div>
                    <div style="font-size: 0.75rem; color: #94A3B8;">Size: {size}</div>
                </div>
                <span class="badge {badge_class}">{fmt}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with cols[1]:
        # Dropdown to switch active file if multiple files uploaded
        if len(files) > 1:
            file_options = {fid: f["filename"] for fid, f in files.items()}
            selected_fid = st.selectbox(
                "Switch Active File:",
                options=list(file_options.keys()),
                format_func=lambda x: file_options[x],
                index=list(file_options.keys()).index(active_id),
                key="_global_active_file_switch",
                label_visibility="collapsed",
            )
            if selected_fid != active_id:
                from utils.session_manager import SessionManager
                SessionManager.set_active_file(selected_fid)
                st.rerun()

    with cols[2]:
        # If Excel file, sheet switcher
        if active_file.get("format") == "excel":
            parsed = active_file.get("parsed_data", {})
            sheets = parsed.get("sheets", [])
            active_sheet = st.session_state.get("active_sheet") or (sheets[0] if sheets else None)
            if sheets and len(sheets) > 1:
                selected_sheet = st.selectbox(
                    "Worksheet:",
                    options=sheets,
                    index=sheets.index(active_sheet) if active_sheet in sheets else 0,
                    key="_global_sheet_switch",
                    label_visibility="collapsed",
                )
                if selected_sheet != active_sheet:
                    from utils.session_manager import SessionManager
                    SessionManager.switch_excel_sheet(selected_sheet)
                    st.rerun()

    st.write("")
    return active_file
