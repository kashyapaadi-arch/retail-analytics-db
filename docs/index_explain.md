# Date index EXPLAIN comparison

Run `sql/index_demo.sql` after loading the schema and sample data. It removes `idx_order_date` if it exists, explains a seven-day range over `sales_order.order_date`, recreates the index, then explains the same query again. The script leaves the index installed, so running it again is safe.

Before the index, MySQL has no ordered access path for the date predicate and normally scans `sales_order`. After the index, a selective range can use `idx_order_date` and read only matching entries plus their table rows. Verify the `type`, `key`, and estimated `rows` columns in each EXPLAIN result.

The optimizer chooses a plan from table statistics and data distribution. With a very small table or a date range that matches most rows, it may still prefer a table scan after the index is added. The comparison uses a narrow range to make indexed access more likely; it does not force a plan.

