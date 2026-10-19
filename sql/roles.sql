-- Role-based access for retail_db. Run as a MySQL administrator after procedures.sql.
-- All passwords below are placeholders: change them before use.
USE retail_db;

CREATE ROLE IF NOT EXISTS 'admin_role'@'%';
CREATE ROLE IF NOT EXISTS 'inventory_mgr_role'@'%';
CREATE ROLE IF NOT EXISTS 'sales_staff_role'@'%';

CREATE USER IF NOT EXISTS 'admin_user'@'%' IDENTIFIED BY 'ChangeThis_Admin_Password';
CREATE USER IF NOT EXISTS 'inventory_mgr'@'%' IDENTIFIED BY 'ChangeThis_Inventory_Password';
CREATE USER IF NOT EXISTS 'sales_staff'@'%' IDENTIFIED BY 'ChangeThis_Sales_Password';

GRANT ALL PRIVILEGES ON retail_db.* TO 'admin_role'@'%';

GRANT SELECT ON retail_db.* TO 'inventory_mgr_role'@'%';
GRANT INSERT, UPDATE ON retail_db.product TO 'inventory_mgr_role'@'%';
GRANT INSERT, UPDATE ON retail_db.supplier TO 'inventory_mgr_role'@'%';
GRANT INSERT, UPDATE ON retail_db.supplier_product TO 'inventory_mgr_role'@'%';
GRANT INSERT, UPDATE ON retail_db.purchase_order TO 'inventory_mgr_role'@'%';
GRANT INSERT, UPDATE ON retail_db.purchase_order_item TO 'inventory_mgr_role'@'%';
GRANT EXECUTE ON PROCEDURE retail_db.receive_purchase_order TO 'inventory_mgr_role'@'%';

GRANT SELECT ON retail_db.product TO 'sales_staff_role'@'%';
GRANT SELECT ON retail_db.inventory TO 'sales_staff_role'@'%';
GRANT SELECT ON retail_db.sales_order TO 'sales_staff_role'@'%';
GRANT SELECT, INSERT ON retail_db.customer TO 'sales_staff_role'@'%';
GRANT EXECUTE ON PROCEDURE retail_db.place_order TO 'sales_staff_role'@'%';

GRANT 'admin_role'@'%' TO 'admin_user'@'%';
GRANT 'inventory_mgr_role'@'%' TO 'inventory_mgr'@'%';
GRANT 'sales_staff_role'@'%' TO 'sales_staff'@'%';

SET DEFAULT ROLE 'admin_role'@'%' TO 'admin_user'@'%';
SET DEFAULT ROLE 'inventory_mgr_role'@'%' TO 'inventory_mgr'@'%';
SET DEFAULT ROLE 'sales_staff_role'@'%' TO 'sales_staff'@'%';

