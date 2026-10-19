-- Supporting audit, price-history, and stock-alert tables plus reporting indexes.
-- Run after schema.sql. Safe to rerun on MySQL 8.0.
USE retail_db;

CREATE TABLE IF NOT EXISTS price_history (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    product_id INT UNSIGNED NOT NULL,
    price DECIMAL(10, 2) NOT NULL,
    valid_from DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    valid_to DATETIME NULL,
    CONSTRAINT pk_price_history PRIMARY KEY (id),
    CONSTRAINT fk_price_history_product FOREIGN KEY (product_id)
        REFERENCES product (product_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT chk_price_history_price CHECK (price > 0),
    CONSTRAINT chk_price_history_period CHECK (valid_to IS NULL OR valid_to > valid_from),
    INDEX idx_price_history_product_period (product_id, valid_from, valid_to)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    table_name VARCHAR(64) NOT NULL,
    action ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    record_id VARCHAR(128) NOT NULL,
    old_value JSON NULL,
    new_value JSON NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_audit_log PRIMARY KEY (id),
    INDEX idx_audit_log_table_record (table_name, record_id),
    INDEX idx_audit_log_changed_at (changed_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS stock_alert (
    alert_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    product_id INT UNSIGNED NOT NULL,
    quantity INT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_stock_alert PRIMARY KEY (alert_id),
    CONSTRAINT fk_stock_alert_product FOREIGN KEY (product_id)
        REFERENCES product (product_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT chk_stock_alert_quantity CHECK (quantity >= 0),
    INDEX idx_stock_alert_product_created (product_id, created_at),
    INDEX idx_stock_alert_created (created_at)
) ENGINE=InnoDB;

-- Indexes used by date and customer reporting. The product-line index is defined
-- with order_item in schema.sql to avoid duplicate indexes on a fresh install.
SET @ddl_order_date = IF(
    (SELECT COUNT(*) FROM information_schema.statistics
     WHERE table_schema = DATABASE() AND table_name = 'sales_order'
       AND index_name = 'idx_order_date') = 0,
    'CREATE INDEX idx_order_date ON sales_order (order_date)',
    'SELECT 1'
);
PREPARE stmt_order_date FROM @ddl_order_date;
EXECUTE stmt_order_date;
DEALLOCATE PREPARE stmt_order_date;

