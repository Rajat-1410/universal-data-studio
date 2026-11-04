"""
Universal Data Customisation & Automation Studio
Main Application Entry Point with Modern Multi-Page Navigation
"""
import streamlit as st
from config import APP_TITLE, APP_VERSION
from utils.session_manager import SessionManager
from utils.ui_components import inject_custom_css

# Configure global page parameters
st.set_page_config(
    page_title=APP_TITLE,
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Initialize Session State
SessionManager.init_session()
inject_custom_css()

# Define sidebar navigation pages corresponding to all 12 requested architecture sections
pages = {
    "Overview": [
        st.Page("pages/dashboard.py", title="1. Dashboard", icon=":material/dashboard:"),
    ],
    "Ingestion & Profiling": [
        st.Page("pages/upload.py", title="2. Upload Files", icon=":material/upload_file:"),
        st.Page("pages/inspector.py", title="3. File Inspector", icon=":material/troubleshoot:"),
    ],
    "Customisation & Matching": [
        st.Page("pages/customisation.py", title="4. Data Customisation", icon=":material/tune:"),
        st.Page("pages/matching.py", title="5. Record Matching", icon=":material/compare_arrows:"),
    ],
    "Engines & Modules": [
        st.Page("pages/xml_studio.py", title="6. XML Studio", icon=":material/code:"),
        st.Page("pages/tally_updater.py", title="7. TallyPrime Updater", icon=":material/receipt_long:"),
        st.Page("pages/workflow_builder.py", title="8. Workflow Builder", icon=":material/account_tree:"),
    ],
    "Quality & Management": [
        st.Page("pages/validation.py", title="9. Validation Centre", icon=":material/verified:"),
        st.Page("pages/export.py", title="10. Export Centre", icon=":material/download:"),
        st.Page("pages/saved_workflows.py", title="11. Saved Workflows", icon=":material/bookmarks:"),
        st.Page("pages/settings.py", title="12. Settings", icon=":material/settings:"),
    ],
}

# Sidebar Branding & Context
with st.sidebar:
    st.markdown(
        f"""
        <div style="padding: 10px 0 16px 0; border-bottom: 1px solid rgba(255,255,255,0.1); margin-bottom: 12px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 1.5rem;">⚡</span>
                <span style="font-weight: 700; font-size: 1.05rem; color: #F8FAFC; letter-spacing: -0.02em;">Universal Studio</span>
            </div>
            <div style="font-size: 0.72rem; color: #60A5FA; margin-top: 2px;">{APP_VERSION}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Active dataset quick badge in sidebar
    active_file = SessionManager.get_active_file()
    if active_file:
        fmt_badge = f"badge-{active_file['format'].lower()}"
        st.markdown(
            f"""
            <div style="background: rgba(30, 41, 59, 0.6); border: 1px solid rgba(255,255,255,0.08); border-radius: 8px; padding: 10px; margin-bottom: 12px;">
                <div style="font-size: 0.72rem; text-transform: uppercase; color: #94A3B8; font-weight: 600;">Active Context</div>
                <div style="font-weight: 600; font-size: 0.85rem; color: #F8FAFC; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 2px;">
                    {active_file['filename']}
                </div>
                <div style="margin-top: 6px;">
                    <span class="badge {fmt_badge}">{active_file['format'].upper()}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# Run modern Streamlit router
pg = st.navigation(pages)
pg.run()
