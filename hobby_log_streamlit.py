"""
Hobby Log Viewer — Streamlit edition.
Pulls live from Google Sheets on load (cached 5 min).

Run locally:
    pip install streamlit gspread google-auth
    streamlit run hobby_log_streamlit.py

Deploy to Streamlit Cloud:
    1. Push this file + requirements.txt to a GitHub repo.
    2. Go to share.streamlit.io → New app → connect the repo.
    3. Add your service account JSON as a secret (see DEPLOYMENT.md or README).
       In Streamlit Cloud secrets, paste:
           [gcp_service_account]
           type = "service_account"
           project_id = "..."
           private_key_id = "..."
           private_key = "..."
           client_email = "..."
           ... (all fields from your JSON key file)
"""

import json

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

# ── CONFIG ────────────────────────────────────────────────────────────────────
SERVICE_ACCOUNT_KEY = r"C:\Users\ndemorest\sheets-key.json"
SHEET_ID            = "1IHBjrv9P70t0kNCSnxzPdBbwJL0-NSyjei_9V4wCYKk"
TAB_NAME            = "The Hobby Log"

COLUMNS = [
    "purchase date", "post date", "platform", "vendor",
    "set", "inserts/parallel", "player (if single)", "numbered",
    "price", "shipping", "tax", "additional cost",
    "comments", "comp", "disposition",
]
MONEY_COLS = {"price", "shipping", "tax", "additional cost", "comp"}
COST_COLS  = ["price", "shipping", "tax", "additional cost"]
FILTER_COLS = ["platform", "vendor", "set", "player (if single)", "disposition"]

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
# ──────────────────────────────────────────────────────────────────────────────


def _get_credentials():
    """Use Streamlit secrets when deployed; fall back to local JSON file."""
    try:
        info = dict(st.secrets["gcp_service_account"])
        return Credentials.from_service_account_info(info, scopes=SCOPES)
    except (KeyError, Exception):
        pass
    return Credentials.from_service_account_file(SERVICE_ACCOUNT_KEY, scopes=SCOPES)


@st.cache_data(ttl=300, show_spinner=False)
def load_data() -> pd.DataFrame:
    creds = _get_credentials()
    gc    = gspread.authorize(creds)
    ws    = gc.open_by_key(SHEET_ID).worksheet(TAB_NAME)
    all_values = ws.get_all_values()
    if not all_values:
        return pd.DataFrame()

    headers = [h.strip().lower() for h in all_values[0]]
    col_idx = {col: headers.index(col) for col in COLUMNS if col in headers}

    rows = []
    for raw in all_values[1:]:
        record = {col: (raw[idx].strip() if idx < len(raw) else "")
                  for col, idx in col_idx.items()}
        if any(v for v in record.values()):
            rows.append(record)

    present_cols = [c for c in COLUMNS if c in col_idx]
    return pd.DataFrame(rows, columns=present_cols)


def _col_total(series) -> float:
    """Sum a column of money strings like '$12.50', ignoring blanks."""
    numeric = pd.to_numeric(
        series.str.replace(r"[$,]", "", regex=True).str.strip(),
        errors="coerce",
    )
    return float(numeric.sum())


def _check_password():
    """Stop script execution if the user has not entered the correct password."""
    if st.session_state.get("authenticated"):
        return

    st.title("🃏 Hobby Log")
    pw = st.text_input("Password", type="password")
    if pw:
        try:
            correct = st.secrets["app_password"]
        except KeyError:
            st.error(
                f"app_password not found. Top-level secret keys visible: "
                f"{list(st.secrets.keys())}"
            )
            st.stop()
        if pw == correct:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()


def main():
    st.set_page_config(page_title="Hobby Log", page_icon="🃏", layout="wide")

    _check_password()

    # ── Header ────────────────────────────────────────────────────────────────
    hdr, btn_col = st.columns([8, 1])
    hdr.title("🃏 Hobby Log")
    if btn_col.button("🔄 Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # ── Load data ─────────────────────────────────────────────────────────────
    with st.spinner("Loading from Google Sheets…"):
        try:
            df = load_data()
        except FileNotFoundError:
            st.error(
                f"Service account key not found at `{SERVICE_ACCOUNT_KEY}`. "
                "Update `SERVICE_ACCOUNT_KEY` in the script."
            )
            return
        except Exception as e:
            st.error(f"Failed to load data: {e}")
            return

    if df.empty:
        st.warning("No data returned from the sheet.")
        return

    # ── Search ────────────────────────────────────────────────────────────────
    search = st.text_input("🔍 Search", placeholder="Search across all fields…")

    # ── Filters ───────────────────────────────────────────────────────────────
    with st.expander("Filters", expanded=False):
        filter_cols_layout = st.columns(len(FILTER_COLS))
        filter_selections: dict[str, str] = {}
        for i, col in enumerate(FILTER_COLS):
            if col not in df.columns:
                continue
            options = ["All"] + sorted(
                {v for v in df[col].tolist() if v}, key=str.lower
            )
            filter_selections[col] = filter_cols_layout[i].selectbox(
                col.title(), options, key=f"f_{col}"
            )

    # ── Apply filters ─────────────────────────────────────────────────────────
    filtered = df.copy()

    for col, val in filter_selections.items():
        if val != "All":
            filtered = filtered[filtered[col] == val]

    if search:
        q = search.lower()
        mask = filtered.apply(
            lambda row: any(q in str(v).lower() for v in row), axis=1
        )
        filtered = filtered[mask]

    # ── Metrics ───────────────────────────────────────────────────────────────
    total_spend = sum(
        _col_total(filtered[col])
        for col in COST_COLS
        if col in filtered.columns
    )

    m1, m2 = st.columns(2)
    m1.metric("Purchases", f"{len(filtered):,}")
    m2.metric("Total Spend", f"${total_spend:,.2f}")

    # ── Table ─────────────────────────────────────────────────────────────────
    st.dataframe(
        filtered,
        use_container_width=True,
        hide_index=True,
        column_config={
            col: st.column_config.TextColumn(col.title())
            for col in filtered.columns
        },
    )


if __name__ == "__main__":
    main()
