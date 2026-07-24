.PHONY: bootstrap full incremental backfill up down logs test

bootstrap:
	docker compose up -d --build airflow-db warehouse
	docker compose run --rm airflow-init

full: bootstrap
	docker compose run --rm airflow python /opt/project/src/download_data.py
	docker compose run --rm airflow python /opt/project/src/load_raw.py --full-refresh
	docker compose run --rm airflow bash -c "cd /opt/project/traffic_dbt && /home/airflow/dbt-venv/bin/dbt build --full-refresh --profiles-dir ."
	docker compose run --rm airflow python /opt/project/src/render_dashboard.py

incremental:
	docker compose run --rm airflow python /opt/project/src/download_data.py
	docker compose run --rm airflow python /opt/project/src/load_raw.py
	docker compose run --rm airflow bash -c "cd /opt/project/traffic_dbt && /home/airflow/dbt-venv/bin/dbt build --profiles-dir ."

backfill:
	docker compose run --rm airflow python /opt/project/src/load_raw.py --start-at "$(START)" --end-at "$(END)"
	docker compose run --rm airflow bash -c "cd /opt/project/traffic_dbt && /home/airflow/dbt-venv/bin/dbt build --profiles-dir ."

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f airflow-scheduler

test:
	python -m pytest -q
