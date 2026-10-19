-- Sales and Inventory Analytics Database: core transactional schema
-- Target: MySQL Server 8.0. Run with an account allowed to create databases.

CREATE DATABASE IF NOT EXISTS retail_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;
USE retail_db;

CREATE TABLE IF NOT EXISTS category (
    category_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(100) NOT NULL,
    CONSTRAINT pk_category PRIMARY KEY (category_id),
    CONSTRAINT uq_category_name UNIQUE (name)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS supplier (
    supplier_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(150) NOT NULL,
    contact VARCHAR(100) NULL,
    city VARCHAR(100) NULL,
    CONSTRAINT pk_supplier PRIMARY KEY (supplier_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS customer (
    customer_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(150) NOT NULL,
    phone VARCHAR(20) NULL,
    city VARCHAR(100) NULL,
    join_date DATE NOT NULL,
    CONSTRAINT pk_customer PRIMARY KEY (customer_id),
    CONSTRAINT uq_customer_phone UNIQUE (phone)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS employee (
    employee_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(150) NOT NULL,
    role ENUM('admin', 'inventory_manager', 'sales_staff') NOT NULL,
    hire_date DATE NOT NULL,
    CONSTRAINT pk_employee PRIMARY KEY (employee_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS product (
    product_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    name VARCHAR(180) NOT NULL,
    category_id INT UNSIGNED NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    cost_price DECIMAL(10, 2) NOT NULL,
    reorder_level INT NOT NULL DEFAULT 10,
    CONSTRAINT pk_product PRIMARY KEY (product_id),
    CONSTRAINT fk_product_category FOREIGN KEY (category_id)
        REFERENCES category (category_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_product_unit_price CHECK (unit_price > 0),
    CONSTRAINT chk_product_cost_price CHECK (cost_price > 0),
    CONSTRAINT chk_product_reorder_level CHECK (reorder_level >= 0),
    INDEX idx_product_category (category_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS inventory (
    product_id INT UNSIGNED NOT NULL,
    quantity_in_stock INT NOT NULL DEFAULT 0,
    last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT pk_inventory PRIMARY KEY (product_id),
    CONSTRAINT fk_inventory_product FOREIGN KEY (product_id)
        REFERENCES product (product_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT chk_inventory_quantity CHECK (quantity_in_stock >= 0)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS supplier_product (
    supplier_id INT UNSIGNED NOT NULL,
    product_id INT UNSIGNED NOT NULL,
    supply_price DECIMAL(10, 2) NOT NULL,
    CONSTRAINT pk_supplier_product PRIMARY KEY (supplier_id, product_id),
    CONSTRAINT fk_supplier_product_supplier FOREIGN KEY (supplier_id)
        REFERENCES supplier (supplier_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_supplier_product_product FOREIGN KEY (product_id)
        REFERENCES product (product_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT chk_supplier_product_supply_price CHECK (supply_price > 0),
    INDEX idx_supplier_product_product (product_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS purchase_order (
    po_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    supplier_id INT UNSIGNED NOT NULL,
    order_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status ENUM('PENDING', 'RECEIVED') NOT NULL DEFAULT 'PENDING',
    CONSTRAINT pk_purchase_order PRIMARY KEY (po_id),
    CONSTRAINT fk_purchase_order_supplier FOREIGN KEY (supplier_id)
        REFERENCES supplier (supplier_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    INDEX idx_purchase_order_supplier (supplier_id),
    INDEX idx_purchase_order_status_date (status, order_date)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS purchase_order_item (
    po_id INT UNSIGNED NOT NULL,
    product_id INT UNSIGNED NOT NULL,
    quantity INT NOT NULL,
    unit_cost DECIMAL(10, 2) NOT NULL,
    CONSTRAINT pk_purchase_order_item PRIMARY KEY (po_id, product_id),
    CONSTRAINT fk_purchase_order_item_order FOREIGN KEY (po_id)
        REFERENCES purchase_order (po_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_purchase_order_item_product FOREIGN KEY (product_id)
        REFERENCES product (product_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_purchase_order_item_quantity CHECK (quantity > 0),
    CONSTRAINT chk_purchase_order_item_unit_cost CHECK (unit_cost > 0),
    INDEX idx_purchase_order_item_product (product_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sales_order (
    order_id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    customer_id INT UNSIGNED NOT NULL,
    employee_id INT UNSIGNED NOT NULL,
    order_date DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payment_mode ENUM('cash', 'card', 'upi') NOT NULL,
    total_amount DECIMAL(12, 2) NOT NULL DEFAULT 0.00,
    CONSTRAINT pk_sales_order PRIMARY KEY (order_id),
    CONSTRAINT fk_sales_order_customer FOREIGN KEY (customer_id)
        REFERENCES customer (customer_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT fk_sales_order_employee FOREIGN KEY (employee_id)
        REFERENCES employee (employee_id)
        ON UPDATE CASCADE ON DELETE RESTRICT
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS order_item (
    order_id INT UNSIGNED NOT NULL,
    product_id INT UNSIGNED NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    discount_pct DECIMAL(5, 2) NOT NULL DEFAULT 0.00,
    CONSTRAINT pk_order_item PRIMARY KEY (order_id, product_id),
    CONSTRAINT fk_order_item_order FOREIGN KEY (order_id)
        REFERENCES sales_order (order_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT fk_order_item_product FOREIGN KEY (product_id)
        REFERENCES product (product_id)
        ON UPDATE CASCADE ON DELETE RESTRICT,
    CONSTRAINT chk_order_item_quantity CHECK (quantity > 0),
    CONSTRAINT chk_order_item_unit_price CHECK (unit_price > 0),
    CONSTRAINT chk_order_item_discount CHECK (discount_pct BETWEEN 0 AND 100),
    INDEX idx_order_item_product (product_id)
) ENGINE=InnoDB;

-- The product trigger in triggers_procedures.sql creates the associated inventory
-- row after each product insert. Do not seed inventory rows directly.

