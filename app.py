"""Warehouse stock & profit tracker: everything on ONE page.  Run with:  streamlit run app.py"""
import streamlit as st

import db
import inventory as inv
from views import dashboard, items, profit, purchases, sales, stock
from views.common import show_flash

st.set_page_config(page_title="Warehouse Stock & Profit", page_icon="📦", layout="wide",
                   initial_sidebar_state="collapsed")
db.init_db()

top_l, top_r = st.columns([3, 1])
top_l.title("📦 Warehouse Stock & Profit")
top_r.text_input("Your name", key="user_name",
                 help="Saved with every purchase and sale you log, so you can see who entered what.")
st.caption("Costing method: FIFO (oldest stock is sold first).")
show_flash()

with db.transaction() as _c:
    _no_items = inv.list_items(_c).empty

# 1. Overview numbers
dashboard.render()

# 2. Data entry: purchases on the left, sales on the right
st.divider()
left, right = st.columns(2, gap="large")
with left:
    purchases.render_form()
with right:
    sales.render_form()

# 3. Stock remaining
st.divider()
stock.render()

# 4. Profit
st.divider()
profit.render()

# 5. Full history
st.divider()
st.header("History")
tab_p, tab_s = st.tabs(["Purchases", "Sales"])
with tab_p:
    purchases.render_history()
with tab_s:
    sales.render_history()

# 6. Items (open by default until the first item exists)
st.divider()
with st.expander("Manage items (add products, change unit / reorder level)", expanded=_no_items):
    items.render()
