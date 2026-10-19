-- Sixteen read-only analysis examples for retail_db.
USE retail_db;

-- 1. Monthly revenue and gross profit (profit uses the current product cost).
SELECT `month`, orders, revenue, profit
FROM monthly_sales_summary
ORDER BY `month`;

-- 2. Top ten products by net sales revenue.
SELECT p.product_id, p.name,
       SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct / 100)) AS net_revenue,
       SUM(oi.quantity) AS units_sold
FROM order_item AS oi
JOIN product AS p ON p.product_id = oi.product_id
GROUP BY p.product_id, p.name
ORDER BY net_revenue DESC, p.product_id
LIMIT 10;

-- 3. Revenue by product category.
SELECT c.name AS category,
       SUM(oi.quantity * oi.unit_price * (1 - oi.discount_pct / 100)) AS net_revenue
FROM category AS c
JOIN product AS p ON p.category_id = c.category_id
JOIN order_item AS oi ON oi.product_id = p.product_id
GROUP BY c.category_id, c.name
ORDER BY net_revenue DESC;

-- 4. Top customer cities by sales revenue.
SELECT cu.city,
       COUNT(DISTINCT so.order_id) AS orders,
       SUM(so.total_amount) AS revenue
FROM customer AS cu
JOIN sales_order AS so ON so.customer_id = cu.customer_id
GROUP BY cu.city
ORDER BY revenue DESC
LIMIT 10;

-- 5. Customers whose lifetime spend is above average customer spend.
WITH customer_spend AS (
    SELECT cu.customer_id, cu.name, cu.city, COALESCE(SUM(so.total_amount), 0) AS spend
    FROM customer AS cu
    LEFT JOIN sales_order AS so ON so.customer_id = cu.customer_id
    GROUP BY cu.customer_id, cu.name, cu.city
)
SELECT customer_id, name, city, spend
FROM customer_spend
WHERE spend > (SELECT AVG(spend) FROM customer_spend)
ORDER BY spend DESC;

-- 6. Customer segments by number of orders.
WITH customer_orders AS (
    SELECT cu.customer_id, cu.name, COUNT(so.order_id) AS order_count
    FROM customer AS cu
    LEFT JOIN sales_order AS so ON so.customer_id = cu.customer_id
    GROUP BY cu.customer_id, cu.name
)
SELECT CASE
           WHEN order_count = 0 THEN 'No orders'
           WHEN order_count = 1 THEN 'One order'
           WHEN order_count BETWEEN 2 AND 5 THEN 'Repeat (2-5)'
           ELSE 'Loyal (6+)'
       END AS customer_segment,
       COUNT(*) AS customers
FROM customer_orders
GROUP BY customer_segment
ORDER BY customers DESC;

-- 7. Salesperson revenue ranking.
WITH employee_revenue AS (
    SELECT e.employee_id, e.name,
           COALESCE(SUM(so.total_amount), 0) AS revenue
    FROM employee AS e
    LEFT JOIN sales_order AS so ON so.employee_id = e.employee_id
    GROUP BY e.employee_id, e.name
)
SELECT employee_id, name, revenue,
       RANK() OVER (ORDER BY revenue DESC) AS revenue_rank
FROM employee_revenue
ORDER BY revenue_rank, employee_id;

-- 8. Month-over-month revenue growth.
WITH monthly AS (
    SELECT `month`, revenue FROM monthly_sales_summary
), lagged AS (
    SELECT `month`, revenue,
           LAG(revenue) OVER (ORDER BY `month`) AS previous_month_revenue
    FROM monthly
)
SELECT `month`, revenue, previous_month_revenue,
       ROUND(100 * (revenue - previous_month_revenue) / NULLIF(previous_month_revenue, 0), 2) AS growth_pct
FROM lagged
ORDER BY `month`;

-- 9. Cumulative monthly revenue.
SELECT `month`, revenue,
       SUM(revenue) OVER (ORDER BY `month` ROWS UNBOUNDED PRECEDING) AS cumulative_revenue
FROM monthly_sales_summary
ORDER BY `month`;

-- 10. Products most often bought together on the same order.
SELECT p1.product_id AS product_a_id, p1.name AS product_a,
       p2.product_id AS product_b_id, p2.name AS product_b,
       COUNT(*) AS orders_together
