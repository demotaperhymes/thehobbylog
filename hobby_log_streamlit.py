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
    "set", "inserts / parallel", "player (if single)", "numbered",
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


def _render_responsive(df: pd.DataFrame):
    """Cards on mobile, full table on desktop — pure CSS, no toggle needed."""
    if df.empty:
        st.info("No results found.")
        return

    def v(row, col):
        return str(row.get(col, "") or "").strip()

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # ── Card layout (mobile) ──────────────────────────────────────────────────
    def field_html(label, value):
        if not value:
            return ""
        return (
            f'<div class="hl-field">'
            f'<span class="hl-lbl">{esc(label)}</span>'
            f'<span class="hl-val">{esc(value)}</span>'
            f'</div>'
        )

    def row_html(fields, extra_class=""):
        inner = "".join(field_html(lbl, val) for lbl, val in fields)
        return f'<div class="hl-row {extra_class}">{inner}</div>' if inner else ""

    cards = []
    for _, row in df.iterrows():
        r = row.to_dict()
        r1 = row_html([("Set", v(r,"set")), ("Player", v(r,"player (if single)")),
                       ("Insert", v(r,"inserts / parallel")), ("#", v(r,"numbered"))], "r1")
        r2 = row_html([("Platform", v(r,"platform")), ("Purchased", v(r,"purchase date")),
                       ("Posted", v(r,"post date")), ("Vendor", v(r,"vendor"))])
        r3 = row_html([("Price", v(r,"price")), ("Shipping", v(r,"shipping")),
                       ("Tax", v(r,"tax")), ("Add'l", v(r,"additional cost")),
                       ("Comp", v(r,"comp"))], "money")
        r4 = row_html([("Disposition", v(r,"disposition")), ("Comments", v(r,"comments"))], "last")
        cards.append(f'<div class="hl-card">{r1}{r2}{r3}{r4}</div>')

    cards_html = "\n".join(cards)

    # ── Table layout (desktop) ────────────────────────────────────────────────
    headers = [c.title() for c in COLUMNS if c in df.columns]
    header_row = "".join(f"<th>{esc(h)}</th>" for h in headers)

    table_rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        r = row.to_dict()
        cls = "tr-even" if i % 2 == 0 else "tr-odd"
        cells = "".join(
            f'<td class="{"td-money" if c in MONEY_COLS else ""}">{esc(v(r, c))}</td>'
            for c in COLUMNS if c in df.columns
        )
        table_rows.append(f'<tr class="{cls}">{cells}</tr>')

    table_html = f"""
    <div class="tbl-wrap">
      <table class="hl-table">
        <thead><tr>{header_row}</tr></thead>
        <tbody>{"".join(table_rows)}</tbody>
      </table>
    </div>
    """

    # ── Combined output ───────────────────────────────────────────────────────
    st.markdown(f"""
    <style>
    /* ── Responsive visibility ── */
    .hl-mobile  {{ display: block; }}
    .hl-desktop {{ display: none;  }}
    @media (min-width: 769px) {{
        .hl-mobile  {{ display: none;  }}
        .hl-desktop {{ display: block; }}
    }}

    /* ── Card styles ── */
    .hl-card {{
        background:#1a2535; border:1px solid #253545;
        border-radius:12px; padding:12px 14px; margin-bottom:10px;
    }}
    .hl-row {{
        display:flex; flex-wrap:wrap; gap:2px 18px;
        padding-bottom:8px; margin-bottom:8px; border-bottom:1px solid #253545;
    }}
    .hl-row.last {{ padding-bottom:0; margin-bottom:0; border-bottom:none; }}
    .hl-field    {{ display:flex; flex-direction:column; min-width:55px; max-width:100%; }}
    .hl-lbl      {{ color:#7a8fa3; font-size:clamp(9px,0.9vw + 0.2rem,11px);
                    font-weight:700; text-transform:uppercase;
                    letter-spacing:.5px; line-height:1.4; }}
    .hl-val      {{ color:#e8eaed; font-size:clamp(12px,1.2vw + 0.3rem,15px);
                    font-weight:500; line-height:1.4; word-break:break-word; }}
    .hl-row.r1   .hl-val {{ font-size:clamp(13px,1.3vw + 0.3rem,16px); font-weight:600; }}
    .hl-row.money .hl-val {{ color:#4ade80; }}

    /* ── Table styles ── */
    .tbl-wrap  {{ overflow-x:auto; width:100%; }}
    .hl-table  {{ border-collapse:collapse; width:100%;
                  font-size:clamp(11px,1.1vw + 0.2rem,14px);
                  color:#e8eaed; white-space:nowrap; }}
    .hl-table thead tr {{ background:#1D9BF0; color:#fff; }}
    .hl-table th {{
        padding:clamp(5px,0.6vw,9px) clamp(6px,0.8vw,11px);
        text-align:left; font-size:clamp(10px,1vw + 0.15rem,13px);
        font-weight:700; letter-spacing:.3px; border-right:1px solid #1278c2;
    }}
    .hl-table th:last-child {{ border-right:none; }}
    .hl-table td {{ padding:7px 10px; border-bottom:1px solid #253545; }}
    .hl-table .tr-even {{ background:#162030; }}
    .hl-table .tr-odd  {{ background:#1a2a3a; }}
    .hl-table .td-money {{ text-align:right; color:#4ade80; }}
    .hl-table tr:hover td {{ background:#1e3a50; }}
    </style>
    <div class="hl-mobile">{cards_html}</div>
    <div class="hl-desktop">{table_html}</div>
    """, unsafe_allow_html=True)


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

    # Mobile-friendly centered login card
    st.markdown("""
    <style>
    /* Password page: vertically center content */
    html, body, [class*="css"] { font-size: 16px !important; }
    @media (max-width: 768px) {
        .block-container {
            padding-left: 1rem !important;
            padding-right: 1rem !important;
            padding-top: 2rem !important;
        }
        .stTextInput input {
            font-size: 18px !important;
            min-height: 48px !important;
            padding: 10px 14px !important;
        }
        .stButton > button {
            min-height: 52px !important;
            font-size: 18px !important;
        }
    }
    </style>
    """, unsafe_allow_html=True)

    _, col, _ = st.columns([1, 3, 1])
    with col:
        st.markdown("<br>", unsafe_allow_html=True)
        st.title("🃏 Hobby Log")
        st.caption("Sports card purchase tracker")
        st.markdown("<br>", unsafe_allow_html=True)

        with st.form("login_form"):
            pw = st.text_input("Password", type="password",
                               placeholder="Enter password",
                               label_visibility="collapsed")
            submitted = st.form_submit_button("Sign In",
                                              use_container_width=True,
                                              type="primary")

        if submitted:
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

    st.markdown("""
    <style>
    /* ── Fluid base font: 13px on small phones → 16px on desktop ── */
    html, body, [class*="css"] {
        font-size: clamp(13px, 1.4vw + 0.5rem, 16px) !important;
    }

    /* Inputs & labels scale with viewport */
    .stTextInput input {
        font-size: clamp(14px, 1.6vw + 0.4rem, 18px) !important;
        min-height: clamp(40px, 5vw, 52px) !important;
    }
    label, .stSelectbox label {
        font-size: clamp(12px, 1.2vw + 0.4rem, 15px) !important;
    }
    div[data-baseweb="select"] * {
        font-size: clamp(13px, 1.3vw + 0.4rem, 16px) !important;
    }

    /* Buttons */
    .stButton > button {
        font-size: clamp(13px, 1.3vw + 0.3rem, 16px) !important;
        min-height: clamp(38px, 4.5vw, 48px) !important;
    }

    /* Metrics */
    [data-testid="stMetricValue"] {
        font-size: clamp(20px, 3vw + 0.5rem, 30px) !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: clamp(11px, 1.1vw + 0.3rem, 14px) !important;
    }

    /* Expander */
    details summary p {
        font-size: clamp(13px, 1.3vw + 0.3rem, 16px) !important;
    }

    /* Mobile-specific layout tweaks */
    @media (max-width: 768px) {
        .block-container {
            padding-left: 0.75rem !important;
            padding-right: 0.75rem !important;
            padding-top: 0.75rem !important;
        }
        .stButton > button { width: 100% !important; }
    }
    </style>
    """, unsafe_allow_html=True)

    _check_password()

    # ── Header ────────────────────────────────────────────────────────────────
    hdr, btn_col = st.columns([4, 1])
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
        filter_selections: dict[str, str] = {}
        available = [col for col in FILTER_COLS if col in df.columns]
        # 2-column grid — readable on both desktop and mobile
        for i in range(0, len(available), 2):
            pair = available[i:i + 2]
            cols = st.columns(2)
            for j, col in enumerate(pair):
                options = ["All"] + sorted(
                    {v for v in df[col].tolist() if v}, key=str.lower
                )
                filter_selections[col] = cols[j].selectbox(
                    col.title(), options, key=f"f_{col}"
                )

    # ── Apply filters ─────────────────────────────────────────────────────────
    filtered = df.copy()

    for col, val in filter_selections.items():
        if val != "All":
            filtered = filtered[filtered[col] == val]

    if search:
        terms = search.lower().split()
        def row_matches(row):
            row_text = " ".join(str(v).lower() for v in row)
            return all(term in row_text for term in terms)
        mask = filtered.apply(row_matches, axis=1)
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

    # ── Responsive layout ─────────────────────────────────────────────────────
    _render_responsive(filtered)


if __name__ == "__main__":
    main()
