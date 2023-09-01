import logging
from typing import Union

import pendulum
import pydantic as pyd
import pytest
from airflow.decorators import task

from airflow_pydantic_dags.dag import PydanticDAG

default_str = "default"
nondefault_str = "nondefault"
default_int = 1


class InnerClass(pyd.BaseModel):
    value: int = default_int


class RunConfig(pyd.BaseModel):
    string_to_print: str = default_str
    nested_values: InnerClass = InnerClass()


def test_task_without_kwargs_fails(caplog):
    caplog.set_level(logging.ERROR)

    with PydanticDAG(
        pydantic_class=RunConfig,
        dag_id="test_pydantic_dag",
        schedule=None,
        start_date=pendulum.datetime(2021, 1, 1, tz="UTC"),
        catchup=False,
    ) as dag:

        @task(dag=dag)
        @dag.parse_config()
        # we do not add kwargs to the task, so airflow will not parse any params
        def pull_params():
            pass

        pull_params()

    dag.test()

    # we can not directly raise the airflowexception, since it is caught by the dag test runner
    # instead test the log
    assert len(caplog.records) > 0
    assert "airflow.exceptions.AirflowException: Airflow did not pass kwargs to task" in caplog.text
    assert "Task failed with exception" in caplog.text


def test_pydantic_class_without_default_fails():
    class RunConfigNoDefault(pyd.BaseModel):
        string_to_print: str

    with pytest.raises(Exception):
        PydanticDAG(
            pydantic_class=RunConfigNoDefault,
            dag_id="test_pydantic_dag",
            schedule=None,
            start_date=pendulum.datetime(2021, 1, 1, tz="UTC"),
            catchup=False,
        )


@pytest.mark.parametrize(
    "params, conf",
    [
        [None, {}],
        [{}, {}],
        [{}, {"string_to_print": nondefault_str}],
        [{}, {"nested_values": {"value": default_int + 1}}],
        [{"extra": 1}, {"string_to_print": nondefault_str}],
        [{"extra": 1}, {"nested_values": {"value": default_int + 1}}],
    ],
)
def test_mapped_expand_against_params(params, conf):
    param_dict = []
    object_dict = []

    with PydanticDAG(
        pydantic_class=RunConfig,
        dag_id="test_pydantic_dag",
        schedule=None,
        start_date=pendulum.datetime(2021, 1, 1, tz="UTC"),
        catchup=False,
        params=params,
    ) as dag:

        @task(dag=dag)
        @dag.parse_config()
        def pull_params(config_object: Union[RunConfig, None] = None, **kwargs):
            assert type(config_object) is dag.run_config_class
            assert dag.run_config_class == RunConfig
            param_dict.append(dict(kwargs["params"]))
            if config_object is not None:
                object_dict.append(config_object.dict())

        pull_params()

    dag.test(run_conf=conf)
    expected_class = RunConfig(**conf)

    # test that params were passed to the dag, including both regular params and the config object's properties
    assert len(param_dict) == 1
    # this lets us test also the non-set params case
    if params is None:
        params = {}
    assert param_dict[0] == dict(params, **expected_class.dict())

    # test that the config object's properties were parsed by pydantic\
    # tested here by equality of the dict that is produced
    assert len(object_dict) == 1
    assert object_dict[0] == expected_class.dict()
