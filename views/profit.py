from datetime import date

import streamlit as st

import db
import reports
from views.common import (date_range_input, excel_bytes, load_items, money, money_cols, show_df,
                          show_flash)


def render():
    st.header("Profit report")

    items = load_items()
    if items.empty:
        st.info("No data yet.")
        return

    f1, f2 = st.columns([2, 2])
    with f1:
        rng = date_range_input("Date range", key="profit_range", default_start=date.today().replace(day=1))
    chosen = f2.multiselect("Items (leave empty for all)", list(items["name"]))
    if rng is None:
        return

    with db.transaction() as c:
        df = reports.sales_detail(c, rng[0], rng[1])
    if chosen:
        df = df[df["item"].isin(chosen)]

    if df.empty:
        st.info("No sales in this selection.")
        return

    s = reports.summary(df)
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Revenue", money(s["revenue"]))
    m2.metric("Cost of goods sold", money(s["cost"]))
    m3.metric("Profit", money(s["profit"]))
    m4.metric("Margin", f"{s['margin_pct']:.1f}%", help=f"{s['sales_count']} sales")

    st.subheader("Profit over time")
    grain = st.radio("Group by", ["Day", "Week", "Month"], index=2, horizontal=True)
    by_period = reports.profit_by_period(df, {"Day": "D", "Week": "W", "Month": "M"}[grain])
    st.bar_chart(by_period.set_index("period")["profit"])

    left, right = st.columns(2)
    by_item = reports.profit_by_item(df)
    with left:
        st.subheader("Profit by item")
        st.bar_chart(by_item.set_index("item")["profit"])
    with right:
        st.subheader("Item summary")
        item_table = by_item.rename(columns={
            "item": "Item", "qty_sold": "Qty sold", "revenue": "Revenue (₹)", "cost": "Cost (₹)",
            "profit": "Profit (₹)", "margin_pct": "Margin %"})
        show_df(item_table, column_config=money_cols("Revenue (₹)", "Cost (₹)", "Profit (₹)"))

    st.subheader("Every sale in this period")
    detail = df[["sale_id", "date", "item", "qty", "sale_price", "revenue", "cost", "profit",
                 "margin_pct", "customer"]].rename(columns={
        "sale_id": "Sale #", "date": "Date", "item": "Item", "qty": "Qty", "sale_price": "Price / unit (₹)",
        "revenue": "Revenue (₹)", "cost": "Cost (₹)", "profit": "Profit (₹)", "margin_pct": "Margin %",
        "customer": "Customer"})
    show_df(detail, column_config=money_cols("Price / unit (₹)", "Revenue (₹)", "Cost (₹)", "Profit (₹)"))

    period_table = by_period.rename(columns={
        "period": grain, "revenue": "Revenue (₹)", "cost": "Cost (₹)", "profit": "Profit (₹)"})
    st.download_button(
        "Download report as Excel",
        data=excel_bytes({"Sales": detail, "By item": item_table, f"By {grain.lower()}": period_table}),
        file_name=f"profit_report_{rng[0]}_to_{rng[1]}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
