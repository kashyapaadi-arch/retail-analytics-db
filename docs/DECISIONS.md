# Design decisions and assumptions

This file records implementation choices where the project brief leaves behavior open.

| Area | Decision |
|---|---|
| Database bootstrap | Each schema script creates its target database if absent and then uses it. Application setup connects to `retail_db`; warehouse ETL creates/uses `retail_dw`. |
| Re-runnable SQL | DDL scripts use `CREATE ... IF NOT EXISTS` where MySQL supports it. Trigger, procedure, and view scripts drop the named object before recreating it. Roles are created conditionally through dynamic SQL because MySQL does not support `CREATE ROLE IF NOT EXISTS` consistently across versions. |
| Sales procedures | `place_order` creates the order and its single requested line. The required procedure signature takes one product and quantity; the app can call it once per product only if a larger multi-line workflow is wrapped at a higher level. |
| Stock locking | Sale and receiving routines lock affected inventory rows with `SELECT ... FOR UPDATE` before changing stock. |
| Order totals | `order_item.unit_price` captures the sale price at the time of sale. The item trigger computes net line amount using percentage discount. The warehouse gross measure is quantity times unit price; discount is stored separately. |
| Profit | Operational monthly profit is net revenue minus `quantity * product.cost_price` at query time. The warehouse captures cost at ETL time as a fact measure. |
| ABC boundaries | Classification uses cumulative revenue divided by total revenue ordered descending. A is up to and including 80%; B is above 80% through 95%; C is the remainder. |
| Seed repeatability | Faker and Python's random generator both use fixed seeds. Customer phones are generated from a deterministic unique sequence to avoid Faker collisions. |
| Seed volume | The requested 2,000 orders and roughly 5,000 lines are generated across a 540-day window with a gradual upward daily order rate, capped to the requested total. |
| Test isolation | The test suite uses `TEST_DB_NAME` (default `retail_db_test`) and must never fall back to `DB_NAME` for destructive setup. |
| Passwords | SQL role passwords are visibly marked placeholders and must be changed before use. No user credential is committed. |
| Report placeholders | `<REG_NO>` and `<SUPERVISOR_NAME>` are retained verbatim because values were not supplied. |
| Time handling | SQL timestamps use the MySQL server's configured time zone; Python-generated datetimes are naive local wall times for compatibility with MySQL `DATETIME`. |

