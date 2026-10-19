# Sales and Inventory Analytics Database

A retail analytics database course project built with MySQL 8.0 and Python. It covers transactional sales and purchasing, inventory controls, reporting, a small data warehouse, demand forecasting, and a Streamlit interface.

## Project status

The project is being built incrementally. Setup and database design documentation are the first milestones; see the commit history for completed work.

## Quick start

Requirements: MySQL 8.0, Python 3.10+, and Graphviz (including its `dot` executable).

1. Create a virtual environment and install `requirements.txt`.
2. Copy `.env.example` to `.env` and set the local database credentials.
3. Create the MySQL databases and apply the scripts under `sql/` in the order documented here as the implementation is completed.

## Planned features

- Retail products, suppliers, customers, staff, inventory, purchase orders, and sales.
- MySQL constraints, triggers, stored procedures, views, analytics, and role grants.
- Deterministic sample data, a star-schema warehouse, forecasting, and reorder suggestions.
- A Streamlit dashboard and a pytest/GitHub Actions validation workflow.

## Repository layout

```text
docs/       Requirements, design diagrams, and project documentation
python/     Seeding, ETL, forecasting, and Streamlit application
report/     College-format project report
sql/        MySQL schema, routines, views, and analytics
tests/      Automated database and pipeline tests
```

## Configuration and secrets

Database settings are loaded from environment variables or a local `.env` file. Never commit `.env` or real credentials. Sample database-role passwords in SQL are placeholders and must be changed before use.

## License

Course-project use. A license will be selected before public distribution.
