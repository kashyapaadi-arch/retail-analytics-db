"""Load deterministic sample data into a freshly initialized retail_db."""

from __future__ import annotations

import os
import random
from datetime import datetime, timedelta
from decimal import Decimal

import mysql.connector
from dotenv import load_dotenv
from faker import Faker


SEED = 20261019
ORDER_COUNT = 2_000
CORE_TABLES = (
    "price_history",
    "audit_log",
    "stock_alert",
    "order_item",
    "sales_order",
    "purchase_order_item",
    "purchase_order",
    "supplier_product",
    "inventory",
    "product",
    "employee",
    "customer",
    "supplier",
    "category",
)

CATEGORIES = {
    "Groceries": [
        ("Basmati Rice 5 kg", 690, 540), ("Toor Dal 1 kg", 158, 118),
        ("Sunflower Oil 1 L", 145, 112), ("Wheat Flour 5 kg", 275, 210),
        ("Masala Tea 500 g", 245, 180), ("Jaggery Powder 1 kg", 115, 82),
        ("Red Chilli Powder 200 g", 92, 61),
    ],
    "Dairy and Bakery": [
        ("Toned Milk 1 L", 68, 54), ("Paneer 200 g", 105, 78),
        ("Fresh Curd 500 g", 52, 37), ("Salted Butter 100 g", 62, 45),
        ("Brown Bread 400 g", 55, 39), ("Cheese Slices 200 g", 128, 96),
        ("Ghee 500 ml", 345, 270),
    ],
    "Personal Care": [
        ("Neem Face Wash 150 ml", 185, 132), ("Herbal Shampoo 340 ml", 299, 215),
        ("Coconut Hair Oil 200 ml", 125, 88), ("Aloe Moisturizer 100 ml", 210, 151),
        ("Mint Toothpaste 150 g", 105, 72), ("Bath Soap 4 Pack", 145, 99),
        ("SPF 50 Sunscreen 50 ml", 399, 295),
    ],
    "Home and Kitchen": [
        ("Stainless Steel Bottle 1 L", 349, 228), ("Cotton Bath Towel", 499, 330),
        ("Non-stick Fry Pan 24 cm", 899, 620), ("Storage Container Set", 579, 390),
        ("LED Bulb 9 W", 99, 58), ("Kitchen Knife Set", 429, 290),
        ("Microfiber Floor Mop", 699, 480),
    ],
    "Electronics": [
        ("USB-C Cable 1 m", 249, 125), ("Wireless Mouse", 699, 420),
        ("Bluetooth Earbuds", 1799, 1180), ("Power Bank 10000 mAh", 1499, 980),
        ("Fast Charger 20 W", 799, 490), ("Smart LED Strip 5 m", 1099, 740),
        ("Fitness Band", 2299, 1580),
    ],
    "Apparel": [
        ("Cotton Kurta", 899, 530), ("Classic Polo T-shirt", 649, 390),
        ("Denim Jeans", 1499, 940), ("Cotton Leggings", 399, 235),
        ("Printed Dupatta", 499, 280), ("Running Socks 3 Pack", 299, 160),
        ("Canvas Tote Bag", 349, 190),
    ],
}

SUPPLIERS = [
    ("Aarav Wholesale", "Mumbai"), ("Bharat Trade Links", "Delhi"),
    ("Cauvery Distributors", "Bengaluru"), ("Deccan Supply Co.", "Hyderabad"),
    ("Eastern Bazaar Supplies", "Kolkata"), ("Ganga Merchants", "Lucknow"),
    ("Himalaya Retail Supply", "Chandigarh"), ("Indus General Traders", "Jaipur"),
    ("Jai Hind Distributors", "Pune"), ("Konkan Wholesale", "Ahmedabad"),
]


def connect():
    load_dotenv()
    required = ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(f"Missing database settings: {', '.join(missing)}")
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "retail_db"),
        charset="utf8mb4",
    )


def require_empty_database(cursor) -> None:
    counts = {}
    for table in CORE_TABLES:
        cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
        counts[table] = cursor.fetchone()[0]
    nonempty = {table: count for table, count in counts.items() if count}
    if nonempty:
        details = ", ".join(f"{table}={count}" for table, count in nonempty.items())
        raise RuntimeError(f"Refusing to seed a database that already contains data ({details}).")


