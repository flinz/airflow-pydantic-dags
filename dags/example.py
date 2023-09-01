from datetime import datetime
from typing import Union

import pydantic as pyd
from airflow.decorators import task

from airflow_pydantic_dags.dag import PydanticDAG


class MyRunConfig(pyd.BaseModel):
    string_to_print: str = "overwrite this"


with PydanticDAG(
    pydantic_class=MyRunConfig,
    dag_id="example",
    schedule=None,
    start_date=datetime(2023, 8, 1),
    params={"airflow_classic_param": 1},
) as dag:

    @task(dag=dag)
    @dag.parse_config()
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
