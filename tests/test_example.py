def test_example():
    """Tests dags/example.py"""

    from airflow_pydantic_dags.examples.example_dag import example_dag

    example_dag.test()
