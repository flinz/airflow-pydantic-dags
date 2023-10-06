from importlib.metadata import PackageNotFoundError, version

from pydantic import __version__ as pydantic_version

pydantic_version_parts = [int(x) for x in pydantic_version.split(".")]
is_pydantic_2 = pydantic_version_parts[0] >= 2

try:
    __version__ = version("airflow_pydantic_dags")
except PackageNotFoundError:
    # package is not installed
    pass
