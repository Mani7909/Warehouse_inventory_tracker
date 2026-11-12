from datetime import date

import streamlit as st

import db
import inventory as inv
from views.common import (current_user, flash, item_label_map, load_items, money, money_cols,
                          pick_or_new, qty_fmt, show_df)


def render_form():
    """Log-a-purchase form (one section of the single page)."""
    st.subheader("Log a purchase")
    items = load_items()
    if items.empty:
        st.info("Add an item on the **Add items** page first (sidebar).")
        return
    labels = item_label_map(items)

    ver = st.session_state.setdefault("purchase_ver", 0)   # bumped after save to clear the inputs
    item_id = st.selectbox("Item", options=list(labels), format_func=lambda i: labels[i], key="p_item")

    with db.transaction() as c:
        open_batches = inv.batches(c, item_id, only_open=True)
        last = inv.last_purchase(c, item_id)
        known_suppliers = inv.suppliers(c)
    if open_batches.empty:
        st.caption("No unsold stock of this item right now.")
    else:
        st.caption("Unsold batches of this item (oldest sells first):")
        show_df(
            open_batches[["purchase_id", "date", "qty_remaining", "unit_cost", "supplier"]].rename(columns={
                "purchase_id": "Batch #", "date": "Bought on", "qty_remaining": "Remaining",
                "unit_cost": "Cost / unit (₹)", "supplier": "Supplier"}),
            column_config=money_cols("Cost / unit (₹)"),
        )

    last_cost = float(last["unit_cost"]) if last else 0.0
    last_supplier = (last["supplier"] if last else "") or None

    c1, c2 = st.columns(2)
    d = c1.date_input("Purchase date", value=date.today(), key=f"p_date_{ver}")
    qty = c2.number_input("Quantity bought", min_value=0.0, step=1.0, format="%.3f", key=f"p_qty_{ver}")
    cost = c1.number_input("Cost per unit (₹)", min_value=0.0, step=1.0, format="%.2f",
                           value=last_cost, key=f"p_cost_{ver}_{item_id}")
    with c2:
        supplier = pick_or_new("Supplier", known_suppliers, f"p_sup_{ver}_{item_id}",
                               allow_none=True, default=last_supplier)
    invoice = c1.text_input("Invoice / bill no. (optional)", key=f"p_inv_{ver}")
    if last:
        st.caption(f"Cost and supplier are pre-filled from your last purchase of this item "
                   f"({money(last_cost)}); change them if this batch is different.")

    if st.button("Save purchase", type="primary"):
        error = None
        try:
            with db.transaction() as c:
                inv.add_purchase(c, item_id, d, qty, cost, supplier, invoice, current_user())
        except inv.InventoryError as e:
            error = str(e)
        if error:
            st.error(error)
        else:
            st.session_state["purchase_ver"] = ver + 1
            flash(f"Purchase saved: {qty_fmt(qty)} × {labels[item_id]} at {money(cost)} each "
                  f"(total {money(qty * cost)}).")
            st.rerun()


def render_history():
    """Purchase history table + delete-a-mistake."""
    with db.transaction() as c:
        allp = inv.batches(c)
    if allp.empty:
        st.info("No purchases logged yet.")
        return
    allp = allp.sort_values(["date", "purchase_id"], ascending=False)
    show_df(
        allp[["purchase_id", "date", "item", "qty", "qty_remaining", "unit_cost",
              "supplier", "invoice_no", "entered_by"]].rename(columns={
            "purchase_id": "Batch #", "date": "Date", "item": "Item", "qty": "Bought",
            "qty_remaining": "Remaining", "unit_cost": "Cost / unit (₹)", "supplier": "Supplier",
            "invoice_no": "Invoice", "entered_by": "Entered by"}),
        column_config=money_cols("Cost / unit (₹)"),
    )

    with st.expander("Delete a mistaken purchase"):
        st.caption("Only batches that no sale has used can be deleted. "
                   "If a sale used it, delete that sale first.")
        pid_labels = {
            int(r.purchase_id): f"#{r.purchase_id} · {r.date} · {r['item']} · {qty_fmt(r.qty)} @ {money(r.unit_cost)}"
            for _, r in allp.iterrows()
        }
        pid = st.selectbox("Batch", options=list(pid_labels), format_func=lambda i: pid_labels[i], key="del_p")
        sure = st.checkbox("Yes, delete this purchase", key="del_p_ok")
        if st.button("Delete purchase", disabled=not sure):
            error = None
            try:
                with db.transaction() as c:
                    inv.delete_purchase(c, pid)
            except inv.InventoryError as e:
                error = str(e)
            if error:
                st.error(error)
            else:
                flash(f"Deleted purchase #{pid}.")
                st.rerun()
