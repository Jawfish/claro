"""Type-narrowing assertion functions."""

from typing import TypeVar

from .types import ExpectationError

T = TypeVar("T")


def require(value: T | None, message: str = "Expected value to not be None") -> T:
    """Assert value is not None and return it with narrowed type.

    Usage:
        value: str | None = get_value()
        result = require(value)  # result: str
    """
    if value is None:
        raise ExpectationError(message)
    return value


def narrow(value: object, cls: type[T], message: str | None = None) -> T:
    """Assert value is instance of cls and return it with narrowed type.

    Usage:
        obj: object = get_object()
        user = narrow(obj, User)  # user: User
    """
    if not isinstance(value, cls):
        raise ExpectationError(
            message
            or f"Expected instance of {cls.__name__}, got {type(value).__name__}"
        )
    return value
