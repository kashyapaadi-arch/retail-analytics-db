from __future__ import annotations

from datetime import date
from decimal import Decimal

import mysql.connector
import pytest


def _category(cursor, name):
    cursor.execute("INSERT INTO category (name) VALUES (%s)", (name,))
    return cursor.lastrowid


def _product(cursor, suffix, stock=0, reorder=10):
    category_id = _category(cursor, f"Test category {suffix}")
    cursor.execute(
        "INSERT INTO product (name,category_id,unit_price,cost_price,reorder_level) VALUES (%s,%s,100.00,60.00,%s)",
        (f"Test product {suffix}", category_id, reorder),
    )
    product_id = cursor.lastrowid
    if stock:
        cursor.execute("UPDATE inventory SET quantity_in_stock=%s WHERE product_id=%s", (stock, product_id))
    return product_id


def _customer_employee(cursor, suffix):
    cursor.execute(
        "INSERT INTO customer (name,phone,city,join_date) VALUES (%s,%s,%s,%s)",
        (f"Test customer {suffix}", f"+91990000{suffix:04d}", "Jaipur", date.today()),
    )
    customer_id = cursor.lastrowid
    cursor.execute(
        "INSERT INTO employee (name,role,hire_date) VALUES (%s,'sales_staff',%s)",
        (f"Test employee {suffix}", date.today()),
    )
    return customer_id, cursor.lastrowid


def test_duplicate_foreign_key_and_check_constraints(connection):
    cursor = connection.cursor()
    category_id = _category(cursor, "Unique category")
    with pytest.raises(mysql.connector.Error):
        cursor.execute("INSERT INTO category (name) VALUES ('Unique category')")
    with pytest.raises(mysql.connector.Error):
        cursor.execute("INSERT INTO product (name,category_id,unit_price,cost_price) VALUES ('Bad FK',999999,10,5)")
    with pytest.raises(mysql.connector.Error):
        cursor.execute("INSERT INTO product (name,category_id,unit_price,cost_price) VALUES ('Bad CHECK',%s,0,5)", (category_id,))


def test_product_insert_and_price_update_triggers(connection):
    cursor = connection.cursor()
    product_id = _product(cursor, 101)
    cursor.execute("SELECT quantity_in_stock FROM inventory WHERE product_id=%s", (product_id,))
    assert cursor.fetchone()[0] == 0
    cursor.execute("SELECT price,valid_to FROM price_history WHERE product_id=%s", (product_id,))
    assert cursor.fetchone() == (Decimal("100.00"), None)

    cursor.execute("UPDATE product SET unit_price=125.00 WHERE product_id=%s", (product_id,))
    cursor.execute("SELECT price,valid_to FROM price_history WHERE product_id=%s ORDER BY id", (product_id,))
    history = cursor.fetchall()
    assert len(history) == 2
    assert history[0][0] == Decimal("100.00") and history[0][1] is not None
    assert history[1][0] == Decimal("125.00") and history[1][1] is None
    cursor.execute("SELECT COUNT(*) FROM audit_log WHERE table_name='product' AND record_id=%s", (str(product_id),))
    assert cursor.fetchone()[0] == 1


def test_order_item_and_inventory_alert_triggers(connection):
    cursor = connection.cursor()
    product_id = _product(cursor, 102)
    cursor.execute("UPDATE inventory SET quantity_in_stock=20 WHERE product_id=%s", (product_id,))
    customer_id, employee_id = _customer_employee(cursor, 102)
    cursor.execute("INSERT INTO sales_order (customer_id,employee_id,payment_mode) VALUES (%s,%s,'cash')", (customer_id, employee_id))
    order_id = cursor.lastrowid
    cursor.execute("INSERT INTO order_item (order_id,product_id,quantity,unit_price,discount_pct) VALUES (%s,%s,3,100,10)", (order_id, product_id))
    cursor.execute("SELECT quantity_in_stock FROM inventory WHERE product_id=%s", (product_id,))
    assert cursor.fetchone()[0] == 17
    cursor.execute("SELECT total_amount FROM sales_order WHERE order_id=%s", (order_id,))
    assert cursor.fetchone()[0] == Decimal("270.00")

    cursor.execute("UPDATE inventory SET quantity_in_stock=10 WHERE product_id=%s", (product_id,))
    cursor.execute("UPDATE inventory SET quantity_in_stock=9 WHERE product_id=%s", (product_id,))
    cursor.execute("SELECT quantity FROM stock_alert WHERE product_id=%s", (product_id,))
    assert cursor.fetchall() == [(9,)]


