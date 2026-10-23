# Agentic Customer 360 BI Platform

End-to-end BI platform: API + CSV ingestion, a Pandas transform layer, a Supabase (PostgreSQL) warehouse, dbt star-schema models with tests, and Apache Airflow orchestration. Power BI dashboards and an AI (Text-to-SQL) agent are planned next.

**Live demo:** https://agentic-customer360-bi-platform-b3idib58gw4qjtyks5uwh7.streamlit.app/

## Architecture

```
DummyJSON API + Kaggle CSVs
        |  extract.py
        v
data/raw  ->  transform.py (clean, drop PII, Parquet)  ->  load.py (COPY)
                                                              |
                                                              v
                                        Supabase PostgreSQL: schema raw
                                                              |  dbt run / dbt test
                                                              v
                      analytics_staging (9 views)  ->  analytics_marts (5 tables)

Apache Airflow runs: extract -> transform -> load -> dbt_run -> dbt_test (daily)
```

Pipeline type: hybrid ETL/ELT. Light cleaning and PII removal happen in Pandas before loading (ETL). Business logic lives in dbt after loading (ELT).

## Tech stack

| Layer               | Tool                                                                |
| ------------------- | ------------------------------------------------------------------- |
| Extract / Transform | Python, Pandas, requests, PyArrow (Parquet)                         |
| Warehouse           | Supabase (PostgreSQL)                                               |
| Modeling and tests  | dbt Core (dbt-postgres)                                             |
| Orchestration       | Apache Airflow 3.3 on WSL2                                          |
| Planned             | Power BI (DAX), LangChain with Groq/Gemini (Text-to-SQL), Streamlit |

## Data sources

- **DummyJSON API** (web store): products, users, carts.
- **Kaggle E-Commerce Sales Analytics** (ERP-style data): 138,116 orders, 397,569 order lines, 25,000 customers, 1,175 products.

Tables are prefixed by source: `web_*` for the DummyJSON store, `erp_*` for the Kaggle sales system.

## Data model (dbt)

- **Staging** (`analytics_staging`, 9 views): one view per raw table, with typed columns (money as `NUMERIC(12,2)`) and meaningful NULLs preserved.
- **Marts** (`analytics_marts`, 5 tables): `dim_products`, `dim_customers`, `dim_date`, `fact_orders` (grain: one order), `fact_order_items` (grain: one product line per order, surrogate key `order_item_id`).
- **Tests:** 25 dbt tests (not null, unique, relationships, accepted values). Current result: 24 pass, 1 expected warning.

## Validated results

KPIs computed from `analytics_marts.fact_orders` match the source dataset statistics:

| KPI                 | Value           |
| ------------------- | --------------- |
| Revenue             | $177,134,263.74 |
| Profit              | $76,146,395.76  |
| Average order value | $1,282.50       |
| Average rating      | 3.68            |
| Return rate         | 6.85%           |
| Cancellation rate   | 6.08%           |

### Known data quality issue

In 11,226 of 138,116 orders (8.1%), the sum of the order lines differs from the order header total (lines are always higher). The cause is in the source data. Order lines are kept and flagged with `is_order_reconciled`; all revenue, profit, AOV and return-rate KPIs are taken from `fact_orders`. This is the single expected warning in the dbt tests.

## Orchestration (Airflow)

The DAG `customer360_pipeline` (`dags/customer360_pipeline.py`) runs the same production scripts and dbt commands in order:

`extract -> transform -> load -> dbt_run -> dbt_test`

- Schedule: daily at 11:00 (Asia/Karachi).
- Retries: 1 retry, 2 minutes apart; the load task has a 20-minute timeout.
- Every task stops on the first failing command and loads the database settings from an environment file outside the repository.
- Airflow runs on WSL2 (Ubuntu) in its own virtual environment; the pipeline scripts and dbt run in a separate one so their dependency versions do not conflict.

![Airflow DAG graph](docs/images/airflow_dag_graph.png)

## Repository structure

```
src/                  extract.py, transform.py, load.py (production scripts)
customer360_dbt/      dbt project (staging views, marts, tests)
dags/                 Airflow DAG
docs/images/          README images
requirements.txt      pinned Python dependencies
```

Notebooks (`*_explore.ipynb`) are for exploration only.

## Running it locally

1. Create a virtual environment and install the pinned dependencies:

```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
```

2. Put the Kaggle CSV files in `data/raw/kaggle/` and create a `.env` file in the project root with `SUPABASE_DB_HOST`, `SUPABASE_DB_PORT`, `SUPABASE_DB_NAME`, `SUPABASE_DB_USER` and `SUPABASE_DB_PASSWORD`.
3. Run the pipeline steps:

```
   python src/extract.py
   python src/transform.py
   python src/load.py
```

4. Run dbt from `customer360_dbt/` with a `profiles.yml` outside the repository (it reads the same variables through `env_var()`):

```
   dbt run
   dbt test
```

`.env`, `data/raw/`, `data/processed/` and `venv/` are never committed.

## Roadmap

- [x] Extract: DummyJSON API and Kaggle CSVs
- [x] Transform: Pandas cleaning, PII removal, Parquet
- [x] Load: Supabase (PostgreSQL), `raw` schema
- [x] Model: dbt star schema with tests
- [x] Orchestrate: Apache Airflow (daily schedule)
- [ ] Visualize: Power BI dashboards
- [ ] AI agent: Text-to-SQL chatbot
- [ ] Deploy: Streamlit app
