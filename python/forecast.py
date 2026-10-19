"""Compare monthly demand baselines, persist forecasts, and suggest replenishment."""

from __future__ import annotations

import argparse
import math
from datetime import date

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.linear_model import LinearRegression
from sqlalchemy import text

from etl import ROOT, _config, _engine, _ensure_dw, _upsert


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> tuple[float, float | None]:
    errors = np.abs(actual - predicted)
    mae = float(errors.mean())
    nonzero = actual != 0
    mape = float((errors[nonzero] / np.abs(actual[nonzero])).mean() * 100) if nonzero.any() else None
    return mae, mape


def _moving_average_forecasts(values: np.ndarray, test_start: int) -> np.ndarray:
    predictions = []
    history = list(values[:test_start])
    for index in range(test_start, len(values)):
        predictions.append(float(np.mean(history[-3:])))
        history.append(float(values[index]))
    return np.asarray(predictions, dtype=float)


def evaluate_series(values: list[float]) -> dict[str, object]:
    """Evaluate both methods with a chronological holdout and forecast one month."""
    y = np.asarray(values, dtype=float)
    if len(y) < 4:
        raise ValueError("At least four monthly observations are required per product")
    split = min(len(y) - 1, max(3, int(math.floor(len(y) * 0.8))))
    actual = y[split:]

    ma_test = _moving_average_forecasts(y, split)
    ma_mae, ma_mape = _metrics(actual, ma_test)

    x = np.arange(len(y), dtype=float).reshape(-1, 1)
    model = LinearRegression().fit(x[:split], y[:split])
    lr_test = np.maximum(0, model.predict(x[split:]))
    lr_mae, lr_mape = _metrics(actual, lr_test)

    next_month_x = np.asarray([[len(y)]], dtype=float)
    next_lr = max(0.0, float(LinearRegression().fit(x, y).predict(next_month_x)[0]))
    next_ma = max(0.0, float(np.mean(y[-3:])))
    return {
        "moving_average": {"mae": ma_mae, "mape": ma_mape, "prediction": next_ma},
        "linear_regression": {"mae": lr_mae, "mape": lr_mape, "prediction": next_lr},
        "test_months": len(actual),
        "split_index": split,
    }


