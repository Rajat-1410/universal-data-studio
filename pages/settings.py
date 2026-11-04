"""
Settings & Workspace Preferences Page
System diagnostics, parsing preferences, display parameters, and environment information.
"""
import sys
import platform
import streamlit as st
import pandas as pd

from config import APP_TITLE, APP_VERSION, AUTHOR
from utils.ui_components import (
    inject_custom_css,
    render_page_header,
    render_metric_card,
)
from utils.session_manager import SessionManager


def show():
    inject_custom_css()
    SessionManager.init_session()

    render_page_header(
        title="Settings & System Diagnostics",
        description="Configure runtime preferences, inspection thresholds, and inspect runtime environment telemetry.",
        badge="Phase 1 Active",
    )

    settings = st.session_state.get("app_settings", {})

    st.markdown("### ⚙️ Workspace Configuration")

    c1, c2 = st.columns(2)

    with c1:
        with st.container(border=True):
            st.markdown("##### 🎛️ Preview & Profiling Settings")
            max_preview = st.slider(
                "Default Preview Rows:",
                min_value=10,
                max_value=200,
                value=settings.get("max_preview_rows", 25),
                step=5,
                key="set_max_preview",
            )
            settings["max_preview_rows"] = max_preview

            auto_detect = st.checkbox(
                "Automatically detect headers in Excel & CSV",
                value=settings.get("auto_detect_headers", True),
                key="set_auto_detect",
            )
            settings["auto_detect_headers"] = auto_detect

            show_health = st.checkbox(
                "Display Data Health Index on Inspection",
                value=settings.get("show_health_score", True),
                key="set_show_health",
            )
            settings["show_health_score"] = show_health

    with c2:
        with st.container(border=True):
            st.markdown("##### 🧹 In-Memory Session Maintenance")
            st.caption("Resetting the session frees up memory and clears all uploaded files and cached dataframes.")

            files = st.session_state.get("files", {})
            st.write(f"- Datasets in Memory: `{len(files)}`")

            if st.button("🗑️ Clear Workspace & Reset Session", type="secondary", key="set_btn_reset"):
                SessionManager.clear_all()
                st.success("Session state cleared successfully.")
                st.rerun()

    st.markdown("---")

    # AI Configuration (Phase 8)
    st.markdown("### 🤖 Natural Language & AI Copilot Settings")

    ai_c1, ai_c2 = st.columns(2)
    with ai_c1:
        with st.container(border=True):
            st.markdown("##### 🧠 AI Engine Selection")
            ai_prov = st.radio(
                "Selected Natural Language Engine:",
                options=["offline", "gemini"],
                format_func=lambda x: "Universal Semantic NLP (Offline, 0 API key required)" if x == "offline" else "Google Gemini API (Cloud LLM)",
                index=0 if settings.get("ai_provider", "offline") == "offline" else 1,
                key="set_ai_provider_radio",
            )
            settings["ai_provider"] = ai_prov

            if ai_prov == "offline":
                st.caption(
                    "✅ **Offline Heuristic NLP:** Runs entirely locally on your machine with 0 external network calls. "
                    "Supports regex grammar intent parsing, fuzzy column schema verification, and instant latency."
                )
            else:
                st.caption(
                    "🌐 **Google Gemini LLM:** Uses Google Gemini API (REST) for understanding free-form open-ended prompts."
                )

    with ai_c2:
        with st.container(border=True):
            st.markdown("##### 🔑 Google Gemini API Credentials (Optional)")
            g_key = st.text_input(
                "Gemini API Key:",
                value=settings.get("gemini_api_key", ""),
                type="password",
                help="Optional. Leave blank to use built-in offline NLP engine.",
                key="set_gemini_api_key_input",
            )
            settings["gemini_api_key"] = g_key

            g_model = st.selectbox(
                "Gemini Model:",
                options=["gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"],
                index=0,
                key="set_gemini_model_sel",
            )
            settings["gemini_model"] = g_model

            if g_key:
                st.success("API key stored in current session.")
            else:
                st.info("No API key provided. System operates in 100% offline mode.")

    st.markdown("---")

    # Environment Telemetry
    st.markdown("### 💻 Runtime Environment Telemetry")

    t1, t2, t3, t4 = st.columns(4)
    with t1:
        render_metric_card("Python Version", sys.version.split(" ")[0], platform.system(), t1)
    with t2:
        render_metric_card("Streamlit Version", st.__version__, "UI Framework", t2)
    with t3:
        render_metric_card("Pandas Version", pd.__version__, "Data Engine", t3)
    with t4:
        render_metric_card("App Release", APP_VERSION, "Universal Studio", t4)


if __name__ == "__main__":
    show()
