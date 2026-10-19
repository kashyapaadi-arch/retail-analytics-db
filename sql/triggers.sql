-- Triggers for product history, audit, sales totals, stock, and low-stock alerts.
-- Run after schema.sql and support_tables.sql.
USE retail_db;

DROP TRIGGER IF EXISTS trg_product_after_insert;
DROP TRIGGER IF EXISTS trg_product_after_update;
DROP TRIGGER IF EXISTS trg_orderitem_after_insert;
DROP TRIGGER IF EXISTS trg_inventory_after_update;

DELIMITER $$

CREATE TRIGGER trg_product_after_insert
AFTER INSERT ON product
FOR EACH ROW
BEGIN
    INSERT INTO inventory (product_id, quantity_in_stock)
    VALUES (NEW.product_id, 0);

    INSERT INTO price_history (product_id, price, valid_from, valid_to)
    VALUES (NEW.product_id, NEW.unit_price, CURRENT_TIMESTAMP, NULL);
END$$

CREATE TRIGGER trg_product_after_update
AFTER UPDATE ON product
FOR EACH ROW
BEGIN
    IF NEW.unit_price <> OLD.unit_price THEN
        UPDATE price_history
           SET valid_to = CURRENT_TIMESTAMP
         WHERE product_id = NEW.product_id
           AND valid_to IS NULL;

        INSERT INTO price_history (product_id, price, valid_from, valid_to)
        VALUES (NEW.product_id, NEW.unit_price, CURRENT_TIMESTAMP, NULL);

        INSERT INTO audit_log (table_name, action, record_id, old_value, new_value)
        VALUES (
            'product',
            'UPDATE',
            CAST(NEW.product_id AS CHAR),
            JSON_OBJECT('unit_price', OLD.unit_price),
            JSON_OBJECT('unit_price', NEW.unit_price)
        );
    END IF;
END$$

CREATE TRIGGER trg_orderitem_after_insert
AFTER INSERT ON order_item
FOR EACH ROW
BEGIN
    UPDATE inventory
       SET quantity_in_stock = quantity_in_stock - NEW.quantity
     WHERE product_id = NEW.product_id;

    UPDATE sales_order
       SET total_amount = total_amount
           + ROUND(NEW.quantity * NEW.unit_price * (1 - NEW.discount_pct / 100), 2)
     WHERE order_id = NEW.order_id;
END$$

CREATE TRIGGER trg_inventory_after_update
AFTER UPDATE ON inventory
FOR EACH ROW
BEGIN
    IF OLD.quantity_in_stock >= (
           SELECT reorder_level FROM product WHERE product_id = NEW.product_id
       )
       AND NEW.quantity_in_stock < (
           SELECT reorder_level FROM product WHERE product_id = NEW.product_id
       ) THEN
        INSERT INTO stock_alert (product_id, quantity)
        VALUES (NEW.product_id, NEW.quantity_in_stock);
    END IF;
END$$

DELIMITER ;

