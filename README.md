# Airflow-Pydantic-DAGs

[![Python CICD](https://github.com/flinz/airflow-pydantic-dags/actions/workflows/python-publish.yml/badge.svg)](https://github.com/flinz/airflow-pydantic-dags/actions/workflows/python-publish.yml)

PydanticDAGs allows you to use [Pydantic](https://pydantic.dev) models for task configuration in your [Airflow](https://airflow.apache.org) DAGs.

## Airflow + Pydantic = ❤️: Use Pydantic for Airflow Task Configuration

Runs of Airflow DAGs can be configured using parameters, that use [propietary validation](https://github.com/apache/airflow/pull/17100) and are not de-serialized: you get a dictionary of parameters in your tasks. This leaves YOU to deal with un-typed dictionary values at the task level, write validation logic for them, all without instrospection when developing.

If only there was a established library to create data models with validation?

Enter [Pydantic](https://pydantic.dev): using the `DAG` model of `airflow-pydantic-dags` you get a Pydantic model passed to your tasks, that contains your validated run configuration. Your model is also exposed in the Airflow UI, making it easy to launch Airflow DAGRuns.

## Installation

Currently, this supports:

- airflow >= 2.6.0
- pydantic < 2

As soon as we publish this to pip :) you can

```
pip install airflow-pydantic-dags
```

## Usage

Use the class `PydanticDAG` instead of `DAG`, and pass the pydantic class you want to use
to parse the params. By decorating tasks with `@dag.parse_config()` you will get a `config_object`
passed to your task, which is an instance of the Pydantic class, initialized with your parameters.

Currently, your Pydantic class **needs to provide default values for all attributes**,
otherwise the DAG will fail to initialize.

In the Airflow UI, you will find all attributes of the Pydantic class exposed as
params. Currently, only non-nested fields are exposed as single items, everything
else will become a json parameter.

> [!NOTE]
> Validation of params by Pydantic when submitting through the UI and CLI is **currently** not
> done at time of DAG run creation, but instead only when the parameters are first accessed
> in a task. Achieving validation at creation time will be part of a future update.
> See just below for how to force earlier validation.

To achieve systematic early validation and fail your PydanticDAG `dag`
for invalid parameters, do one of the following:

- use `PydanticDAG(add_validation_task=True)`: this will add a task
  (without dependencies) to your DAG that validates the params
- use `dag.get_validation_task` to get a task that validates the params:
  You can use this to create custom dependencies in your DAG on the validation
- use the decorator `@dag.parse_config` on any of your own tasks:
  this will force validation of the params

## Example

Source is at [dags/example.py](dags/example.py):

```python
from airflow_pydantic_dags.dag import PydanticDAG
from airflow.decorators import task
from datetime import datetime


class MyRunConfig(pyd.BaseModel):
    string_to_print: str = "overwrite this"


with PydanticDAG(
        params_pydantic_class=MyRunConfig,
        dag_id="example",
        schedule=None,
        start_date=datetime(2023, 8, 1),
        params={"airflow_classic_param": 1},
    ) as dag:

        @task(dag=dag)
        @dag.parse_config()
        def pull_params(config_object: MyRunConfig | None = None, **kwargs):

            # params contains pydantic and non-pydantic parameter values
            print("Params:")
            print(kwargs["params"])

            # using the dag.parse_config() decorator, we also get the deserialized pydantic object as 'config_object'
            print("Pydantic object:")
            print(type(config_object))
            print(config_object)

        pull_params()
```

This generates an UI interface for your DAG, including all pydantic and non-pydantic parameters:
![Alt text](docs/imgs/example_trigger_ui.png)

And the task log shows

```
{logging_mixin.py:151} INFO - Params:
{logging_mixin.py:151} INFO - {'airflow_classic_param': 1, 'string_to_print': 'overwrite this'}
{logging_mixin.py:151} INFO - Pydantic object:
{logging_mixin.py:151} INFO - <class 'unusual_prefix_95fa66c061cb15347627f327a8a577346657e3a7_example.MyRunConfig'>
{logging_mixin.py:151} INFO - string_to_print='overwrite this'
```

## Mentions

### Other projects

- [pyproject.toml](./pyproject.toml), [setup.cfg](./setup.cfg), and [.pre-commit-config.yaml](./.pre-commit-config.yaml) were adapted from the excellent [coookiecutter-django](https://github.com/cookiecutter/cookiecutter-django) project.
