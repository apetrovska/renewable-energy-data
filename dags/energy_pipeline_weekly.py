from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

def _load_owid():
    from ingestion.load_to_raw import load_owid
    load_owid()

# ---- Default arguments ------------------------------------------------
# Ці налаштування застосовуються до КОЖНОГО task в DAG якщо не перевизначені
default_args = {
    "owner": "anna",
    "retries": 1,                          # repeat task once again if 1 task failed
    "retry_delay": timedelta(minutes=5),   # wait 5 mins before retry
    "email_on_failure": False,             # do not send email (no smtp)
}

# ---- DAG definition ---------------------------------------------------
with DAG(
    dag_id="energy_pipeline_weekly",                            # unique name in UI
    description="Weekly OWID data refresh",
    schedule="0 6 * * 0",                                       # every Sunday at 06:00 UTC
    start_date=datetime(2025, 1, 1),           # starting from this date Airflow counts runs
    catchup=False,                                              # do not execute missed runs
    default_args=default_args,
    tags=["energy", "weekly", "owid"],                          # filters in UI
) as dag:

    # ---- Task 1: extract + load OWID ----------------------------------
    load_owid_task = PythonOperator(
        task_id="load_raw_owid",
        python_callable=_load_owid,
    )

    # ---- Task 2: notify on failure ------------------------------------
    notify_task = BashOperator(
        task_id="notify_on_failure",
        bash_command='echo "Pipeline failed: {{ task_instance.task_id }}"',
        trigger_rule="one_failed",            # runs only in case of at least 1 task failed
    )

    # ---- Dependencies -------------------------------------------------
    load_owid_task >> notify_task