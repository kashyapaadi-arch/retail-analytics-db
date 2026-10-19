"""Shared MySQL connection and query helpers for the Streamlit application."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterable

import mysql.connector
import pandas as pd
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_connection():
    load_dotenv(PROJECT_ROOT / ".env")
    names = ("DB_HOST", "DB_USER", "DB_PASSWORD", "DB_NAME")
    missing = [name for name in names if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Missing database settings: {', '.join(missing)}")
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME", "retail_db"),
        charset="utf8mb4",
    )


def query_df(sql: str, params: Iterable[Any] = ()) -> pd.DataFrame:
    connection = get_connection()
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(sql, tuple(params))
        return pd.DataFrame(cursor.fetchall())
    finally:
        connection.close()


def execute(sql: str, params: Iterable[Any] = ()) -> int | None:
    connection = get_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(sql, tuple(params))
        connection.commit()
        return cursor.lastrowid
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def call_procedure(name: str, arguments: list[Any]) -> tuple:
    """Call an allow-listed stored procedure and return its OUT arguments."""
    if name not in {"place_order", "receive_purchase_order"}:
        raise ValueError("Unsupported stored procedure")
    connection = get_connection()
    try:
        cursor = connection.cursor()
        result = cursor.callproc(name, arguments)
        for procedure_result in cursor.stored_results():
            procedure_result.fetchall()
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

