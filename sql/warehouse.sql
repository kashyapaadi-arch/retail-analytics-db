-- Retail sales analytics star schema. ETL creates this schema before loading.
CREATE DATABASE IF NOT EXISTS retail_dw
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_0900_ai_ci;
USE retail_dw;

CREATE TABLE IF NOT EXISTS dim_date (
    date_key INT NOT NULL,
    full_date DATE NOT NULL,
    day_of_month TINYINT UNSIGNED NOT NULL,
    month_number TINYINT UNSIGNED NOT NULL,
    month_name VARCHAR(12) NOT NULL,
    quarter_number TINYINT UNSIGNED NOT NULL,
    year_number SMALLINT UNSIGNED NOT NULL,
    weekday_name VARCHAR(12) NOT NULL,
    CONSTRAINT pk_dim_date PRIMARY KEY (date_key),
    CONSTRAINT uq_dim_date_full_date UNIQUE (full_date)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dim_product (
    product_key INT UNSIGNED NOT NULL AUTO_INCREMENT,
    product_id INT UNSIGNED NOT NULL,
    product_name VARCHAR(180) NOT NULL,
    category_id INT UNSIGNED NOT NULL,
    category_name VARCHAR(100) NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    cost_price DECIMAL(10, 2) NOT NULL,
    CONSTRAINT pk_dim_product PRIMARY KEY (product_key),
    CONSTRAINT uq_dim_product_source UNIQUE (product_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key INT UNSIGNED NOT NULL AUTO_INCREMENT,
    customer_id INT UNSIGNED NOT NULL,
    customer_name VARCHAR(150) NOT NULL,
    city VARCHAR(100) NULL,
    CONSTRAINT pk_dim_customer PRIMARY KEY (customer_key),
    CONSTRAINT uq_dim_customer_source UNIQUE (customer_id)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS dim_employee (
    employee_key INT UNSIGNED NOT NULL AUTO_INCREMENT,
    employee_id INT UNSIGNED NOT NULL,
    employee_name VARCHAR(150) NOT NULL,
    role VARCHAR(32) NOT NULL,
    CONSTRAINT pk_dim_employee PRIMARY KEY (employee_key),
    CONSTRAINT uq_dim_employee_source UNIQUE (employee_id)
) ENGINE=InnoDB;

-- Grain: one sales_order line (order_id, product_id).
CREATE TABLE IF NOT EXISTS fact_sales (
    fact_sales_key BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    order_id INT UNSIGNED NOT NULL,
    product_id INT UNSIGNED NOT NULL,
    date_key INT NOT NULL,
    product_key INT UNSIGNED NOT NULL,
    customer_key INT UNSIGNED NOT NULL,
    employee_key INT UNSIGNED NOT NULL,
    quantity INT NOT NULL,
    gross_amount DECIMAL(14, 2) NOT NULL,
    discount_amount DECIMAL(14, 2) NOT NULL,
    net_amount DECIMAL(14, 2) NOT NULL,
    cost_amount DECIMAL(14, 2) NOT NULL,
    profit DECIMAL(14, 2) NOT NULL,
    CONSTRAINT pk_fact_sales PRIMARY KEY (fact_sales_key),
    CONSTRAINT uq_fact_sales_order_line UNIQUE (order_id, product_id),
    CONSTRAINT fk_fact_sales_date FOREIGN KEY (date_key) REFERENCES dim_date (date_key),
    CONSTRAINT fk_fact_sales_product FOREIGN KEY (product_key) REFERENCES dim_product (product_key),
    CONSTRAINT fk_fact_sales_customer FOREIGN KEY (customer_key) REFERENCES dim_customer (customer_key),
    CONSTRAINT fk_fact_sales_employee FOREIGN KEY (employee_key) REFERENCES dim_employee (employee_key),
    CONSTRAINT chk_fact_sales_quantity CHECK (quantity > 0),
    INDEX idx_fact_sales_date (date_key),
    INDEX idx_fact_sales_product (product_key),
    INDEX idx_fact_sales_customer (customer_key),
    INDEX idx_fact_sales_employee (employee_key)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS demand_forecast (
    product_id INT UNSIGNED NOT NULL,
    forecast_month DATE NOT NULL,
    model_name ENUM('moving_average', 'linear_regression') NOT NULL,
    predicted_units DECIMAL(12, 2) NOT NULL,
    mae DECIMAL(12, 4) NULL,
    mape DECIMAL(9, 4) NULL,
    generated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT pk_demand_forecast PRIMARY KEY (product_id, forecast_month, model_name),
    CONSTRAINT fk_demand_forecast_product FOREIGN KEY (product_id)
        REFERENCES dim_product (product_id)
        ON UPDATE CASCADE ON DELETE CASCADE,
    CONSTRAINT chk_demand_forecast_units CHECK (predicted_units >= 0),
    INDEX idx_demand_forecast_month (forecast_month)
) ENGINE=InnoDB;

-- The Streamlit sales role needs warehouse reads for dashboard and forecast pages.
GRANT SELECT ON retail_dw.* TO 'sales_staff_role'@'%';