FROM order_item AS oi1
JOIN order_item AS oi2
  ON oi2.order_id = oi1.order_id AND oi2.product_id > oi1.product_id
JOIN product AS p1 ON p1.product_id = oi1.product_id
JOIN product AS p2 ON p2.product_id = oi2.product_id
GROUP BY p1.product_id, p1.name, p2.product_id, p2.name
ORDER BY orders_together DESC, product_a_id, product_b_id
LIMIT 20;

-- 11. Cheapest supplier offer for each product (stable tie-breaking by supplier id).
WITH ranked_offers AS (
    SELECT sp.product_id, sp.supplier_id, sp.supply_price,
           ROW_NUMBER() OVER (
               PARTITION BY sp.product_id
               ORDER BY sp.supply_price, sp.supplier_id
           ) AS offer_rank
    FROM supplier_product AS sp
)
SELECT p.product_id, p.name AS product_name,
       s.supplier_id, s.name AS supplier_name, ro.supply_price
FROM ranked_offers AS ro
JOIN product AS p ON p.product_id = ro.product_id
JOIN supplier AS s ON s.supplier_id = ro.supplier_id
WHERE ro.offer_rank = 1
ORDER BY p.product_id;

-- 12. Slow movers: products with no sales in the last 90 days or very low unit movement.
SELECT p.product_id, p.name,
       COALESCE(SUM(CASE WHEN so.order_date >= CURRENT_DATE - INTERVAL 90 DAY
                         THEN oi.quantity ELSE 0 END), 0) AS units_last_90_days,
       MAX(so.order_date) AS last_sold_at
FROM product AS p
LEFT JOIN order_item AS oi ON oi.product_id = p.product_id
LEFT JOIN sales_order AS so ON so.order_id = oi.order_id
GROUP BY p.product_id, p.name
HAVING units_last_90_days <= 2
ORDER BY units_last_90_days, last_sold_at;

-- 13. Payment-mode order count and revenue share.
SELECT payment_mode,
       COUNT(*) AS orders,
       SUM(total_amount) AS revenue,
       ROUND(100 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS order_share_pct
FROM sales_order
GROUP BY payment_mode
ORDER BY orders DESC;

-- 14. Best-selling product in each category.
WITH category_product_sales AS (
    SELECT c.category_id, c.name AS category_name,
           p.product_id, p.name AS product_name,
           COALESCE(SUM(oi.quantity), 0) AS units_sold
    FROM category AS c
    JOIN product AS p ON p.category_id = c.category_id
    LEFT JOIN order_item AS oi ON oi.product_id = p.product_id
    GROUP BY c.category_id, c.name, p.product_id, p.name
), ranked AS (
    SELECT *, ROW_NUMBER() OVER (
        PARTITION BY category_id ORDER BY units_sold DESC, product_id
    ) AS category_rank
    FROM category_product_sales
)
SELECT category_name, product_id, product_name, units_sold
FROM ranked
WHERE category_rank = 1
ORDER BY category_name;

-- 15. ABC product count and revenue summary.
SELECT abc_class,
       COUNT(*) AS products,
       SUM(revenue) AS class_revenue
FROM abc_classification
GROUP BY abc_class
ORDER BY FIELD(abc_class, 'A', 'B', 'C');

-- 16. Low-stock reorder list with the cheapest supplier offer.
WITH ranked_offers AS (
    SELECT sp.product_id, sp.supplier_id, sp.supply_price,
           ROW_NUMBER() OVER (
               PARTITION BY sp.product_id ORDER BY sp.supply_price, sp.supplier_id
           ) AS offer_rank
    FROM supplier_product AS sp
)
SELECT lsp.product_id, lsp.product_name,
       lsp.quantity_in_stock, lsp.reorder_level,
       GREATEST(lsp.reorder_level * 2 - lsp.quantity_in_stock, 0) AS suggested_order_qty,
       s.name AS cheapest_supplier, ro.supply_price
FROM low_stock_products AS lsp
LEFT JOIN ranked_offers AS ro ON ro.product_id = lsp.product_id AND ro.offer_rank = 1
LEFT JOIN supplier AS s ON s.supplier_id = ro.supplier_id
ORDER BY suggested_order_qty DESC, lsp.product_name;

