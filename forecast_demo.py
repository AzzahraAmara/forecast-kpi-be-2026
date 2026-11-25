"""Synthetic-only demo of the Forecast BE KPI workflow.

The production workflow retrieves actuals from BigQuery. The commented query
documents that step; this demo uses generated data and never connects to a
company system.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import random
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np


# Production source-data example (documentation only; intentionally disabled):
#
# from google.cloud import bigquery
# client = bigquery.Client()  # Authorized service account / ADC.
# query = '''
# SELECT period, channel, productcategory, metric_components
# FROM `your-project.your_dataset.your_table`
# WHERE period < DATE_TRUNC(CURRENT_DATE(), MONTH)
# '''
# actuals = client.query(query).to_dataframe()
#
# The demo below generates synthetic inputs locally instead.

PRODUCT_CATEGORIES = ("Susu Cokelat", "Susu Vanila", "Susu Stroberi")
CHANNELS = ("Supermarket", "Online")
ALL_FOCUS = "ALL FOCUS PRODUCTS"
HISTORY_FIELDS = [
    "period",
    "channel",
    "product_category",
    "repeat_transactions",
    "total_transactions",
    "gmv",
    "unique_customers",
    "leads",
    "base",
    "NC",
    "LC",
    "LCO",
    "NCLCO",
    "Usership",
    "RR",
    "CV",
    "LR",
]
FORECAST_FIELDS = [
    "period",
    "channel",
    "product_category",
    "record_type",
    "RR",
    "CV",
    "LR",
    "NC",
    "LC",
    "LCO",
    "NCLCO",
    "Usership",
]


def shift_month(month: date, offset: int) -> date:
    month_index = month.year * 12 + month.month - 1 + offset
    year, zero_based_month = divmod(month_index, 12)
    return date(year, zero_based_month + 1, 1)


def forecast_months(as_of: date) -> list[date]:
    """Forecast from the as-of month through December, inclusive."""
    first_month = date(as_of.year, as_of.month, 1)
    last_month = date(as_of.year, 12, 1)
    return [
        shift_month(first_month, offset)
        for offset in range(last_month.month - first_month.month + 1)
    ]


def make_history(
    history_months: int, as_of: date, seed: int
) -> list[dict[str, Any]]:
    """Generate raw monthly components and derived KPIs for generic segments."""
    rng = random.Random(seed)
    first_month = shift_month(date(as_of.year, as_of.month, 1), -history_months)
    rows: list[dict[str, Any]] = []

    for channel_index, channel in enumerate(CHANNELS):
        for product_index, product in enumerate(PRODUCT_CATEGORIES):
            segment_index = channel_index * len(PRODUCT_CATEGORIES) + product_index
            previous_gmv_per_customer = 42.0 + segment_index * 6.0
            for month_index in range(history_months):
                period = shift_month(first_month, month_index)
                late_months = max(0, month_index - (history_months - 4))

                total_transactions = rng.randint(900, 1600)
                rr = (
                    0.50
                    + product_index * 0.035
                    + channel_index * 0.02
                    + month_index * 0.0015
                    - late_months * 0.008
                    + rng.uniform(-0.005, 0.005)
                )
                repeat_transactions = round(
                    total_transactions * min(0.95, max(0.05, rr))
                )

                unique_customers = rng.randint(350, 800)
                monthly_change = 0.012 + rng.uniform(-0.005, 0.008)
                previous_gmv_per_customer *= 1 + monthly_change
                gmv = round(previous_gmv_per_customer * unique_customers, 2)

                base = rng.randint(600, 1400)
                lr = (
                    0.42
                    + product_index * 0.045
                    + channel_index * 0.025
                    + month_index * 0.002
                    - late_months * 0.006
                    + rng.uniform(-0.006, 0.006)
                )
                leads = round(base * min(0.98, max(0.02, lr)))

                # Vary segment sizes so the demo exercises both seeded growth tiers.
                nc_base = (35 if product_index == 0 else 75) + channel_index * 12
                nc = max(0, round(nc_base * (1 + month_index * 0.012)))
                lc = max(
                    0,
                    round((110 + product_index * 15 + channel_index * 20)
                          * (1 + month_index * 0.008)),
                )
                lco_base = 24 if product_index == 2 else 58
                lco = max(0, round((lco_base + channel_index * 8)
                                   * (1 + month_index * 0.01)))

                row: dict[str, Any] = {
                    "period": period.isoformat(),
                    "channel": channel,
                    "product_category": product,
                    "repeat_transactions": repeat_transactions,
                    "total_transactions": total_transactions,
                    "gmv": gmv,
                    "unique_customers": unique_customers,
                    "leads": leads,
                    "base": base,
                    "NC": nc,
                    "LC": lc,
                    "LCO": lco,
                    "NCLCO": nc + lco,
                    "Usership": nc + lc + lco,
                    "RR": repeat_transactions / total_transactions,
                    "CV": gmv / unique_customers,
                    "LR": leads / base,
                }
                rows.append(row)
    return rows


def recovery_factor(history_length: int) -> float:
    if history_length < 6:
        return 0.30
    if history_length < 12:
        return 0.50
    return 0.60


def project_rr(values: list[float], periods: list[date]) -> list[float]:
    current = values[-1]
    peak = max(max(values[-18:]), current)
    target = current + (peak - current) * recovery_factor(len(values))
    return [
        float(value)
        for value in np.linspace(current, target, len(periods) + 1)[1:]
    ]


def project_cv(values: list[float], periods: list[date]) -> list[float]:
    history_length = len(values)
    if history_length >= 6:
        recent = values[-6:]
        first, last = recent[0], recent[-1]
        monthly_growth = (
            (last / first) ** (1 / (len(recent) - 1)) - 1 if first > 0 else 0.01
        )
    elif history_length >= 3:
        growth_rates = [
            current / previous - 1
            for previous, current in zip(values, values[1:])
            if previous > 0
        ]
        monthly_growth = (
            sum(growth_rates) / len(growth_rates) if growth_rates else 0.01
        )
    else:
        monthly_growth = 0.01

    monthly_growth = float(np.clip(monthly_growth, 0.005, 0.03))
    current = values[-1]
    forecasts = []
    for _ in periods:
        current *= 1 + monthly_growth
        forecasts.append(current)
    return forecasts


def project_lr(values: list[float], periods: list[date]) -> list[float]:
    current = values[-1]
    top_values = sorted(values, reverse=True)[:3]
    peak = max(sum(top_values) / len(top_values), current)
    target = current + (peak - current) * recovery_factor(len(values))
    return [
        float(value)
        for value in np.clip(
            np.linspace(current, target, len(periods) + 1)[1:], 0, 1
        )
    ]


def deterministic_rng(channel: str, product: str, metric: str) -> np.random.RandomState:
    """Match the source workflow's stable segment-and-metric seed."""
    seed_string = f"{channel}_{product}_{metric}"
    digest = hashlib.md5(seed_string.encode("utf-8")).hexdigest()
    unique_seed = int(digest, 16) % (2**32)
    return np.random.RandomState(unique_seed)