def main() -> None:
    random.seed(SEED)
    fake = Faker("en_IN")
    Faker.seed(SEED)
    connection = connect()
    try:
        cursor = connection.cursor()
        require_empty_database(cursor)

        category_ids = {}
        cursor.executemany("INSERT INTO category (name) VALUES (%s)", [(name,) for name in CATEGORIES])
        cursor.execute("SELECT category_id, name FROM category")
        category_ids = {name: category_id for category_id, name in cursor.fetchall()}

        cursor.executemany(
            "INSERT INTO supplier (name, contact, city) VALUES (%s, %s, %s)",
            [(name, f"+91-{random.randint(7000, 9999)}-{random.randint(100000, 999999)}", city)
             for name, city in SUPPLIERS],
        )
        cursor.execute("SELECT supplier_id FROM supplier ORDER BY supplier_id")
        supplier_ids = [row[0] for row in cursor.fetchall()]

        roles = ["admin"] + ["inventory_manager"] * 2 + ["sales_staff"] * 5
        employees = [
            (fake.name(), role, fake.date_between(start_date="-8y", end_date="today"))
            for role in roles
        ]
        cursor.executemany(
            "INSERT INTO employee (name, role, hire_date) VALUES (%s, %s, %s)", employees
        )
        cursor.execute("SELECT employee_id, role FROM employee ORDER BY employee_id")
        employee_rows = cursor.fetchall()
        sales_employee_ids = [employee_id for employee_id, role in employee_rows if role == "sales_staff"]

        customers = []
        used_phones = set()
        for i in range(300):
            phone = f"+91{7000000000 + i:010d}"
            if phone in used_phones:
                raise AssertionError("Deterministic customer phone collision")
            used_phones.add(phone)
            customers.append((fake.name(), phone, fake.city(), fake.date_between(start_date="-5y", end_date="today")))
        cursor.executemany(
            "INSERT INTO customer (name, phone, city, join_date) VALUES (%s, %s, %s, %s)",
            customers,
        )
        cursor.execute("SELECT customer_id FROM customer ORDER BY customer_id")
        customer_ids = [row[0] for row in cursor.fetchall()]

        product_values = []
        supplier_product_values = []
        for category_name, products in CATEGORIES.items():
            for name, unit_price, cost_price in products:
                product_values.append((name, category_ids[category_name], Decimal(unit_price), Decimal(cost_price), 10))
        cursor.executemany(
            """INSERT INTO product (name, category_id, unit_price, cost_price, reorder_level)
               VALUES (%s, %s, %s, %s, %s)""",
            product_values,
        )
        cursor.execute("SELECT product_id, cost_price FROM product ORDER BY product_id")
        product_rows = cursor.fetchall()
        product_ids = [product_id for product_id, _ in product_rows]

        # Each product has two supplier offers. The product trigger creates each
        # inventory row and initial price-history version; no support rows are inserted here.
        supplier_offer_rows = []
        for index, (product_id, cost_price) in enumerate(product_rows):
            supplier_a = supplier_ids[index % len(supplier_ids)]
            supplier_b = supplier_ids[(index + 5) % len(supplier_ids)]
            for supplier_id, factor in ((supplier_a, Decimal("0.96")), (supplier_b, Decimal("1.02"))):
                supply_price = (cost_price * factor).quantize(Decimal("0.01"))
                supplier_offer_rows.append((supplier_id, product_id, supply_price))
        cursor.executemany(
            "INSERT INTO supplier_product (supplier_id, product_id, supply_price) VALUES (%s, %s, %s)",
            supplier_offer_rows,
        )

        # A high opening balance lets the sales history load without synthetic
        # manual order totals. The order-item trigger decrements this stock.
        cursor.execute("UPDATE inventory SET quantity_in_stock = 100000")

        now = datetime.now().replace(microsecond=0)
        day_weights = [1 + (540 - day) / 270 for day in range(540)]
        order_items = []
        for _ in range(ORDER_COUNT):
            days_ago = random.choices(range(540), weights=day_weights, k=1)[0]
            order_date = now - timedelta(days=days_ago, seconds=random.randint(0, 86399))
            customer_id = random.choice(customer_ids)
            employee_id = random.choice(sales_employee_ids)
            payment_mode = random.choice(("cash", "card", "upi"))
            cursor.execute(
                """INSERT INTO sales_order (customer_id, employee_id, order_date, payment_mode)
                   VALUES (%s, %s, %s, %s)""",
                (customer_id, employee_id, order_date, payment_mode),
            )
            order_id = cursor.lastrowid
            line_count = random.randint(1, 4)
            for product_id in random.sample(product_ids, line_count):
                quantity = random.randint(1, 5)
                discount = random.choice((0, 0, 0, 5, 10))
                order_items.append((order_id, product_id, quantity, discount))

        # The trigger uses the captured product price and updates order totals.
        cursor.executemany(
            """INSERT INTO order_item (order_id, product_id, quantity, unit_price, discount_pct)
               SELECT %s, %s, %s, unit_price, %s FROM product WHERE product_id = %s""",
            [
                (order_id, product_id, quantity, discount, product_id)
                for order_id, product_id, quantity, discount in order_items
            ],
        )

        # Leave realistic closing stock; the inventory trigger records threshold crossings.
        for product_id in product_ids:
            cursor.execute(
                "UPDATE inventory SET quantity_in_stock = %s WHERE product_id = %s",
                (random.randint(0, 149), product_id),
            )
        connection.commit()

        print("Seed complete:")
        for table in ("category", "supplier", "employee", "customer", "product", "inventory", "supplier_product", "sales_order", "order_item", "price_history", "stock_alert"):
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
            print(f"  {table}: {cursor.fetchone()[0]}")
        cursor.close()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


if __name__ == "__main__":
    main()

