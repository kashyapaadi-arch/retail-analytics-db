"""Streamlit user interface for the retail sales and inventory database."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st
from mysql.connector import Error as MySQLError

from db import call_procedure, get_connection, query_df

st.set_page_config(page_title="Retail Analytics", page_icon="🛍️", layout="wide")
st.title("Sales and Inventory Analytics")
st.caption("Retail operations, stock health, and sales insights")

PAGES = ("Dashboard", "Inventory", "Sales", "Purchasing", "Forecast", "Audit log")
page = st.sidebar.radio("Page", PAGES)


def show_database_error(error: Exception) -> None:
    st.error(f"Could not complete the database request: {error}")
    st.caption("Check that MySQL is running, the SQL scripts have been applied, and your .env settings are correct.")


def _dashboard() -> None:
    st.header("Dashboard")
    try:
        kpis = query_df(
            """SELECT (SELECT COUNT(*) FROM sales_order) AS orders,
                      (SELECT COALESCE(SUM(total_amount), 0) FROM sales_order) AS revenue,
                      (SELECT COUNT(*) FROM product) AS products,
                      (SELECT COUNT(*) FROM low_stock_products) AS low_stock"""
        ).iloc[0]
        cols = st.columns(4)
        cols[0].metric("Orders", f"{int(kpis['orders']):,}")
        cols[1].metric("Revenue", f"₹{float(kpis['revenue']):,.2f}")
        cols[2].metric("Products", f"{int(kpis['products']):,}")
        cols[3].metric("Low stock", f"{int(kpis['low_stock']):,}")

        monthly = query_df("SELECT `month`, revenue, profit FROM monthly_sales_summary ORDER BY `month`")
        top_products = query_df(
            """SELECT p.name AS product, SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct / 100)) AS revenue
                 FROM order_item oi JOIN product p ON p.product_id=oi.product_id
                GROUP BY p.product_id, p.name ORDER BY revenue DESC LIMIT 10"""
        )
        category = query_df(
            """SELECT c.name AS category, SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct / 100)) AS revenue
                 FROM category c JOIN product p ON p.category_id=c.category_id
                 JOIN order_item oi ON oi.product_id=p.product_id GROUP BY c.category_id,c.name ORDER BY revenue DESC"""
        )
        left, right = st.columns(2)
        with left:
            st.subheader("Monthly revenue and profit")
            if not monthly.empty:
                st.plotly_chart(px.line(monthly, x="month", y=["revenue", "profit"], markers=True,
                                        labels={"value": "₹", "variable": "Measure"}), use_container_width=True)
            st.subheader("Top products")
            if not top_products.empty:
                st.plotly_chart(px.bar(top_products, x="revenue", y="product", orientation="h"), use_container_width=True)
        with right:
            st.subheader("Revenue share by category")
            if not category.empty:
                st.plotly_chart(px.pie(category, names="category", values="revenue", hole=0.4), use_container_width=True)
            st.subheader("Recent orders")
            st.dataframe(query_df(
                """SELECT so.order_id, so.order_date, c.name AS customer, so.payment_mode, so.total_amount
                     FROM sales_order so JOIN customer c ON c.customer_id=so.customer_id
                    ORDER BY so.order_date DESC LIMIT 10"""), use_container_width=True, hide_index=True)
    except Exception as exc:
        show_database_error(exc)


def _inventory() -> None:
    st.header("Inventory")
    try:
        inventory = query_df(
            """SELECT p.product_id, p.name AS product, c.name AS category,
                      i.quantity_in_stock, p.reorder_level, p.unit_price,
                      COALESCE(a.abc_class, 'C') AS abc_class
                 FROM product p JOIN category c ON c.category_id=p.category_id
                 JOIN inventory i ON i.product_id=p.product_id
                 LEFT JOIN abc_classification a ON a.product_id=p.product_id
                ORDER BY i.quantity_in_stock, p.name"""
        )
        st.dataframe(inventory, use_container_width=True, hide_index=True)
        st.subheader("Recent low-stock alerts")
        alerts = query_df(
            """SELECT sa.created_at, p.name AS product, sa.quantity
                 FROM stock_alert sa JOIN product p ON p.product_id=sa.product_id
                ORDER BY sa.created_at DESC LIMIT 100"""
        )
        st.dataframe(alerts, use_container_width=True, hide_index=True)
    except Exception as exc:
        show_database_error(exc)


def _sales() -> None:
    st.header("Sales")
    try:
        customers = query_df("SELECT customer_id, name, phone FROM customer ORDER BY name")
        employees = query_df("SELECT employee_id, name FROM employee WHERE role='sales_staff' ORDER BY name")
        products = query_df(
            """SELECT p.product_id, p.name, p.unit_price, i.quantity_in_stock
                 FROM product p JOIN inventory i ON i.product_id=p.product_id ORDER BY p.name"""
        )
        if customers.empty or employees.empty or products.empty:
            st.info("Load the sample data before placing an order.")
            return
        customer_labels = {f"{r.name} · {r.phone or 'no phone'}": int(r.customer_id) for r in customers.itertuples()}
        employee_labels = {r.name: int(r.employee_id) for r in employees.itertuples()}
        product_labels = {f"{r.name} · ₹{float(r.unit_price):.2f} · stock {r.quantity_in_stock}": r for r in products.itertuples()}
        with st.form("place-order"):
            customer_label = st.selectbox("Customer", list(customer_labels))
            employee_name = st.selectbox("Sales staff", list(employee_labels))
            product_label = st.selectbox("Product", list(product_labels))
            quantity = st.number_input("Quantity", min_value=1, max_value=1000, value=1, step=1)
            discount = st.selectbox("Discount", [0, 5, 10], index=0)
            payment = st.selectbox("Payment mode", ["cash", "card", "upi"])
            submitted = st.form_submit_button("Place order", type="primary")
        if submitted:
            product = product_labels[product_label]
            try:
                result = call_procedure("place_order", [
                    customer_labels[customer_label], employee_labels[employee_name],
                    int(product.product_id), int(quantity), float(discount), payment, 0,
                ])
                st.success(f"Order #{result[-1]} placed successfully.")
            except MySQLError as exc:
                message = str(exc)
                if "Insufficient stock" in message:
                    st.warning("There is not enough stock to complete that order.")
                else:
                    st.error(f"The order was rejected: {message}")
        st.subheader("Recent orders")
        st.dataframe(query_df(
            """SELECT so.order_id, so.order_date, c.name AS customer, so.payment_mode, so.total_amount
                 FROM sales_order so JOIN customer c ON c.customer_id=so.customer_id
                ORDER BY so.order_date DESC LIMIT 50"""), use_container_width=True, hide_index=True)
    except Exception as exc:
        show_database_error(exc)


def _suggestions() -> pd.DataFrame:
    return query_df(
        """WITH latest_forecast AS (
               SELECT product_id, MAX(forecast_month) AS forecast_month
               FROM retail_dw.demand_forecast GROUP BY product_id
           ), best AS (
               SELECT df.product_id, df.predicted_units, df.forecast_month,
                      ROW_NUMBER() OVER (PARTITION BY df.product_id ORDER BY df.mae, df.model_name) AS rank_no
               FROM retail_dw.demand_forecast df
               JOIN latest_forecast lf ON lf.product_id=df.product_id AND lf.forecast_month=df.forecast_month
           ), cheapest AS (
               SELECT supplier_id, product_id, supply_price,
                      ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY supply_price,supplier_id) AS rank_no
               FROM supplier_product
           ), monthly_demand AS (
               SELECT p.product_id, DATE_FORMAT(d.full_date,'%Y-%m-01') AS month_start, SUM(f.quantity) AS units
               FROM retail_dw.fact_sales f
               JOIN retail_dw.dim_date d ON d.date_key=f.date_key
               JOIN retail_dw.dim_product p ON p.product_key=f.product_key
               GROUP BY p.product_id, DATE_FORMAT(d.full_date,'%Y-%m-01')
           ), recent_demand AS (
               SELECT product_id, units,
                      ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY month_start DESC) AS month_rank
               FROM monthly_demand
           ), safety AS (
               SELECT product_id, CEIL(1.65 * COALESCE(STDDEV_SAMP(units),0)) AS safety_stock
               FROM recent_demand WHERE month_rank <= 6 GROUP BY product_id
           )
           SELECT p.product_id, p.name AS product, b.forecast_month, b.predicted_units,
                  COALESCE(safety.safety_stock,0) AS safety_stock, i.quantity_in_stock,
                  GREATEST(0, CEIL(b.predicted_units + COALESCE(safety.safety_stock,0) - i.quantity_in_stock)) AS suggested_order_qty,
                  c.supplier_id, s.name AS supplier_name, c.supply_price
           FROM best b JOIN product p ON p.product_id=b.product_id
           JOIN inventory i ON i.product_id=p.product_id
           LEFT JOIN safety ON safety.product_id=p.product_id
           LEFT JOIN cheapest c ON c.product_id=p.product_id AND c.rank_no=1
           LEFT JOIN supplier s ON s.supplier_id=c.supplier_id
           WHERE b.rank_no=1 ORDER BY suggested_order_qty DESC, p.name"""
    )


def _purchasing() -> None:
    st.header("Purchasing")
    try:
        suggestions = _suggestions()
        if suggestions.empty:
            st.info("Run the ETL and forecasting scripts to see replenishment suggestions.")
        else:
            st.subheader("Forecast-based reorder suggestions")
            st.dataframe(suggestions, use_container_width=True, hide_index=True)
            if st.button("Draft pending purchase orders", type="primary"):
                needs = suggestions[(suggestions.suggested_order_qty > 0) & suggestions.supplier_id.notna()]
                if needs.empty:
                    st.info("No products currently need restocking.")
                else:
                    connection = get_connection()
                    try:
                        cursor = connection.cursor()
                        for supplier_id, group in needs.groupby("supplier_id"):
                            cursor.execute("INSERT INTO purchase_order (supplier_id,status) VALUES (%s,'PENDING')", (int(supplier_id),))
                            po_id = cursor.lastrowid
                            cursor.executemany(
                                "INSERT INTO purchase_order_item (po_id,product_id,quantity,unit_cost) VALUES (%s,%s,%s,%s)",
                                [(po_id, int(r.product_id), int(r.suggested_order_qty), r.supply_price) for r in group.itertuples()],
                            )
                        connection.commit()
                        st.success(f"Drafted {needs.supplier_id.nunique()} pending purchase order(s).")
                    except Exception:
                        connection.rollback()
                        raise
                    finally:
                        connection.close()
        st.subheader("Pending purchase orders")
        pending = query_df(
            """SELECT po.po_id, po.order_date, s.name AS supplier, COUNT(poi.product_id) AS lines
                 FROM purchase_order po JOIN supplier s ON s.supplier_id=po.supplier_id
                 LEFT JOIN purchase_order_item poi ON poi.po_id=po.po_id
                WHERE po.status='PENDING' GROUP BY po.po_id, po.order_date, s.name ORDER BY po.order_date DESC"""
        )
        st.dataframe(pending, use_container_width=True, hide_index=True)
        if not pending.empty:
            po_labels = {f"PO #{r.po_id} · {r.supplier} · {r.order_date}": int(r.po_id) for r in pending.itertuples()}
            selected = st.selectbox("Purchase order to receive", list(po_labels))
            if st.button("Receive selected purchase order"):
                try:
                    call_procedure("receive_purchase_order", [po_labels[selected]])
                    st.success("Purchase order received and stock updated.")
                    st.rerun()
                except MySQLError as exc:
                    st.error(f"The purchase order was rejected: {exc}")
    except Exception as exc:
        show_database_error(exc)


def _forecast() -> None:
    st.header("Demand forecast")
    try:
        products = query_df("SELECT product_id, name FROM product ORDER BY name")
        if products.empty:
            st.info("Load products and run the warehouse ETL first.")
            return
        labels = {r.name: int(r.product_id) for r in products.itertuples()}
        selected_name = st.selectbox("Product", list(labels))
        product_id = labels[selected_name]
        history = query_df(
            """SELECT DATE_FORMAT(d.full_date,'%Y-%m-01') AS month_start, SUM(f.quantity) AS units
                 FROM retail_dw.fact_sales f JOIN retail_dw.dim_date d ON d.date_key=f.date_key
                JOIN retail_dw.dim_product p ON p.product_key=f.product_key
                WHERE p.product_id=%s GROUP BY DATE_FORMAT(d.full_date,'%Y-%m-01') ORDER BY month_start""",
            (product_id,),
        )
        forecast = query_df(
            """SELECT forecast_month, model_name, predicted_units, mae, mape
                 FROM retail_dw.demand_forecast WHERE product_id=%s ORDER BY forecast_month DESC, model_name""",
            (product_id,),
        )
        if not history.empty and not forecast.empty:
            actual = history.copy()
            actual["series"] = "Actual"
            predicted = forecast.rename(columns={"forecast_month": "month_start", "predicted_units": "units"})
            predicted = predicted.rename(columns={"model_name": "series"})[["month_start", "series", "units"]]
            chart = pd.concat([actual[["month_start", "series", "units"]], predicted], ignore_index=True)
            st.plotly_chart(px.line(chart, x="month_start", y="units", color="series", markers=True), use_container_width=True)
            st.subheader("Model errors and next-month predictions")
            st.dataframe(forecast, use_container_width=True, hide_index=True)
        else:
            st.info("No stored forecast is available for this product yet. Run python/forecast.py.")
    except Exception as exc:
        show_database_error(exc)


def _audit() -> None:
    st.header("Audit log")
    try:
        audit = query_df(
            """SELECT id, table_name, action, record_id, old_value, new_value, changed_at
                 FROM audit_log ORDER BY changed_at DESC LIMIT 500"""
        )
        st.dataframe(audit, use_container_width=True, hide_index=True)
    except Exception as exc:
        show_database_error(exc)


{
    "Dashboard": _dashboard,
    "Inventory": _inventory,
    "Sales": _sales,
    "Purchasing": _purchasing,
    "Forecast": _forecast,
    "Audit log": _audit,
}[page]()

