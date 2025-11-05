import hmac
import streamlit as st

PRIMARY = "#4A6B4C"
BG = "#F5F1E8"

def _get_secret_password() -> str:
    try:
        return st.secrets["auth"]["password"]
    except Exception:
        return ""

def _check_password() -> bool:
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if st.session_state.authenticated:
        return True

    with st.sidebar:
        st.markdown("### 🔒 FinSight AI — Sign In")
        pw_input = st.text_input("Password", type="password",
                                 help="Enter the access password to view the demo")
        if st.button("Unlock"):
            expected = _get_secret_password()
            if expected and hmac.compare_digest(pw_input, expected):
                st.session_state.authenticated = True
                st.success("Access granted.")
                return True
            st.error("Incorrect password. Please try again.")
            st.stop()

    st.markdown(
        f"""
        <div style="padding:2rem; background:{BG};
                    border:1px solid #ddd; border-radius:12px; text-align:center;">
            <h2 style="color:{PRIMARY}; margin-bottom:0.5rem;">FinSight AI — Variance Dashboard</h2>
            <p style="color:#2D2D2D; margin:0.25rem 0 1rem 0;">This demo is password protected.</p>
            <p style="color:#5A5A5A;">Use the sidebar to enter the password.</p>
        </div>
        """,
        unsafe_allow_html=True
    )
    st.stop()

def require_password():
    """Call this at the very top of the main app file."""
    if not _check_password():
        st.stop()
    with st.sidebar:
        if st.button("Log out"):
            st.session_state.authenticated = False
            st.rerun()
