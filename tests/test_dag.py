import logging
from typing import Union

import pendulum
import pydantic as pyd
import pytest
from airflow.decorators import task

from airflow_pydantic_dags.dag import PydanticDAG
from airflow_pydantic_dags.warnings import IgnoringExtrasWarning

default_str = "default"
nondefault_str = "nondefault"
default_int = 1


class InnerClass(pyd.BaseModel):
    value: int = default_int


class RunConfig(pyd.BaseModel):
    string_to_print: str = default_str
    nested_values: InnerClass = InnerClass()


def test_task_without_kwargs_fails(caplog: pytest.LogCaptureFixture):
    """Test that using the parse_config decorator on a task without
    kwargs fails"""

    # we use logging capture to reliably get an error here,
    # in airflow>=2.6.3, see below for a description
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

    # normally i would catch this via
    # `with pytest.raises(AirflowException):`
    # which worked in airflow==2.6.0.
    # In 2.6.3, however this seems to not be the case anymore,
    # and the exception gets caught by the test() method somehow.
    # To be investigated whats the underlying airflow change.
    dag.test()

    # since we can not directly catch the airflowexception (see above)
    # instead test the log for exceptions in airflow
    assert len(caplog.records) > 0
    assert "airflow.exceptions.AirflowException: Airflow did not pass kwargs to task" in caplog.text
    assert "Task failed with exception" in caplog.text


def test_pydantic_class_without_default_fails():
    """Test we raise an error when providing a pydantic class without
    default values."""

    # create a pydantic class without default values
    class RunConfigNoDefault(pyd.BaseModel):
        string_to_print: str

    # make sure this raises an exception at DAG instantiation time
    with pytest.raises(Exception):
        PydanticDAG(
            pydantic_class=RunConfigNoDefault,
            dag_id="test_pydantic_dag",
            schedule=None,
            start_date=pendulum.datetime(2021, 1, 1, tz="UTC"),
            catchup=False,
        )


@pytest.mark.parametrize(
    "setting",
    [pyd.Extra.allow, pyd.Extra.forbid],
)
def test_pydantic_class_without_extra_ignore_warning(setting: pyd.Extra):
    """Test that extra!=Extra.ignore raises a warning when
    behavior is changed in the Pydantic class"""

    # create a pydantic model that does NOT
    # ignore extra fields
    class RunConfigNoIgnore(pyd.BaseModel):
        only_attr: str = "value"

        class Config:
            extra = setting

    # instantiate a dag, to raise a warning about
    # the change of behavior in the pydantic class
    with pytest.warns(IgnoringExtrasWarning):
        dag = PydanticDAG(
            pydantic_class=RunConfigNoIgnore,
            dag_id="test_pydantic_dag",
            schedule=None,
            start_date=pendulum.datetime(2021, 1, 1, tz="UTC"),
            catchup=False,
        )

    # this is a little paranoid, but lets just test
    # our assumptions about python:
    # if we modify the class at runtime, this is independent
    # of the scope we do this in.
    assert dag.run_config_class is RunConfigNoIgnore
    assert RunConfigNoIgnore.Config.extra is pyd.Extra.ignore

    # and since we're a little paranoid about pydantic itself
    # (can we really modify Config at runtime?
    # I've had some unexpected behavior doing similar things)
    # let's be complete and test whether the change is actually
    # working as intended, i.e. we're ignoring extra values
    x = RunConfigNoIgnore(**{"other_attr": "ignore_this"})
    assert len(x.dict().keys()) == 1
    assert list(x.dict().keys())[0] == "only_attr"


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
    """Test that params are expanded as expected, and pydantic objects
    are parsed as expected."""
    param_dict = []
    object_dict = []

    # create a DAG that has a single task, which
    # outputs the params and object dictionaries into
    # lists, so we can test for expected values after
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