def test_place_order_success_and_rollback_on_insufficient_stock(connection):
    cursor = connection.cursor()
    product_id = _product(cursor, 103, stock=5)
    customer_id, employee_id = _customer_employee(cursor, 103)
    result = cursor.callproc("place_order", [customer_id, employee_id, product_id, 2, 5.0, "upi", 0])
    order_id = result[-1]
    cursor.execute("SELECT total_amount FROM sales_order WHERE order_id=%s", (order_id,))
    assert cursor.fetchone()[0] == Decimal("190.00")
    cursor.execute("SELECT quantity_in_stock FROM inventory WHERE product_id=%s", (product_id,))
    assert cursor.fetchone()[0] == 3

    cursor.execute("SELECT COUNT(*) FROM sales_order")
    before_count = cursor.fetchone()[0]
    with pytest.raises(mysql.connector.Error, match="Insufficient stock"):
        cursor.callproc("place_order", [customer_id, employee_id, product_id, 4, 0, "cash", 0])
    cursor.execute("SELECT COUNT(*) FROM sales_order")
    assert cursor.fetchone()[0] == before_count
    cursor.execute("SELECT quantity_in_stock FROM inventory WHERE product_id=%s", (product_id,))
    assert cursor.fetchone()[0] == 3


def test_receive_purchase_order_and_reject_double_receive(connection):
    cursor = connection.cursor()
    supplier_id = None
    cursor.execute("INSERT INTO supplier (name,city) VALUES ('Test supplier 104','Jaipur')")
    supplier_id = cursor.lastrowid
    product_id = _product(cursor, 104)
    cursor.execute("INSERT INTO purchase_order (supplier_id) VALUES (%s)", (supplier_id,))
    po_id = cursor.lastrowid
    cursor.execute("INSERT INTO purchase_order_item (po_id,product_id,quantity,unit_cost) VALUES (%s,%s,7,55)", (po_id, product_id))
    cursor.callproc("receive_purchase_order", [po_id])
    cursor.execute("SELECT status FROM purchase_order WHERE po_id=%s", (po_id,))
    assert cursor.fetchone()[0] == "RECEIVED"
    cursor.execute("SELECT quantity_in_stock FROM inventory WHERE product_id=%s", (product_id,))
    assert cursor.fetchone()[0] == 7
    with pytest.raises(mysql.connector.Error, match="Purchase order already received"):
        cursor.callproc("receive_purchase_order", [po_id])
    cursor.execute("SELECT quantity_in_stock FROM inventory WHERE product_id=%s", (product_id,))
    assert cursor.fetchone()[0] == 7


def test_views_return_expected_rows(connection):
    cursor = connection.cursor()
    product_id = _product(cursor, 105, stock=1, reorder=10)
    customer_id, employee_id = _customer_employee(cursor, 105)
    cursor.execute("INSERT INTO sales_order (customer_id,employee_id,payment_mode) VALUES (%s,%s,'card')", (customer_id, employee_id))
    order_id = cursor.lastrowid
    cursor.execute("INSERT INTO order_item (order_id,product_id,quantity,unit_price,discount_pct) VALUES (%s,%s,1,100,0)", (order_id, product_id))
    cursor.execute("SELECT orders,revenue FROM monthly_sales_summary WHERE `month`=CAST(DATE_FORMAT(CURRENT_DATE,'%Y-%m-01') AS DATE)")
    row = cursor.fetchone()
    assert row is not None and row[0] >= 1 and row[1] >= Decimal("100.00")
    cursor.execute("SELECT COUNT(*) FROM low_stock_products WHERE product_id=%s", (product_id,))
    assert cursor.fetchone()[0] == 1
    cursor.execute("SELECT abc_class FROM abc_classification WHERE product_id=%s", (product_id,))
    assert cursor.fetchone()[0] in {"A", "B", "C"}


def test_etl_reconciliation_and_forecast_sanity(connection):
    cursor = connection.cursor()
    product_id = _product(cursor, 106)
    cursor.execute("UPDATE inventory SET quantity_in_stock=100 WHERE product_id=%s", (product_id,))
    customer_id, employee_id = _customer_employee(cursor, 106)
    for month_offset in range(10):
        cursor.execute(
            "INSERT INTO sales_order (customer_id,employee_id,order_date,payment_mode) VALUES (%s,%s,DATE_SUB(CURRENT_DATE,INTERVAL %s MONTH),'cash')",
            (customer_id, employee_id, 9 - month_offset),
        )
        order_id = cursor.lastrowid
        cursor.execute("INSERT INTO order_item (order_id,product_id,quantity,unit_price,discount_pct) VALUES (%s,%s,%s,100,0)", (order_id, product_id, month_offset + 1))

    from etl import run_etl
    from forecast import evaluate_series, run_forecast

    result = run_etl()
    assert result["reconciled"] is True
    assert result["fact_rows"] >= 10
    report = evaluate_series([3, 4, 4, 5, 7, 8, 9, 10, 12, 13])
    assert report["moving_average"]["mae"] >= 0
    assert report["linear_regression"]["mae"] >= 0
    assert report["moving_average"]["prediction"] >= 0
    assert report["linear_regression"]["prediction"] >= 0
    forecast_result = run_forecast(draft_orders=False)
    assert forecast_result["forecast_month"] is not None
    assert len(forecast_result["product_model_metrics"]) >= 2
    cursor.execute("SELECT COUNT(*) FROM retail_dw_test.demand_forecast WHERE product_id=%s", (product_id,))
    assert cursor.fetchone()[0] == 2

