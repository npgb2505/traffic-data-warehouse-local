from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="traffic_data_warehouse",
    description="Complete UCI Metro Interstate Traffic dataset to tested dbt marts",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    params={
        "start_at": "",
        "end_at": "",
        "full_refresh": False,
        "force_download": False,
    },
    default_args={"owner": "data-engineering", "retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["traffic", "dbt", "incremental", "postgresql"],
) as dag:
    download_source = BashOperator(
        task_id="download_public_source",
        bash_command=(
            "python /opt/project/src/download_data.py "
            "{% if params.force_download %}--force{% endif %}"
        ),
    )
    load_raw = BashOperator(
        task_id="load_raw",
        bash_command=(
            "python /opt/project/src/load_raw.py "
            "{% if params.full_refresh %}--full-refresh{% endif %} "
            "{% if params.start_at %}--start-at '{{ params.start_at }}'{% endif %} "
            "{% if params.end_at %}--end-at '{{ params.end_at }}'{% endif %}"
        ),
    )
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command=(
            "cd /opt/project/traffic_dbt && "
            "/home/airflow/dbt-venv/bin/dbt run --profiles-dir ."
        ),
    )
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command=(
            "cd /opt/project/traffic_dbt && "
            "/home/airflow/dbt-venv/bin/dbt test --profiles-dir ."
        ),
    )
    render_dashboard = BashOperator(
        task_id="render_dashboard",
        bash_command="python /opt/project/src/render_dashboard.py",
    )
    publish_observability = BashOperator(
        task_id="publish_observability_artifacts",
        bash_command=(
            "python /opt/project/src/render_dbt_evidence.py && "
            "test -s /opt/project/artifacts/metrics.prom && "
            "test -s /opt/project/artifacts/dashboard.html"
        ),
    )
    download_source >> load_raw >> dbt_run >> dbt_test >> render_dashboard >> publish_observability