def project_volume(
    values: list[int], channel: str, product: str, metric: str, periods: list[date]
) -> list[int]:
    """Apply the source workflow's seeded monthly growth tiers to a volume."""
    base_value = values[-1] if values[-1] > 0 else next(
        (value for value in reversed(values) if value > 0), 0
    )
    if base_value <= 0:
        return [0] * len(periods)

    rng = deterministic_rng(channel, product, metric)
    current = float(base_value)
    forecasts = []
    for _ in periods:
        if base_value < 50:
            growth_rate = rng.uniform(0.00, 0.01)
        else:
            growth_rate = rng.uniform(0.02, 0.03)
        current *= 1 + growth_rate
        forecasts.append(int(np.round(current)))
    return forecasts


def build_forecasts(
    history: list[dict[str, Any]], periods: list[date]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in history:
        grouped[(row["channel"], row["product_category"])].append(row)

    result: list[dict[str, Any]] = []
    by_channel_period: dict[tuple[str, date], list[dict[str, Any]]] = defaultdict(list)

    for (channel, product), rows in sorted(grouped.items()):
        rows.sort(key=lambda row: row["period"])
        rr_values = [float(row["RR"]) for row in rows]
        cv_values = [float(row["CV"]) for row in rows]
        lr_values = [float(row["LR"]) for row in rows]
        nc_values = [int(row["NC"]) for row in rows]
        lc_values = [int(row["LC"]) for row in rows]
        lco_values = [int(row["LCO"]) for row in rows]

        projections = {
            "RR": project_rr(rr_values, periods),
            "CV": project_cv(cv_values, periods),
            "LR": project_lr(lr_values, periods),
            "NC": project_volume(nc_values, channel, product, "nc", periods),
            "LC": project_volume(lc_values, channel, product, "lc", periods),
            "LCO": project_volume(lco_values, channel, product, "lco", periods),
        }

        for index, period in enumerate(periods):
            nc = projections["NC"][index]
            lc = projections["LC"][index]
            lco = projections["LCO"][index]
            row = {
                "period": period.isoformat(),
                "channel": channel,
                "product_category": product,
                "record_type": "FORECAST",
                "RR": round(projections["RR"][index], 6),
                "CV": round(projections["CV"][index], 6),
                "LR": round(projections["LR"][index], 6),
                "NC": nc,
                "LC": lc,
                "LCO": lco,
                "NCLCO": nc + lco,
                "Usership": nc + lc + lco,
            }
            result.append(row)
            by_channel_period[(channel, period)].append(row)

    for (channel, period), rows in sorted(by_channel_period.items()):
        total_nc = sum(row["NC"] for row in rows)
        total_lc = sum(row["LC"] for row in rows)
        total_lco = sum(row["LCO"] for row in rows)
        result.append(
            {
                "period": period.isoformat(),
                "channel": channel,
                "product_category": ALL_FOCUS,
                "record_type": "ALL_FOCUS_TOTAL",
                "RR": "",
                "CV": "",
                "LR": "",
                "NC": total_nc,
                "LC": total_lc,
                "LCO": total_lco,
                "NCLCO": total_nc + total_lco,
                "Usership": total_nc + total_lc + total_lco,
            }
        )
    return sorted(
        result,
        key=lambda row: (row["period"], row["channel"], row["product_category"]),
    )


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate synthetic KPI actuals and forecasts through December."
    )
    parser.add_argument(
        "--history-months",
        type=int,
        default=12,
        help="Synthetic actual months before the as-of month (default: 12).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=2026,
        help="Seed for reproducible synthetic input values (default: 2026).",
    )
    parser.add_argument(
        "--as-of",
        type=date.fromisoformat,
        default=date.today(),
        metavar="YYYY-MM-DD",
        help="Forecast run date; actuals end in the prior month (default: today).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "data",
        help="Directory for generated CSV files (default: ./data).",
    )
    args = parser.parse_args()
    if args.history_months < 1:
        parser.error("--history-months must be at least 1")
    return args


def main() -> None:
    args = parse_args()
    history = make_history(args.history_months, args.as_of, args.seed)
    periods = forecast_months(args.as_of)
    forecasts = build_forecasts(history, periods)

    history_file = args.output_dir / "synthetic_history.csv"
    forecast_file = args.output_dir / "synthetic_forecast.csv"
    write_csv(history_file, HISTORY_FIELDS, history)
    write_csv(forecast_file, FORECAST_FIELDS, forecasts)

    focus_rows = [row for row in forecasts if row["record_type"] == "ALL_FOCUS_TOTAL"]
    for total in focus_rows:
        channel, period = total["channel"], total["period"]
        details = [
            row
            for row in forecasts
            if row["channel"] == channel
            and row["period"] == period
            and row["record_type"] == "FORECAST"
        ]
        assert total["NCLCO"] == sum(row["NCLCO"] for row in details)
        assert total["Usership"] == sum(row["Usership"] for row in details)

    print(f"Synthetic actual rows: {len(history)} -> {history_file}")
    print(f"Forecast rows: {len(forecasts)} -> {forecast_file}")
    print(f"Forecast periods: {periods[0]} through {periods[-1]}")
    print("No BigQuery, database, network, or company data was accessed.")


if __name__ == "__main__":
    main()
