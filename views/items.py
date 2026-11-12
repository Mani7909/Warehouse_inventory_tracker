import streamlit as st

import db
import inventory as inv
from views.common import (CATEGORY_PRESETS, UNIT_PRESETS, flash, load_items, merge_choices,
                          pick_or_new, show_df)


def render():
    """The 'Add items' page body."""
    items = load_items()
    with db.transaction() as c:
        used_categories = inv.categories(c)
    units = merge_choices(UNIT_PRESETS, items["unit"] if not items.empty else [])
    categories = merge_choices(CATEGORY_PRESETS, used_categories)

    ver = st.session_state.setdefault("item_ver", 0)   # bumped after save to clear the inputs

    st.subheader("Add a new item")
    st.caption("Add an item once, then log purchases and sales against it. "
               "Pick the unit and category from the lists, or choose ➕ Add new… to type your own.")
    c1, c2 = st.columns(2)
    name = c1.text_input("Item name", key=f"i_name_{ver}")
    with c2:
        unit = pick_or_new("Unit", units, f"i_unit_{ver}", default="pcs")
    with c1:
        category = pick_or_new("Category", categories, f"i_cat_{ver}", allow_none=True)
    reorder = c2.number_input("Reorder level (alert when stock falls to this or below)",
                              min_value=0.0, step=1.0, format="%.3f", key=f"i_reorder_{ver}")

    if st.button("Add item", type="primary"):
        error = None
        try:
            with db.transaction() as c:
                inv.add_item(c, name, unit, category, reorder)
        except inv.InventoryError as e:
            error = str(e)
        if error:
            st.error(error)
        else:
            st.session_state["item_ver"] = ver + 1
            flash(f"Added item '{name.strip()}'.")
            st.rerun()

    st.subheader("All items")
    if items.empty:
        st.info("No items yet. Add your first one above.")
        return

    show_df(items[["name", "category", "unit", "reorder_level"]].rename(columns={
        "name": "Item", "category": "Category", "unit": "Unit", "reorder_level": "Reorder level"}))

    with st.expander("Edit unit, category or reorder level"):
        names = dict(zip(items["item_id"].astype(int), items["name"]))
        item_id = st.selectbox("Item", options=list(names), format_func=lambda i: names[i], key="edit_item")
        row = items[items["item_id"] == item_id].iloc[0]
        e1, e2, e3 = st.columns(3)
        with e1:
            e_unit = pick_or_new("Unit", units, f"e_unit_{item_id}", default=row["unit"])
        with e2:
            e_cat = pick_or_new("Category", categories, f"e_cat_{item_id}", allow_none=True,
                                default=row["category"] or None)
        e_reorder = e3.number_input("Reorder level", min_value=0.0, step=1.0, format="%.3f",
                                    value=float(row["reorder_level"]), key=f"e_reorder_{item_id}")
        if st.button("Save changes"):
            with db.transaction() as c:
                inv.update_item(c, int(item_id), e_unit, e_cat, e_reorder)
            flash(f"Updated '{row['name']}'.")
            st.rerun()
