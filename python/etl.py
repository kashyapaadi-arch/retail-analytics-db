"""Extract retail sales, transform with pandas, and idempotently load retail_dw."""

from __future__ import annotations

import os
import re
from pathlib import Path

import mysql.connector
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "sql" / "warehouse.sql"


def _config() -> dict[str, str | int]:
    load_dotenv(ROOT / ".env")
    required = ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"Missing database settings: {', '.join(missing)}")
    return {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", ""),
        "password": os.getenv("DB_PASSWORD", ""),
        "source_db": os.getenv("DB_NAME", "retail_db"),
        "dw_db": os.getenv("DW_NAME", "retail_dw"),
    }


def _engine(config: dict, database: str):
    return create_engine(
        URL.create(
            "mysql+pymysql",
            username=config["user"],
            password=config["password"],
            host=config["host"],
            port=config["port"],
            database=database,
            query={"charset": "utf8mb4"},
        ),
        pool_pre_ping=True,
    )


def _ensure_dw(config: dict) -> None:
    name = str(config["dw_db"])
    if not name.replace("_", "").isalnum():
        raise ValueError("DW_NAME may contain only letters, digits, and underscores")
    server = mysql.connector.connect(
        host=config["host"], port=config["port"], user=config["user"], password=config["password"]
    )
    try:
        cur = server.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        cur.close()
    finally:
        server.close()

    engine = _engine(config, name)
    try:
        schema_sql = re.sub(r"(?m)^\s*--.*$", "", SCHEMA_PATH.read_text(encoding="utf-8"))
        statements = [part.strip() for part in schema_sql.split(";")]
        with engine.begin() as connection:
            for statement in statements:
                if not statement or statement.upper().startswith(("CREATE DATABASE", "USE ")):
                    continue
                connection.exec_driver_sql(statement)
    finally:
        engine.dispose()


def _upsert(engine, sql: str, rows: list[tuple]) -> None:
    if not rows:
        return
    raw = engine.raw_connection()
    try:
        cursor = raw.cursor()
        cursor.executemany(sql, rows)
        raw.commit()
        cursor.close()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()


def _lookup(engine, query: str, natural_column: str, key_column: str) -> dict:
    result = pd.read_sql_query(text(query), engine)
    return dict(zip(result[natural_column], result[key_column]))


