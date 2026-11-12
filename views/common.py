"""Small UI helpers shared by all pages."""
import io
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import db
import inventory as inv


def money(x):
    x = float(x or 0)
    return f"-₹{abs(x):,.2f}" if x < 0 else f"₹{x:,.2f}"


def qty_fmt(x):
    s = f"{float(x or 0):,.3f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def current_user():
    return (st.session_state.get("user_name") or "").strip()


# ---- one-shot success/error messages that survive st.rerun() ----

def flash(msg, kind="success"):
    st.session_state["_flash"] = (kind, msg)


def show_flash():
    item = st.session_state.pop("_flash", None)
    if item:
        kind, msg = item
        getattr(st, kind)(msg)


def show_df(df, **kwargs):
    """st.dataframe at full width, working across Streamlit versions."""
    kwargs.setdefault("hide_index", True)
    try:
        st.dataframe(df, width="stretch", **kwargs)
    except TypeError:
        st.dataframe(df, use_container_width=True, **kwargs)


def money_cols(*labels):
    return {l: st.column_config.NumberColumn(l, format="%.2f") for l in labels}


def excel_bytes(sheets):
    """dict of {sheet name: DataFrame} -> .xlsx bytes."""
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        for name, df in sheets.items():
            df.to_excel(xw, sheet_name=name[:31], index=False)
    return buf.getvalue()


def date_range_input(label, key, default_start=None):
    """Returns (start_iso, end_iso) or None while the user is mid-selection."""
    start = default_start or (date.today() - timedelta(days=30))
    val = st.date_input(label, value=(start, date.today()), key=key)
    if isinstance(val, (list, tuple)) and len(val) == 2:
        return val[0].isoformat(), val[1].isoformat()
    st.info("Pick both a start and an end date.")
    return None


def load_items():
    with db.transaction() as c:
        return inv.list_items(c)


def item_label_map(items):
    return {int(r.item_id): f"{r['name']} ({r.unit})" for _, r in items.iterrows()}
