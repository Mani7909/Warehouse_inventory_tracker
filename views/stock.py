import streamlit as st

import db
import inventory as inv
from views.common import excel_bytes, money, money_cols, qty_fmt, show_df, show_flash


def render():
    st.header("Stock on hand")

    with db.transaction() as c:
        soh = inv.stock_on_hand(c)
        batches = inv.batches(c, only_open=True)

    if soh.empty:
        st.info("No items yet. Add items on the Add items page first.")
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("Total stock value (at cost)", money(soh["stock_value"].sum()))
    c2.metric("Items with stock", int((soh["qty_on_hand"] > 0).sum()))
    c3.metric("Low-stock items", int(soh["low_stock"].sum()))

    f1, f2, f3 = st.columns([2, 2, 1])
    search = f1.text_input("Search item")
    cats = sorted([x for x in soh["category"].unique() if x])
    chosen = f2.multiselect("Category", cats)
    only_stock = f3.checkbox("In stock only", value=False)

    view = soh.copy()
    if search:
        view = view[view["item"].str.contains(search, case=False, na=False)]
    if chosen:
        view = view[view["category"].isin(chosen)]
    if only_stock:
        view = view[view["qty_on_hand"] > 0]

    view["status"] = view.apply(
        lambda r: "Out of stock" if r["qty_on_hand"] <= 0 else ("Low" if r["low_stock"] else "OK"), axis=1)
    table = view[["item", "category", "qty_on_hand", "unit", "avg_cost", "stock_value",
                  "reorder_level", "status"]].rename(columns={
        "item": "Item", "category": "Category", "qty_on_hand": "In stock", "unit": "Unit",
        "avg_cost": "Avg cost (₹)", "stock_value": "Stock value (₹)", "reorder_level": "Reorder level",
        "status": "Status"})
    show_df(table, column_config=money_cols("Avg cost (₹)", "Stock value (₹)"))

    st.download_button(
        "Download as Excel",
        data=excel_bytes({"Stock on hand": table, "Open batches": batches.drop(columns=["entered_by"])}),
        file_name="stock_on_hand.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    st.subheader("Batches behind the stock")
    st.caption("Each row is a purchase that still has unsold units. Different cost per unit = different purchase price.")
    names = ["All items"] + list(view["item"])
    pick = st.selectbox("Show batches for", names)
    b = batches if pick == "All items" else batches[batches["item"] == pick]
    b = b[b["item"].isin(view["item"])]
    if b.empty:
        st.caption("No open batches.")
    else:
        show_df(
            b[["purchase_id", "item", "date", "qty", "qty_remaining", "unit_cost", "value_remaining",
               "supplier"]].rename(columns={
                "purchase_id": "Batch #", "item": "Item", "date": "Bought on", "qty": "Originally bought",
                "qty_remaining": "Remaining", "unit_cost": "Cost / unit (₹)",
                "value_remaining": "Value left (₹)", "supplier": "Supplier"}),
            column_config=money_cols("Cost / unit (₹)", "Value left (₹)"),
        )
