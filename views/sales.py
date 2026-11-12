from datetime import date

import streamlit as st

import db
import inventory as inv
import reports
from views.common import (current_user, date_range_input, flash, item_label_map, load_items, money,
                          money_cols, qty_fmt, show_df)


def render_form():
    """Log-a-sale form with live FIFO preview (one section of the single page)."""
    st.subheader("Log a sale")
    items = load_items()
    if items.empty:
        st.info("Add an item under **Manage items** first.")
        return
    labels = item_label_map(items)
    units = dict(zip(items["item_id"].astype(int), items["unit"]))

    ver = st.session_state.setdefault("sale_ver", 0)   # bumped after save to reset the inputs
    item_id = st.selectbox("Item", options=list(labels), format_func=lambda i: labels[i], key="s_item")

    c1, c2 = st.columns(2)
    d = c1.date_input("Sale date", value=date.today(), key=f"s_date_{ver}")
    qty = c2.number_input("Quantity sold", min_value=0.0, step=1.0, format="%.3f", key=f"s_qty_{ver}")
    price = c1.number_input("Selling price per unit (₹)", min_value=0.0, step=1.0, format="%.2f",
                            key=f"s_price_{ver}")
    customer = c2.text_input("Customer (optional)", key=f"s_cust_{ver}")

    preview, err = None, None
    with db.transaction() as c:
        avail = inv.stock_available(c, item_id, d)
        total = inv.stock_available(c, item_id)
        if qty > 0:
            try:
                preview = inv.preview_sale(c, item_id, d, qty, price)
            except inv.InventoryError as e:
                err = str(e)

    unit = units[item_id]
    st.caption(f"Available to sell on {d}: **{qty_fmt(avail)} {unit}**"
               + (f" (total in warehouse: {qty_fmt(total)})" if abs(total - avail) > 1e-9 else ""))

    if err:
        st.error(err)
    elif preview:
        m1, m2, m3 = st.columns(3)
        m1.metric("Revenue", money(preview["revenue"]))
        m2.metric("Cost (FIFO)", money(preview["cost"]))
        m3.metric("Profit", money(preview["profit"]))
        st.caption("Stock this sale will use:")
        plan = [{"Batch #": p["purchase_id"], "Bought on": p["batch_date"], "Qty used": p["qty_taken"],
                 "Cost / unit (₹)": p["unit_cost"], "Cost (₹)": p["qty_taken"] * p["unit_cost"]}
                for p in preview["plan"]]
        show_df(plan, column_config=money_cols("Cost / unit (₹)", "Cost (₹)"))
        if price <= 0:
            st.warning("Enter a selling price to save this sale.")

    can_save = preview is not None and price > 0
    if st.button("Save sale", type="primary", disabled=not can_save):
        error, result = None, None
        try:
            with db.transaction() as c:
                result = inv.record_sale(c, item_id, d, qty, price, customer, current_user())
        except inv.InventoryError as e:
            error = str(e)
        if error:
            st.error(error)
        else:
            st.session_state["sale_ver"] = ver + 1
            flash(f"Sale saved: {qty_fmt(qty)} × {labels[item_id]} on {d}. "
                  f"Profit {money(result['profit'])}.")
            st.rerun()


def render_history():
    """Sales history table, batches used per sale, delete-a-sale."""
    rng = date_range_input("Date range", key="sales_hist_range")
    if rng is None:
        return
    with db.transaction() as c:
        sales = reports.sales_detail(c, rng[0], rng[1])
    if sales.empty:
        st.info("No sales in this date range.")
        return

    show_df(
        sales[["sale_id", "date", "item", "qty", "sale_price", "revenue", "cost", "profit",
               "customer", "entered_by"]].rename(columns={
            "sale_id": "Sale #", "date": "Date", "item": "Item", "qty": "Qty",
            "sale_price": "Price / unit (₹)", "revenue": "Revenue (₹)", "cost": "Cost (₹)",
            "profit": "Profit (₹)", "customer": "Customer", "entered_by": "Entered by"}),
        column_config=money_cols("Price / unit (₹)", "Revenue (₹)", "Cost (₹)", "Profit (₹)"),
    )

    with st.expander("See which batches a sale used, or delete a sale"):
        s_labels = {
            int(r.sale_id): f"#{r.sale_id} · {r.date} · {r['item']} · {qty_fmt(r.qty)} @ {money(r.sale_price)}"
            for _, r in sales.iterrows()
        }
        sid = st.selectbox("Sale", options=list(s_labels), format_func=lambda i: s_labels[i], key="view_sale")
        with db.transaction() as c:
            allocs = reports.sale_allocations(c, sid)
        show_df(allocs.rename(columns={
            "purchase_id": "Batch #", "batch_date": "Bought on", "qty_taken": "Qty used",
            "unit_cost": "Cost / unit (₹)", "cost": "Cost (₹)"}),
            column_config=money_cols("Cost / unit (₹)", "Cost (₹)"))
        st.caption("Deleting a sale puts its quantity back into the exact batches it came from.")
        sure = st.checkbox("Yes, delete this sale", key="del_s_ok")
        if st.button("Delete sale", disabled=not sure):
            with db.transaction() as c:
                inv.delete_sale(c, sid)
            flash(f"Deleted sale #{sid}; stock restored.")
            st.rerun()
