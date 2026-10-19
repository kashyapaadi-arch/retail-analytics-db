"""Integration-test setup using only the dedicated retail_db_test database."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import mysql.connector
import pytest


ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
sys.path.insert(0, str(ROOT / "python"))


def _statements(source: str):
    source = re.sub(r"(?m)^\s*--.*$", "", source)
    delimiter = ";"
    buffer = ""
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER "):
            delimiter = stripped.split(None, 1)[1]
            continue
        buffer += line + "\n"
        while delimiter in buffer:
            statement, buffer = buffer.split(delimiter, 1)
            if statement.strip():
                yield statement.strip()
    if buffer.strip():
        yield buffer.strip()


def _apply_file(connection, path: Path, source_db: str, target_db: str) -> None:
    sql = path.read_text(encoding="utf-8")
    sql = re.sub(rf"\b{re.escape(source_db)}\b", target_db, sql)
    cursor = connection.cursor(buffered=True)
    try:
        for statement in _statements(sql):
            cursor.execute(statement)
            if cursor.with_rows:
                cursor.fetchall()
    finally:
        cursor.close()


@pytest.fixture(scope="session")
def mysql_settings():
    db_name = os.getenv("TEST_DB_NAME", "retail_db_test")
    dw_name = os.getenv("TEST_DW_NAME", "retail_dw_test")
    if db_name == os.getenv("DB_NAME", "retail_db") or db_name != "retail_db_test":
        pytest.fail("Tests must use the dedicated TEST_DB_NAME=retail_db_test database")
    settings = {
        "host": os.getenv("TEST_DB_HOST", os.getenv("DB_HOST", "127.0.0.1")),
        "port": int(os.getenv("TEST_DB_PORT", os.getenv("DB_PORT", "3306"))),
        "user": os.getenv("TEST_DB_USER", os.getenv("DB_USER", "root")),
        "password": os.getenv("TEST_DB_PASSWORD", os.getenv("DB_PASSWORD", "root")),
        "database": db_name,
        "dw_database": dw_name,
    }
    original = {key: os.environ.get(key) for key in ("DB_HOST", "DB_PORT", "DB_USER", "DB_PASSWORD", "DB_NAME", "DW_NAME")}
    os.environ.update({
        "DB_HOST": settings["host"], "DB_PORT": str(settings["port"]),
        "DB_USER": settings["user"], "DB_PASSWORD": settings["password"],
        "DB_NAME": db_name, "DW_NAME": dw_name,
    })
    try:
        try:
            admin = mysql.connector.connect(
                host=settings["host"], port=settings["port"], user=settings["user"],
                password=settings["password"], autocommit=True,
            )
        except mysql.connector.Error as exc:
            if os.getenv("REQUIRE_MYSQL_TESTS") == "1":
                pytest.fail(f"Required MySQL test service is unavailable: {exc}")
            pytest.skip(f"MySQL integration tests skipped because the server is unavailable: {exc}")
        cursor = admin.cursor()
        cursor.execute(f"DROP DATABASE IF EXISTS `{dw_name}`")
        cursor.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
        cursor.execute(f"CREATE DATABASE `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        cursor.close()
        for filename in ("schema.sql", "support_tables.sql", "triggers.sql", "procedures.sql", "views.sql"):
            _apply_file(admin, SQL_DIR / filename, "retail_db", db_name)
        # Validate the read-only query pack and index demo against a clean schema.
        _apply_file(admin, SQL_DIR / "analytics_queries.sql", "retail_db", db_name)
        _apply_file(admin, SQL_DIR / "index_demo.sql", "retail_db", db_name)
        admin.close()
        yield settings
        cleanup = mysql.connector.connect(host=settings["host"], port=settings["port"], user=settings["user"], password=settings["password"], autocommit=True)
        cur = cleanup.cursor()
        cur.execute(f"DROP DATABASE IF EXISTS `{dw_name}`")
        cur.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
        cur.close()
        cleanup.close()
    finally:
        for key, value in original.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@pytest.fixture
def connection(mysql_settings):
    conn = mysql.connector.connect(
        host=mysql_settings["host"], port=mysql_settings["port"], user=mysql_settings["user"],
        password=mysql_settings["password"], database=mysql_settings["database"], autocommit=True,
    )
    try:
        yield conn
    finally:
        conn.close()

