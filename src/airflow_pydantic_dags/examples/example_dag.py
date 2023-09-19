from datetime import datetime
from typing import Union

import pydantic as pyd
from airflow.decorators import task

from airflow_pydantic_dags.dag import PydanticDAG


class MyRunConfig(pyd.BaseModel):
    string_param: str = "has space"
    int_param: int = 1

    @pyd.validator("string_param")
    def name_must_contain_space(cls, v):
        if " " not in v:
            raise ValueError("must contain a space")
        return v


with PydanticDAG(
    pydantic_class=MyRunConfig,
    add_validation_task=True,
    dag_id="example",
    schedule=None,
    start_date=datetime(2023, 8, 1),
    params={"airflow_classic_param": 1},
) as example_dag:

    @task(dag=example_dag)
    @example_dag.parse_config()
    # in Airflow, at DAG initalization time, keyword arguments are None
    def pull_params(config_object: Union[MyRunConfig, None] = None, **kwargs):
        # params contains pydantic and non-pydantic parameter values
        print("Params:")
        print(kwargs["params"])

        if config_object is not None:
            # using the dag.parse_config() decorator, we also get the deserialized pydantic object as 'config_object'
            print("Pydantic object:")
            print(type(config_object))
            print(config_object)

    pull_params()
