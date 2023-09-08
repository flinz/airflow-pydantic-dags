import warnings
from functools import wraps
from typing import Generic, TypeVar

import pydantic as pyd
from airflow import DAG
from airflow.exceptions import AirflowException

from airflow_pydantic_dags.exceptions import NoDefaultValuesException
from airflow_pydantic_dags.warnings import IgnoringExtrasWarning

T = TypeVar("T", bound=pyd.BaseModel)


class PydanticDAG(DAG, Generic[T]):
    """PydanticDAG allows developers use any Pydantic model to validate task configuration using
    the Airflow params, and to writing tasks directly against the Pydantic model.

    Given a Pydantic class MyModel, the PydanticDAG has the following features:
    a. A PydanticDAG initialized with MyModel exposes all attributes of MyModel in the
       Airflow trigger UI as parameters. This is realized by extending the params dictionary
       by all attributes of MyModel at instantiation time.
    b. The PydanticDAG instance provides a decorator (parse_config) that will
       instantiate MyModel using the values in the params dictionary, and append the model
       instance to the kwargs. This can be used to receive an instance of MyModel in
       tasks, allowing you to access DAG parameters/config as like dataclasses -- typed and validated
       by Pydantic.
    """

    def __init__(self, pydantic_class: type[T], *args, **kwargs):
        """Initialize an Airflow DAG that uses pydantic_class to
        parse and validate DAG parameters/config.

        Args:
            pydantic_class (subclass of pydantic.BaseModel): Pydantic model to use for
            for task parameters/config validation. Requirements for the Pydantic model are:
            - the model must provide default values for all attributes: this is required
              since the Airflow UI requires default values for all parameters.

        Raises:
            NoDefaultValuesException: Raised if the Pydantic model can not be instantiated
                with default values.
        """

        self.run_config_class = pydantic_class

        # we use the existing params, if they are set
        # this allows setting traditional params, not covered by the pydantic classes
        if "params" not in kwargs or kwargs["params"] is None:
            kwargs["params"] = {}

        try:
            # this will enforce default values exist for all fields in the run_config
            # validation error will be raised here, if the pydantic model does not
            # provide default settings for all attributes.
            pydantic_class_default_instance = pydantic_class()
        except pyd.ValidationError as e:
            raise NoDefaultValuesException(
                f"Pydantic class {type(pydantic_class)} is missing default values for some fields: {e}"
            )

        # append pydantic attributes to the params
        # this makes them available in the UI to trigger dags
        kwargs["params"].update(pydantic_class_default_instance.dict())

        # ensure the pydantic model ignores extra fields
        # which we use to parse params, and ignore the extra
        if pydantic_class_default_instance.Config.extra is not pyd.Extra.ignore:
            # we originally also had Extra.allow, but I don't see
            # a usecase for this. I want only the fields relating
            # to my model to be parsed.
            warnings.warn(
                IgnoringExtrasWarning(
                    f"Setting Pydantic class {type(pydantic_class)} to "
                    "use Config.extra=ignore, instead of "
                    f"Config.extra={pydantic_class_default_instance.Config.extra}"
                )
            )
            self.run_config_class.Config.extra = pyd.Extra.ignore

        super().__init__(*args, **kwargs)

    def parse_config(self):
        def return_config(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                if "params" not in kwargs:
                    raise AirflowException(
                        f"Airflow did not pass kwargs to task, please add "
                        f"`**kwargs` to the task definition of `{f.__name__}`."
                    )
                return f(
                    *args,
                    config_object=self.run_config_class(**kwargs["params"]),
                    **kwargs,
                )

            return wrapper

        return return_config
