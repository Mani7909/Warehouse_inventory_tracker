"""Warehouse stock & profit tracker.  Run with:  streamlit run app.py

Two pages (sidebar):
  * Warehouse - purchases, sales, stock, profit and history, all on one page
  * Add items - create and edit the product list
"""
import streamlit as st

import db
import inventory as inv
from views import dashboard, items, profit, purchases, sales, stock
from views.common import show_flash

st.set_page_config(page_title="Warehouse Stock & Profit", page_icon="📦", layout="wide",
                   initial_sidebar_state="expanded")
db.init_db()


def home():
    st.title("📦 Warehouse Stock & Profit")
    st.caption("Costing method: FIFO (oldest stock is sold first).")
    show_flash()

    with db.transaction() as c:
        no_items = inv.list_items(c).empty
    if no_items:
        st.page_link(items_page, label="Add your first item", icon="➕")

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


def add_items():
    st.title("➕ Add items")
    show_flash()
    items.render()


home_page = st.Page(home, title="Warehouse", icon="📦", url_path="warehouse", default=True)
items_page = st.Page(add_items, title="Add items", icon="➕", url_path="items")

with st.sidebar:
    st.text_input("Your name", key="user_name",
                  help="Saved with every purchase and sale you log, so you can see who entered what.")

st.navigation([home_page, items_page]).run()
