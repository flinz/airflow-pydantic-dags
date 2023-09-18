import pytest
from airflow.exceptions import AirflowException


def test_example():
    """Run dags/example.py to ensure it runs correctly."""

    from airflow_pydantic_dags.examples.example_dag import example_dag

    example_dag.test()


def test_example_fails_without_space():
    """Test that the pydantic validator fails without space in a name."""

    from airflow_pydantic_dags.examples.example_dag import example_dag

    with pytest.raises(AirflowException, match="must contain a space"):
        example_dag.test(run_conf={"string_param": "hasnospace"})
