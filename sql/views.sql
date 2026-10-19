-- Reporting views for the retail application and analytics queries.
USE retail_db;

DROP VIEW IF EXISTS monthly_sales_summary;
DROP VIEW IF EXISTS low_stock_products;
DROP VIEW IF EXISTS abc_classification;

CREATE VIEW monthly_sales_summary AS
SELECT
    CAST(DATE_FORMAT(so.order_date, '%Y-%m-01') AS DATE) AS `month`,
    COUNT(DISTINCT so.order_id) AS orders,
    CAST(SUM(so.total_amount) AS DECIMAL(14, 2)) AS revenue,
    CAST(SUM(
        oi.quantity * oi.unit_price * (1 - oi.discount_pct / 100)
        - oi.quantity * p.cost_price
    ) AS DECIMAL(14, 2)) AS profit
FROM sales_order AS so
JOIN order_item AS oi ON oi.order_id = so.order_id
JOIN product AS p ON p.product_id = oi.product_id
GROUP BY CAST(DATE_FORMAT(so.order_date, '%Y-%m-01') AS DATE);

CREATE VIEW low_stock_products AS
SELECT
    p.product_id,
    p.name AS product_name,
    c.name AS category_name,
    i.quantity_in_stock,
    p.reorder_level,
    p.unit_price
FROM product AS p
JOIN category AS c ON c.category_id = p.category_id
JOIN inventory AS i ON i.product_id = p.product_id
WHERE i.quantity_in_stock <= p.reorder_level;

CREATE VIEW abc_classification AS
WITH product_revenue AS (
    SELECT
        p.product_id,
        p.name AS product_name,
        COALESCE(SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct / 100)), 0.00) AS revenue
    FROM product AS p
    LEFT JOIN order_item AS oi ON oi.product_id = p.product_id
    GROUP BY p.product_id, p.name
), cumulative_revenue AS (
    SELECT
        product_id,
        product_name,
        revenue,
        SUM(revenue) OVER (
            ORDER BY revenue DESC, product_id
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_revenue,
        SUM(revenue) OVER () AS total_revenue
    FROM product_revenue
)
SELECT
    product_id,
    product_name,
    CAST(revenue AS DECIMAL(14, 2)) AS revenue,
    CASE
        WHEN total_revenue = 0 THEN 'C'
        WHEN running_revenue / total_revenue <= 0.80 THEN 'A'
        WHEN running_revenue / total_revenue <= 0.95 THEN 'B'
        ELSE 'C'
    END AS abc_class
FROM cumulative_revenue;

