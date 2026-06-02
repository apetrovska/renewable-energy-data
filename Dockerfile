FROM apache/airflow:2.9.3-python3.11

USER root
RUN apt-get update && apt-get install -y git && apt-get clean

USER airflow

RUN pip install --no-cache-dir \
    dbt-bigquery==1.7.0 \
    entsoe-py \
    openmeteo-requests \
    requests-cache \
    retry-requests