def _next_month(first: date) -> date:
    year, month = first.year, first.month
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def run_forecast(draft_orders: bool = False) -> dict[str, object]:
    load_dotenv(ROOT / ".env")
    config = _config()
    _ensure_dw(config)
    source = _engine(config, str(config["source_db"]))
    dw = _engine(config, str(config["dw_db"]))
    try:
        monthly = pd.read_sql_query(
            """SELECT f.product_id, DATE_FORMAT(d.full_date, '%Y-%m-01') AS month_start,
                      SUM(f.quantity) AS units
                 FROM fact_sales AS f
                 JOIN dim_date AS d ON d.date_key=f.date_key
                GROUP BY f.product_id, DATE_FORMAT(d.full_date, '%Y-%m-01')
                ORDER BY f.product_id, month_start""",
            dw,
        )
        if monthly.empty:
            raise RuntimeError("The warehouse has no sales facts. Run python/etl.py first.")
        monthly["month_start"] = pd.to_datetime(monthly["month_start"])
        month_range = pd.date_range(monthly["month_start"].min(), monthly["month_start"].max(), freq="MS")
        predictions = []
        model_rows = []
        suggestion_rows = []

        products = pd.read_sql_query(
            """SELECT p.product_id, p.name, p.reorder_level, i.quantity_in_stock
                 FROM product AS p JOIN inventory AS i ON i.product_id=p.product_id""",
            source,
        )
        offers = pd.read_sql_query(
            """SELECT product_id, supplier_id, supply_price,
                      ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY supply_price, supplier_id) AS offer_rank
                 FROM supplier_product""",
            source,
        )
        cheapest = offers[offers["offer_rank"] == 1].set_index("product_id")

        for product_id, group in monthly.groupby("product_id"):
            series = (group.set_index("month_start")["units"]
                      .reindex(month_range, fill_value=0).astype(float))
            if len(series) < 4:
                continue
            result = evaluate_series(series.tolist())
            forecast_month = _next_month(month_range[-1].date())
            for model_key, display_name in (("moving_average", "moving_average"), ("linear_regression", "linear_regression")):
                model_result = result[model_key]
                predictions.append((int(product_id), forecast_month, display_name,
                                    round(model_result["prediction"], 2), model_result["mae"], model_result["mape"]))
                model_rows.append({"product_id": int(product_id), "model": display_name, **model_result})

            best_model = min(("moving_average", "linear_regression"), key=lambda key: result[key]["mae"])
            demand = result[best_model]["prediction"]
            recent = series[-6:].to_numpy(dtype=float)
            safety_stock = math.ceil(1.65 * float(np.std(recent, ddof=1))) if len(recent) > 1 else 0
            product_row = products.loc[products["product_id"] == product_id]
            if product_row.empty:
                continue
            current_stock = int(product_row.iloc[0]["quantity_in_stock"])
            required_qty = max(0, math.ceil(demand + safety_stock - current_stock))
            offer = cheapest.loc[product_id] if product_id in cheapest.index else None
            suggestion_rows.append({
                "product_id": int(product_id), "product_name": product_row.iloc[0]["name"],
                "forecast_units": round(float(demand), 2), "safety_stock": safety_stock,
                "current_stock": current_stock, "suggested_order_qty": required_qty,
                "supplier_id": int(offer["supplier_id"]) if offer is not None else None,
                "supply_price": offer["supply_price"] if offer is not None else None,
                "model": best_model,
            })

        sql = """INSERT INTO demand_forecast (product_id, forecast_month, model_name, predicted_units, mae, mape)
                 VALUES (%s,%s,%s,%s,%s,%s)
                 ON DUPLICATE KEY UPDATE predicted_units=VALUES(predicted_units), mae=VALUES(mae), mape=VALUES(mape)"""
        _upsert(dw, sql, predictions)

        if draft_orders:
            needs = [row for row in suggestion_rows if row["suggested_order_qty"] > 0 and row["supplier_id"] is not None]
            if needs:
                raw = source.raw_connection()
                try:
                    cur = raw.cursor()
                    by_supplier = {}
                    for item in needs:
                        by_supplier.setdefault(item["supplier_id"], []).append(item)
                    for supplier_id, items in by_supplier.items():
                        cur.execute("INSERT INTO purchase_order (supplier_id, status) VALUES (%s, 'PENDING')", (supplier_id,))
                        po_id = cur.lastrowid
                        cur.executemany(
                            "INSERT INTO purchase_order_item (po_id, product_id, quantity, unit_cost) VALUES (%s,%s,%s,%s)",
                            [(po_id, item["product_id"], item["suggested_order_qty"], item["supply_price"]) for item in items],
                        )
                    raw.commit()
                    cur.close()
                except Exception:
                    raw.rollback()
                    raise
                finally:
                    raw.close()

        total_errors = {}
        for model_key in ("moving_average", "linear_regression"):
            model_metrics = [row for row in model_rows if row["model"] == model_key]
            total_errors[model_key] = {
                "mean_mae": float(np.mean([row["mae"] for row in model_metrics])) if model_metrics else None,
                "mean_mape": float(np.mean([row["mape"] for row in model_metrics if row["mape"] is not None]))
                if any(row["mape"] is not None for row in model_metrics) else None,
            }
        return {
            "forecast_month": predictions[0][1].isoformat() if predictions else None,
            "model_errors": total_errors,
            "product_model_metrics": model_rows,
            "reorder_suggestions": suggestion_rows,
            "drafted_supplier_groups": len({r["supplier_id"] for r in suggestion_rows if r["suggested_order_qty"] > 0 and r["supplier_id"] is not None}) if draft_orders else 0,
        }
    finally:
        source.dispose()
        dw.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--draft-orders", action="store_true", help="Create pending purchase orders for positive reorder suggestions")
    args = parser.parse_args()
    result = run_forecast(draft_orders=args.draft_orders)
    print(pd.Series(result["model_errors"]).to_string())
    print(f"Forecast month: {result['forecast_month']}")
    print(f"Products evaluated: {len(result['product_model_metrics']) // 2}")
    print(f"Drafted supplier groups: {result['drafted_supplier_groups']}")


if __name__ == "__main__":
    main()

