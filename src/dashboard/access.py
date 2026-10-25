import streamlit as st

from security.auth import check_credentials, password_configured
from security.limits import Limits

USER_KEY = "user"

def minutes(seconds: int) -> int:
    return max(1, -(-seconds // 60))

def session_allowed(limits: Limits, ip: str) -> bool:
    if "session_allowed" not in st.session_state:
        st.session_state["session_allowed"] = limits.sessions.hit(ip)
    allowed, wait = st.session_state["session_allowed"]
    if not allowed:
        st.error(f"Too many requests from your address. Try again in {minutes(wait)} min.")
    return allowed

def login_gate(limits: Limits, ip: str) -> bool:
    if st.session_state.get(USER_KEY):
        return True

    _, middle, _ = st.columns([1, 1.2, 1])
    with middle:
        st.title("Bookstore Sales")
        if not password_configured():
            st.error("Login is not configured on the server (APP_PASSWORD_HASH is missing).")
            return False
        allowed, wait = limits.login_failures.check(ip)
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", width="stretch", disabled=not allowed)
        if not allowed:
            st.error(f"Too many failed attempts. Try again in {minutes(wait)} min.")
        elif submitted:
            if check_credentials(username, password):
                limits.login_failures.reset(ip)
                st.session_state[USER_KEY] = username.strip()
                st.rerun()
            limits.login_failures.hit(ip)
            st.error("Wrong username or password.")
    return False

def logout_button() -> None:
    with st.sidebar:
        st.caption(f"Signed in as **{st.session_state[USER_KEY]}**")
        if st.button("Log out", icon=":material/logout:"):
            st.session_state.clear()
            st.rerun()
