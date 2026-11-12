import streamlit as st

import db
import inventory as inv
from views.common import flash, show_df, show_flash, load_items


def render():
    st.caption("Add an item once, then log purchases and sales against it.")

    items = load_items()

    with st.form("add_item", clear_on_submit=True):
        st.subheader("Add a new item")
        c1, c2 = st.columns(2)
        name = c1.text_input("Item name")
        unit = c2.text_input("Unit (pcs, kg, box, ...)", value="pcs")
        category = c1.text_input("Category (optional)")
        reorder = c2.number_input("Reorder level (alert when stock falls to this or below)",
                                  min_value=0.0, step=1.0, format="%.3f")
        ok = st.form_submit_button("Add item", type="primary")

    if ok:
        error = None
        try:
            with db.transaction() as c:
                inv.add_item(c, name, unit, category, reorder)
        except inv.InventoryError as e:
            error = str(e)
        if error:
            st.error(error)
        else:
            flash(f"Added item '{name.strip()}'.")
            st.rerun()

    st.subheader("All items")
    if items.empty:
        st.info("No items yet. Add your first one above.")
        return

    show_df(items[["name", "category", "unit", "reorder_level"]].rename(columns={
        "name": "Item", "category": "Category", "unit": "Unit", "reorder_level": "Reorder level"}))

    with st.expander("Edit unit, category or reorder level"):
        names = dict(zip(items["item_id"], items["name"]))
        item_id = st.selectbox("Item", options=list(names), format_func=lambda i: names[i], key="edit_item")
        row = items[items["item_id"] == item_id].iloc[0]
        with st.form(f"edit_item_form_{item_id}"):
            c1, c2, c3 = st.columns(3)
            unit = c1.text_input("Unit", value=row["unit"])
            category = c2.text_input("Category", value=row["category"])
            reorder = c3.number_input("Reorder level", min_value=0.0, step=1.0, format="%.3f",
                                      value=float(row["reorder_level"]))
            saved = st.form_submit_button("Save changes")
        if saved:
            with db.transaction() as c:
                inv.update_item(c, int(item_id), unit, category, reorder)
            flash(f"Updated '{row['name']}'.")
            st.rerun()
