def test_example():
    """Tests dags/example.py"""

    from airflow_pydantic_dags.example import example_dag

    example_dag.test()