def run_etl() -> dict[str, object]:
    config = _config()
    _ensure_dw(config)
    source = _engine(config, str(config["source_db"]))
    destination = _engine(config, str(config["dw_db"]))
    try:
        products = pd.read_sql_query(
            """SELECT p.product_id, p.name AS product_name, p.category_id,
                      c.name AS category_name, p.unit_price, p.cost_price
                 FROM product AS p JOIN category AS c ON c.category_id = p.category_id""",
            source,
        )
        customers = pd.read_sql_query(
            "SELECT customer_id, name AS customer_name, city FROM customer", source
        )
        employees = pd.read_sql_query(
            "SELECT employee_id, name AS employee_name, role FROM employee", source
        )
        sales = pd.read_sql_query(
            """SELECT so.order_id, oi.product_id, DATE(so.order_date) AS sales_date,
                      so.customer_id, so.employee_id, oi.quantity,
                      ROUND(oi.quantity * oi.unit_price, 2) AS gross_amount,
                      ROUND(oi.quantity * oi.unit_price * (1 - oi.discount_pct / 100), 2) AS net_amount,
                      ROUND(oi.quantity * p.cost_price, 2) AS cost_amount
                 FROM sales_order AS so
                 JOIN order_item AS oi ON oi.order_id = so.order_id
                 JOIN product AS p ON p.product_id = oi.product_id""",
            source,
        )

        _upsert(destination,
                """INSERT INTO dim_product (product_id, product_name, category_id, category_name, unit_price, cost_price)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   ON DUPLICATE KEY UPDATE product_name=VALUES(product_name), category_id=VALUES(category_id),
                     category_name=VALUES(category_name), unit_price=VALUES(unit_price), cost_price=VALUES(cost_price)""",
                list(products[["product_id", "product_name", "category_id", "category_name", "unit_price", "cost_price"]].itertuples(index=False, name=None)))
        _upsert(destination,
                """INSERT INTO dim_customer (customer_id, customer_name, city) VALUES (%s, %s, %s)
                   ON DUPLICATE KEY UPDATE customer_name=VALUES(customer_name), city=VALUES(city)""",
                list(customers[["customer_id", "customer_name", "city"]].itertuples(index=False, name=None)))
        _upsert(destination,
                """INSERT INTO dim_employee (employee_id, employee_name, role) VALUES (%s, %s, %s)
                   ON DUPLICATE KEY UPDATE employee_name=VALUES(employee_name), role=VALUES(role)""",
                list(employees[["employee_id", "employee_name", "role"]].itertuples(index=False, name=None)))

        sales["sales_date"] = pd.to_datetime(sales["sales_date"]).dt.date
        if not sales.empty:
            days = pd.date_range(sales["sales_date"].min(), sales["sales_date"].max(), freq="D")
            date_rows = [
                (int(day.strftime("%Y%m%d")), day.date(), day.day, day.month, day.strftime("%B"),
                 (day.month - 1) // 3 + 1, day.year, day.strftime("%A"))
                for day in days
            ]
            _upsert(destination,
                    """INSERT INTO dim_date (date_key, full_date, day_of_month, month_number, month_name, quarter_number, year_number, weekday_name)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                       ON DUPLICATE KEY UPDATE full_date=VALUES(full_date), day_of_month=VALUES(day_of_month),
                         month_number=VALUES(month_number), month_name=VALUES(month_name), quarter_number=VALUES(quarter_number),
                         year_number=VALUES(year_number), weekday_name=VALUES(weekday_name)""",
                    date_rows)

            product_keys = _lookup(destination, "SELECT product_id, product_key FROM dim_product", "product_id", "product_key")
            customer_keys = _lookup(destination, "SELECT customer_id, customer_key FROM dim_customer", "customer_id", "customer_key")
            employee_keys = _lookup(destination, "SELECT employee_id, employee_key FROM dim_employee", "employee_id", "employee_key")
            sales["date_key"] = sales["sales_date"].map(lambda value: int(value.strftime("%Y%m%d")))
            sales["product_key"] = sales["product_id"].map(product_keys)
            sales["customer_key"] = sales["customer_id"].map(customer_keys)
            sales["employee_key"] = sales["employee_id"].map(employee_keys)
            sales["discount_amount"] = sales["gross_amount"] - sales["net_amount"]
            sales["profit"] = sales["net_amount"] - sales["cost_amount"]
            fact_columns = ["order_id", "product_id", "date_key", "product_key", "customer_key", "employee_key",
                            "quantity", "gross_amount", "discount_amount", "net_amount", "cost_amount", "profit"]
            fact_sql = """INSERT INTO fact_sales
                (order_id, product_id, date_key, product_key, customer_key, employee_key, quantity,
                 gross_amount, discount_amount, net_amount, cost_amount, profit)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON DUPLICATE KEY UPDATE date_key=VALUES(date_key), product_key=VALUES(product_key),
                 customer_key=VALUES(customer_key), employee_key=VALUES(employee_key), quantity=VALUES(quantity),
                 gross_amount=VALUES(gross_amount), discount_amount=VALUES(discount_amount), net_amount=VALUES(net_amount),
                 cost_amount=VALUES(cost_amount), profit=VALUES(profit)"""
            _upsert(destination, fact_sql, list(sales[fact_columns].itertuples(index=False, name=None)))

        with destination.connect() as dw_conn:
            fact_total = dw_conn.execute(text("SELECT COALESCE(SUM(net_amount), 0) FROM fact_sales")).scalar_one()
        with source.connect() as source_conn:
            order_total = source_conn.execute(text("SELECT COALESCE(SUM(total_amount), 0) FROM sales_order")).scalar_one()
        if fact_total != order_total:
            raise AssertionError(f"ETL reconciliation failed: fact net={fact_total}, sales order total={order_total}")

        with destination.connect() as conn:
            fact_count = conn.execute(text("SELECT COUNT(*) FROM fact_sales")).scalar_one()
        return {"fact_rows": int(fact_count), "fact_net_amount": str(fact_total), "order_total_amount": str(order_total), "reconciled": True}
    finally:
        source.dispose()
        destination.dispose()


def main() -> None:
    print(run_etl())


if __name__ == "__main__":
    main()

