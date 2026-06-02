from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

# -- Callable functions ------------------------------------------------
def _extract_and_load_entsoe():
    import pandas as pd
    from ingestion.load_to_raw import load_entsoe

    yesterday = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    start = pd.Timestamp(yesterday - timedelta(days=3), tz="UTC")
    end   = pd.Timestamp(yesterday + timedelta(days=1), tz="UTC")

    load_entsoe(start=start, end=end)


def _extract_and_load_weather():
    from ingestion.load_to_raw import load_weather
    load_weather()


# -- Default arguments -------------------------------------------------
default_args = {
    "owner": "anna",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": False,
}

# -- DAG definition ----------------------------------------------------
with DAG(
    dag_id="energy_pipeline_daily",
    description="Daily ENTSO-E and weather data ingestion + dbt run",
    schedule="0 7 * * *",           # every day at 07:00 UTC
    start_date=datetime(2025, 1, 1),
    catchup=False,
    default_args=default_args,
    tags=["energy", "daily", "entsoe", "weather", "dbt"],
) as dag:

    # -- Task 1a: extract and load ENTSO-E ----------------------------
    extract_entsoe_task = PythonOperator(
        task_id="extract_entsoe",
        python_callable=_extract_and_load_entsoe,
        execution_timeout=timedelta(hours=2),   # ENTSO-E can be slow
    )

    # -- Task 1b: extract and load weather ----------------------------
    extract_weather_task = PythonOperator(
        task_id="extract_weather",
        python_callable=_extract_and_load_weather,
        execution_timeout=timedelta(minutes=30),
    )

    # -- Task 2: dbt seed ---------------------------------------------
    dbt_seed_task = BashOperator(
        task_id="dbt_seed",
        bash_command="cd /opt/airflow/dbt && dbt seed --target prod",
        execution_timeout=timedelta(minutes=10),
    )

    # -- Task 3: dbt source freshness ---------------------------------
    dbt_freshness_task = BashOperator(
        task_id="dbt_source_freshness",
        bash_command="cd /opt/airflow/dbt && dbt source freshness --target prod",
        execution_timeout=timedelta(minutes=10),
    )

    # -- Task 4: dbt run ----------------------------------------------
    dbt_run_task = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/airflow/dbt && dbt run --target prod  --full-refresh",
        execution_timeout=timedelta(hours=1),
    )

    # -- Task 5: dbt test ---------------------------------------------
    dbt_test_task = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/airflow/dbt && dbt test --target prod",
        execution_timeout=timedelta(minutes=30),
    )

    # -- Task 6: notify on failure ------------------------------------
    notify_task = BashOperator(
        task_id="notify_on_failure",
        bash_command='echo "Pipeline failed at task: {{ task_instance.task_id }}"',
        trigger_rule="one_failed",
    )

    # -- Dependencies -------------------------------------------------
    [extract_entsoe_task, extract_weather_task] >> dbt_seed_task
    dbt_seed_task >> dbt_freshness_task
    dbt_freshness_task >> dbt_run_task >> dbt_test_task >> notify_task