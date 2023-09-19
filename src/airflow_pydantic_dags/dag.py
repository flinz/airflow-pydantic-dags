import warnings
from functools import wraps
from typing import Callable, Generic, TypeVar, Union

import pydantic as pyd
from airflow import DAG
from airflow.exceptions import AirflowException
from airflow.operators.python import PythonOperator
from airflow.utils.session import NEW_SESSION, provide_session
from sqlalchemy.orm.session import Session

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

    def __init__(self, pydantic_class: type[T], *args, add_validation_task: bool = False, **kwargs):
        """Initialize an Airflow DAG that uses pydantic_class to
        parse and validate DAG parameters/config.

        Args:
            pydantic_class (subclass of pydantic.BaseModel): Pydantic model to use for
                for task parameters/config validation. Requirements for the Pydantic model are:
                - the model must provide default values for all attributes: this is required
                    since the Airflow UI requires default values for all parameters
                - the model should have Config.Extra.ignore set, otherwise this will be changed
                    at initalization time and a warning will be generated.
            insert_validation_task (bool): Whether to insert a validation task (without any
                task dependencies).
                this is useful if you are triggering tasks from the UI: the frontend code
                instantiates this PydanticDAG as regular DAG and therefore never calls
                the create_dagrun override method below, so it will succeed to create a run
                even for nonvalid parameters. The validation task will be executed at the start
                of the DAG fail if parameters are invalid.

        Raises:
            NoDefaultValuesException: Raised if the Pydantic model can not be instantiated
                with default values.
        """

        self.run_config_class = pydantic_class

        # we use the existing params, if they are set
        # this allows setting traditional params, not covered by the pydantic classes
        if "params" not in kwargs or kwargs["params"] is None:
            kwargs["params"] = {}

        print("--------------------------------------------------- PARAMS")
        print(kwargs["params"])
        print("---------------------------------------------------")

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

        if add_validation_task:
            validation_task = self.get_validation_task()
            self.add_task(validation_task)

    def get_pydantic_config(self, config_dict: dict) -> T:
        """Instantiate a pydantic model instance for the given config dictionary.

        Args:
            config_dict (dict): Dictionary passed to pydantic to instantate the pydantic instance
        """

        try:
            o = self.run_config_class(**config_dict)
        except pyd.ValidationError as e:
            raise AirflowException(f"Invalid configuration for Pydantic class {self.run_config_class}: " f"{e}")

        return o

    RT = TypeVar("RT")

    def parse_config(self) -> Callable[[Callable[..., RT]], Callable[..., RT]]:
        """Returns a function decorator that will check for params in the kwargs,
        deserialize these params as the pydantic model, and pass the model the kwargs.

        Raises:
            AirflowException: If the function to be wrapped does not have kwargs defined.

        Returns:
            function: Decorator that will inject the pydantic model `config_object`
                into named arguments
        """

        def return_config(f):
            @wraps(f)
            def wrapper(*args, **kwargs):
                if "params" not in kwargs:
                    # params will always be passed in kwargs by airflow
                    # therefore the likely cause to end up here is if
                    # kwargs is not in the function signature
                    raise AirflowException(
                        f"Airflow did not pass kwargs to task, please add "
                        f"`**kwargs` to the task definition of `{f.__name__}`."
                    )
                return f(
                    *args,
                    config_object=self.get_pydantic_config(kwargs["params"]),
                    **kwargs,
                )

            return wrapper

        return return_config

    @provide_session
    def create_dagrun(self, *args, session: Session = NEW_SESSION, conf: Union[dict, None] = None, **kwargs):
        """Override the original create_dagrun method of airflow.DAG,
        to validaate the whether we can parse the configuration as a
        pydantic object before creating a dagrun.
        """

        if conf is not None:
            self.get_pydantic_config(conf)

        # mypy throws a validation error here, if we pass the arguments explicitly
        # lets add them to kwargs to prevent duplication of arguments passed
        kwargs["session"] = session
        kwargs["conf"] = conf
        return super().create_dagrun(*args, **kwargs)

    def get_validation_task(self, task_id: str = "validate_params"):
        """Returns an Airflow task bound to the DAG, that will validate the configuration.

        Args:
            task_id (str, optional): _description_. Defaults to 'validate_params'.

        This is useful if we are triggering tasks from the UI:
        the frontend code somehow gets a DAG instead of the PydanticDAG
        and therefore never calls the create_dagrun override
        method above, so it will succeed to create a run
        even for nonvalid parameters.

        This task can be used to create a validation step,
        that will surely fail.
        """

        @self.parse_config()
        def function(**func_kwargs):
            print(func_kwargs)

        return PythonOperator(task_id=task_id, python_callable=function)
