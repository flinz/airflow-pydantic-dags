airflow-run:
	AIRFLOW__CORE__LOAD_EXAMPLES=false AIRFLOW__CORE__DAGS_FOLDER=$(shell pwd)/src/airflow_pydantic_dags/examples airflow standalone
