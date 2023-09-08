from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("airflow_pydantic_dags")
except PackageNotFoundError:
    # package is not installed
    pass
