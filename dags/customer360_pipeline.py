"""Customer 360 pipeline DAG: extract -> transform -> load -> dbt run -> dbt test.

Every task runs the same production scripts used locally, inside the dedicated
pipeline virtualenv (kept separate from the Airflow virtualenv).
"""
from datetime import timedelta
from pathlib import Path

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import DAG

# dags/customer360_pipeline.py -> the project root is one level above dags/
PROJECT_ROOT = Path(__file__).resolve().parent.parent
WSL_HOME = Path.home() / "airflow-c360"

PIPELINE_BIN = WSL_HOME / "pipeline_venv" / "bin"
ENV_FILE = WSL_HOME / "pipeline.env"  # Supabase settings, kept outside the repo
DBT_PROFILES_DIR = WSL_HOME / "dbt_profiles"  # profiles.yml (env_var() only)
DBT_PROJECT_DIR = PROJECT_ROOT / "customer360_dbt"

# Shared shell prologue: stop on any error and load the Supabase variables.
SHELL_PROLOGUE = f"set -euo pipefail\nset -a\n. {ENV_FILE}\nset +a\n"


def python_step(script: str) -> str:
    """Build the bash command that runs one project script in the pipeline venv."""
    return f"{SHELL_PROLOGUE}cd {PROJECT_ROOT}\n{PIPELINE_BIN}/python src/{script}\n"


def dbt_step(command: str) -> str:
    """Build the bash command that runs one dbt command from the dbt project folder."""
    return (
        f"{SHELL_PROLOGUE}"
        f"export DBT_PROFILES_DIR={DBT_PROFILES_DIR}\n"
        f"cd {DBT_PROJECT_DIR}\n"
        f"{PIPELINE_BIN}/dbt {command}\n"
    )


default_args = {
    "owner": "arooj",
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
    "execution_timeout": timedelta(minutes=10),
}

with DAG(
    dag_id="customer360_pipeline",
    description="Extract, transform, load into Supabase, then model with dbt",
    start_date=pendulum.datetime(2026, 1, 1, tz="Asia/Karachi"),
    schedule="0 11 * * *",  # every day at 11:00 Pakistan time 
    catchup=False,
    max_active_runs=1,
    default_args=default_args,
    tags=["customer360", "etl", "dbt"],
) as dag:
    extract = BashOperator(task_id="extract", bash_command=python_step("extract.py"))
    transform = BashOperator(task_id="transform", bash_command=python_step("transform.py"))
    load = BashOperator(
        task_id="load",
        bash_command=python_step("load.py"),
        execution_timeout=timedelta(minutes=20),  # load takes about 265 s
    )
    dbt_run = BashOperator(task_id="dbt_run", bash_command=dbt_step("run"))
    dbt_test = BashOperator(task_id="dbt_test", bash_command=dbt_step("test"))

    extract >> transform >> load >> dbt_run >> dbt_test
