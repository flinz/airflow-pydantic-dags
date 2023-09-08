class NoDefaultValuesException(Exception):
    """Exception that is raised when the Pydantic class does
    not provide default values for all its attributes."""

    pass
