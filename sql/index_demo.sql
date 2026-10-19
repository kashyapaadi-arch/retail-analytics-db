-- Compare the same selective date-range query before and after idx_order_date.
-- Run after schema.sql. This demo temporarily drops and then recreates the index.
USE retail_db;

SET @ddl_drop_date_index = IF(
    (SELECT COUNT(*) FROM information_schema.statistics
     WHERE table_schema = DATABASE() AND table_name = 'sales_order'
       AND index_name = 'idx_order_date') > 0,
    'ALTER TABLE sales_order DROP INDEX idx_order_date',
    'SELECT 1'
);
PREPARE stmt_drop_date_index FROM @ddl_drop_date_index;
EXECUTE stmt_drop_date_index;
DEALLOCATE PREPARE stmt_drop_date_index;

-- BEFORE: inspect the plan without the date index.
EXPLAIN
SELECT order_id, order_date, total_amount
FROM sales_order
WHERE order_date >= CURRENT_DATE - INTERVAL 7 DAY
  AND order_date < CURRENT_DATE + INTERVAL 1 DAY;

SET @ddl_add_date_index = IF(
    (SELECT COUNT(*) FROM information_schema.statistics
     WHERE table_schema = DATABASE() AND table_name = 'sales_order'
       AND index_name = 'idx_order_date') = 0,
    'CREATE INDEX idx_order_date ON sales_order (order_date)',
    'SELECT 1'
);
PREPARE stmt_add_date_index FROM @ddl_add_date_index;
EXECUTE stmt_add_date_index;
DEALLOCATE PREPARE stmt_add_date_index;

-- AFTER: inspect the identical predicate with idx_order_date available.
EXPLAIN
SELECT order_id, order_date, total_amount
FROM sales_order
WHERE order_date >= CURRENT_DATE - INTERVAL 7 DAY
  AND order_date < CURRENT_DATE + INTERVAL 1 DAY;

