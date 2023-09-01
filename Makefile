airflow-run:
	AIRFLOW__CORE__LOAD_EXAMPLES=false AIRFLOW__CORE__DAGS_FOLDER=$(shell pwd)/dags airflow standalone
