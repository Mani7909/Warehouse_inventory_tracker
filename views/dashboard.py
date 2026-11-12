from datetime import date

import streamlit as st

import db
import inventory as inv
import reports
from views.common import money, qty_fmt, show_df, show_flash, money_cols


def render():
    st.header("Overview")

    with db.transaction() as c:
        soh = inv.stock_on_hand(c)
        sales = reports.sales_detail(c)

    if soh.empty:
        st.info("Welcome! Add your products on the **Add items** page (sidebar), then log purchases and sales.")
        return

    month_start = date.today().replace(day=1).isoformat()
    this_month = reports.summary(sales[sales["date"] >= month_start])
    overall = reports.summary(sales)
    low = soh[soh["low_stock"]]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stock value (at cost)", money(soh["stock_value"].sum()))
    c2.metric("Items in stock", f"{int((soh['qty_on_hand'] > 0).sum())} of {len(soh)}")
    c3.metric("Profit this month", money(this_month["profit"]),
              help=f"Revenue {money(this_month['revenue'])}, from {this_month['sales_count']} sales")
    c4.metric("Profit all time", money(overall["profit"]),
              help=f"Revenue {money(overall['revenue'])}, margin {overall['margin_pct']:.1f}%")

    if not low.empty:
        st.warning(f"{len(low)} item(s) at or below their reorder level.")
        show_df(
            low[["item", "qty_on_hand", "unit", "reorder_level"]].rename(columns={
                "item": "Item", "qty_on_hand": "In stock", "unit": "Unit", "reorder_level": "Reorder level"}),
        )

    left, right = st.columns(2)
    with left:
        st.subheader("Profit by month")
        by_month = reports.profit_by_period(sales, "M")
        if by_month.empty:
            st.caption("No sales logged yet.")
        else:
            st.bar_chart(by_month.set_index("period")["profit"])
    with right:
        st.subheader("Latest sales")
        if sales.empty:
            st.caption("No sales logged yet.")
        else:
            latest = sales.head(8)[["date", "item", "qty", "revenue", "profit"]].rename(columns={
                "date": "Date", "item": "Item", "qty": "Qty", "revenue": "Revenue (₹)", "profit": "Profit (₹)"})
            show_df(latest, column_config=money_cols("Revenue (₹)", "Profit (₹)"))
