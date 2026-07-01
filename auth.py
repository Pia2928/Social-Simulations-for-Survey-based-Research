"""
Single-user authentication with a hardcoded password.
No secrets.toml, no external auth service required.

Public API kept identical to the multi-user auth.py so app.py, db.py, and
agent_library_v2.py don't need any changes — DISPLAY_NAMES/USER_COLORS now
contain exactly one entry, and owner_badge_html still works for the "created
by" badges even though there's only ever one possible owner.
"""

from __future__ import annotations

import streamlit as st

# ─── Single user identity ──────────────────────────────────────────────────────
# Change these values to whatever you want shown in the app.

USERNAME     = "me"
DISPLAY_NAME = "My Account"
USER_COLOR   = "#7C3AED"   # purple — used for the "created by" badge

# ─── Password ───────────────────────────────────────────────────────────────────
# Hardcoded here rather than in .streamlit/secrets.toml. Fine for a small,
# local, single-user research tool — just be aware that anyone with read
# access to this file (including anyone you share the repo with) can see it
# in plaintext. Set to "" to disable the login screen entirely.

APP_PASSWORD = "Social Simulations"

DISPLAY_NAMES: dict[str, str] = {USERNAME: DISPLAY_NAME}
USER_COLORS:   dict[str, str] = {USERNAME: USER_COLOR}


# ─── Public API ───────────────────────────────────────────────────────────────

def require_login() -> None:
    """
    Show a password screen and halt execution until unlocked.

    If APP_PASSWORD is empty, login is skipped entirely and the app opens
    directly — useful for purely local/offline use where a password gate
    is unnecessary friction.
    """
    if not APP_PASSWORD:
        st.session_state.setdefault("logged_in", True)
        st.session_state.setdefault("username", USERNAME)
        st.session_state.setdefault("display_name", DISPLAY_NAME)
        return

    if not st.session_state.get("logged_in"):
        _login_screen()
        st.stop()


def current_user() -> str:
    """Return the single user's username."""
    return st.session_state.get("username", USERNAME)


def current_display_name() -> str:
    """Return the single user's display name."""
    return st.session_state.get("display_name", DISPLAY_NAME)


def owner_badge_html(username: str) -> str:
    """Return an HTML pill badge, safe for st.markdown(unsafe_allow_html=True)."""
    color = USER_COLORS.get(username, "#6B7280")
    name  = DISPLAY_NAMES.get(username, username or DISPLAY_NAME)
    return (
        f'<span style="background:{color};color:#fff;padding:2px 10px;'
        f'border-radius:999px;font-size:0.72rem;font-weight:700;'
        f'letter-spacing:0.03em;white-space:nowrap">{name}</span>'
    )


# ─── Private helpers ──────────────────────────────────────────────────────────

def _login_screen() -> None:
    st.markdown("<br><br>", unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 1.2, 1])
    with mid:
        st.markdown("## 👤 Social Simulation Agent Builder")
        st.caption("Research tool for synthetic human agent simulation")
        st.divider()
        password = st.text_input("Password", type="password", key="_login_pass")
        if st.button("Sign in", type="primary", use_container_width=True, key="_login_btn"):
            _check(password)
        st.markdown("<br>", unsafe_allow_html=True)


def _check(password: str) -> None:
    if password == APP_PASSWORD:
        st.session_state.update(
            logged_in=True,
            username=USERNAME,
            display_name=DISPLAY_NAME,
        )
        st.rerun()
    else:
        st.error("Incorrect password.")
