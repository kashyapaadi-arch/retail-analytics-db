-- Optional reporting access for the Streamlit sales role. Run after warehouse.sql.
GRANT SELECT ON retail_dw.* TO 'sales_staff_role'@'%';

