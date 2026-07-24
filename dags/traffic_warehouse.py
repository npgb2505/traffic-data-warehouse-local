from __future__ import annotations

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator


with DAG(
    dag_id="traffic_data_warehouse",
    description="Traffic files to tested dbt marts",
    start_date=datetime(2026, 1, 1),
    schedule="@daily",
    catchup=False,
    default_args={"owner": "data-engineering", "retries": 2, "retry_delay": timedelta(minutes=2)},
    tags=["traffic", "dbt", "postgresql"],
) as dag:
    generate_data = BashOperator(
        task_id="generate_demo_data",
        bash_command="python /opt/project/src/generate_data.py",
    )
    load_raw = BashOperator(
        task_id="load_raw",
        bash_command="python /opt/project/src/load_raw.py",
    )
    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/project/traffic_dbt && dbt run --profiles-dir .",
    )
    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/project/traffic_dbt && dbt test --profiles-dir .",
    )
    render_dashboard = BashOperator(
        task_id="render_dashboard",
        bash_command="python /opt/project/src/render_dashboard.py",
    )
    generate_data >> load_raw >> dbt_run >> dbt_test >> render_dashboard

