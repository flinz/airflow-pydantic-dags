from functools import wraps
from typing import Generic, TypeVar

import pydantic as pyd
from airflow import DAG
from airflow.exceptions import AirflowException

T = TypeVar("T", bound=pyd.BaseModel)


class PydanticDAG(DAG, Generic[T]):
    def __init__(self, pydantic_class: type[T], *args, **kwargs):
        # modify run_config class to allow extra fields
        # which we use to parse params, and ignore the extra ones
        # along the lines of:
        #    run_config_class.model_config.update({"extra": "allow"})
        # TODO need to check in pydantic how to do this
        self.run_config_class = pydantic_class

        try:
            # we use the existing params, if they are set
            # this allows setting traditional params, not covered by the pydantic classes
            if "params" not in kwargs or kwargs["params"] is None:
                kwargs["params"] = {}

            # this will enforce default values exist for all fields in the run_config
            kwargs["params"].update(pydantic_class().dict())

        except pyd.ValidationError as e:
            raise ValueError(f"Pydantic class {type(pydantic_class)} is missing default fields: {e}")

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
