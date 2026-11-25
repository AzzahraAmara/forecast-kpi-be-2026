# Forecast BE KPI 2026 - Synthetic Demo

A runnable, synthetic-data demonstration of the Forecast BE KPI workflow. All sample values and segment labels in this repository are fabricated; they are not company data or business results.

![Forecast KPI workflow](forecast-workflow.png)

## Metrics

- **RR - Retention Rate:** repeat successful transactions divided by total successful transactions.
- **CV - Customer Value:** GMV divided by unique customers.
- **LR - Linkage Rate:** leads divided by base.
- **NC - New Customer**
- **LC - Loyal Customer**
- **LCO - Loyal Customer Other**
- **NCLCO:** `NC + LCO`
- **Usership:** `NC + LC + LCO`

## Run the demo

The production workflow retrieves actuals from BigQuery. A BigQuery query is included as a comment in [`forecast_demo.py`](forecast_demo.py) to document that workflow step, but the demo does not connect to BigQuery, a database, or any network service. It generates sample actuals locally and writes:

- [`data/synthetic_history.csv`](data/synthetic_history.csv)
- [`data/synthetic_forecast.csv`](data/synthetic_forecast.csv)

Requires Python 3.10+ and NumPy:

```powershell
py -m pip install numpy
py forecast_demo.py --history-months 12 --seed 2026 --as-of 2026-07-01
```

For the example above, synthetic actuals run through June 2026; forecasts run from July through December 2026. Generated sample data can be reproduced with the same seed and parameters.

### Script parameters

| Parameter | Meaning | Default |
|---|---|---:|
| `--history-months` | Number of synthetic monthly actuals before the forecast month. | `12` |
| `--seed` | Seed controlling the generated synthetic input values. | `2026` |
| `--as-of` | Forecast run date (`YYYY-MM-DD`). Actual history ends in the previous month; forecast starts in this date's month and runs through December. | Today |
| `--output-dir` | Folder for the generated CSV files. | `./data` |

## CSV fields

The history CSV includes:

| Field | Meaning |
|---|---|
| `period` | First day of the month represented by the row. |
| `channel` | Synthetic channel: `Supermarket` or `Online`. |
| `product_category` | Synthetic product: `Susu Cokelat`, `Susu Vanila`, or `Susu Stroberi`. |
| `repeat_transactions`, `total_transactions` | Synthetic numerator and denominator used to calculate RR. |
| `gmv`, `unique_customers` | Synthetic numerator and denominator used to calculate CV. |
| `leads`, `base` | Synthetic numerator and denominator used to calculate LR. |
| `NC`, `LC`, `LCO` | Synthetic monthly customer volumes. |
| `NCLCO`, `Usership` | Derived totals: `NC + LCO` and `NC + LC + LCO`. |
| `RR`, `CV`, `LR` | Derived KPI values. RR and LR are rates; CV is a synthetic value per customer, not real currency data. |

The forecast CSV contains the period, channel, product, record type, and forecast values. `ALL_FOCUS_TOTAL` rows sum the three example product categories within a channel. RR, CV, and LR are left blank in those total rows because rates and per-customer values should not be added across products.

## Forecast logic

RR, CV, and LR use the same core formulas and forecast approaches documented in the source workflow:

- **RR:** use the maximum rate in up to the latest 18 actual observations as the recovery peak. The recovery factor is `0.30` with fewer than 6 observations, `0.50` with 6-11, and `0.60` with 12 or more. Forecast values move linearly from the latest actual toward the target through December.
- **CV:** with at least 6 observations, estimate monthly growth from the first and last values in the latest 6; with 3-5 observations, average the available month-to-month growth rates; with fewer than 3, use `1%`. Clamp monthly growth to `0.5%-3%`.
- **LR:** use the mean of the three highest actual rates as the recovery peak, apply the same history-length recovery factors as RR, and clamp the rate to `0-1`.
- **NC, LC, and LCO:** start from the latest positive actual value and forecast month by month. A stable seed is derived from the synthetic channel, product, and metric. Baselines below `50` use seeded monthly growth from `0%-1%`; other baselines use `2%-3%`. Values are rounded to whole numbers. NCLCO and Usership are calculated from the projected components.

The volume RNG follows the source workflow's deterministic per-segment pattern. The sample outputs are still synthetic and are not forecasts of company performance.

## Scope and limitations

The script demonstrates formulas and forecasting behavior with fabricated data. It does **not** reproduce production results or the complete production pipeline. Company-specific source tables, product/channel hierarchies, exclusion rules, and allocation/reconciliation mappings are not included. `ALL FOCUS PRODUCTS` is only a generic sum across the three sample products.

The original notebook is intentionally excluded from the GitHub version; see `.gitignore`. The diagram is retained as a workflow illustration.
