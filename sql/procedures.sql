-- Transactional sales and purchasing procedures.
-- Run after schema.sql, support_tables.sql, and triggers.sql.
USE retail_db;

DROP PROCEDURE IF EXISTS place_order;
DROP PROCEDURE IF EXISTS receive_purchase_order;

DELIMITER $$

CREATE PROCEDURE place_order(
    IN p_customer_id INT UNSIGNED,
    IN p_employee_id INT UNSIGNED,
    IN p_product_id INT UNSIGNED,
    IN p_quantity INT,
    IN p_discount_pct DECIMAL(5, 2),
    IN p_payment_mode VARCHAR(10),
    OUT p_order_id INT UNSIGNED
)
BEGIN
    DECLARE v_stock INT;
    DECLARE v_unit_price DECIMAL(10, 2);

    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    IF p_quantity <= 0 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Quantity must be positive';
    END IF;
    IF p_discount_pct < 0 OR p_discount_pct > 100 THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Discount must be between 0 and 100';
    END IF;
    IF p_payment_mode NOT IN ('cash', 'card', 'upi') THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Unsupported payment mode';
    END IF;

    SELECT i.quantity_in_stock, pr.unit_price
      INTO v_stock, v_unit_price
      FROM inventory AS i
      JOIN product AS pr ON pr.product_id = i.product_id
     WHERE i.product_id = p_product_id
     FOR UPDATE;

    IF v_stock < p_quantity THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Insufficient stock';
    END IF;

    INSERT INTO sales_order (customer_id, employee_id, payment_mode)
    VALUES (p_customer_id, p_employee_id, p_payment_mode);
    SET p_order_id = LAST_INSERT_ID();

    INSERT INTO order_item (order_id, product_id, quantity, unit_price, discount_pct)
    VALUES (p_order_id, p_product_id, p_quantity, v_unit_price, p_discount_pct);

    COMMIT;
END$$

CREATE PROCEDURE receive_purchase_order(IN p_po_id INT UNSIGNED)
BEGIN
    DECLARE v_status VARCHAR(10);
    DECLARE v_done BOOLEAN DEFAULT FALSE;
    DECLARE v_product_id INT UNSIGNED;
    DECLARE v_quantity INT;

    DECLARE item_cursor CURSOR FOR
        SELECT product_id, quantity
          FROM purchase_order_item
         WHERE po_id = p_po_id
         ORDER BY product_id;
    DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_done = TRUE;
    DECLARE EXIT HANDLER FOR SQLEXCEPTION
    BEGIN
        ROLLBACK;
        RESIGNAL;
    END;

    START TRANSACTION;

    BEGIN
        DECLARE CONTINUE HANDLER FOR NOT FOUND SET v_status = 'MISSING';
        SELECT status INTO v_status
          FROM purchase_order
         WHERE po_id = p_po_id
         FOR UPDATE;
    END;

    IF v_status = 'MISSING' THEN
        SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Purchase order not found';
    END IF;

    IF v_status <> 'PENDING' THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'Purchase order already received';
    END IF;

    OPEN item_cursor;
    item_loop: LOOP
        FETCH item_cursor INTO v_product_id, v_quantity;
        IF v_done THEN
            LEAVE item_loop;
        END IF;

        UPDATE inventory
           SET quantity_in_stock = quantity_in_stock + v_quantity
         WHERE product_id = v_product_id;
    END LOOP;
    CLOSE item_cursor;

    UPDATE purchase_order
       SET status = 'RECEIVED'
     WHERE po_id = p_po_id;

    COMMIT;
END$$

DELIMITER ;

