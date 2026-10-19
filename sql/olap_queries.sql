-- OLAP examples using GROUP BY ... WITH ROLLUP against the sales warehouse.
USE retail_dw;

-- Revenue by year, month, and category with month and year subtotals and a grand total.
SELECT d.year_number, d.month_number, p.category_name,
       SUM(f.net_amount) AS net_revenue,
       SUM(f.profit) AS profit
FROM fact_sales AS f
JOIN dim_date AS d ON d.date_key = f.date_key
JOIN dim_product AS p ON p.product_key = f.product_key
GROUP BY d.year_number, d.month_number, p.category_name WITH ROLLUP;

-- Quantity and revenue by customer city and salesperson with subtotals.
SELECT c.city, e.employee_name,
       SUM(f.quantity) AS units_sold,
       SUM(f.net_amount) AS net_revenue
FROM fact_sales AS f
JOIN dim_customer AS c ON c.customer_key = f.customer_key
JOIN dim_employee AS e ON e.employee_key = f.employee_key
GROUP BY c.city, e.employee_name WITH ROLLUP;

