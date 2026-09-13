"""Exceptions raised by piqtec.

The package never lets third-party exceptions (``requests``) escape; everything
is normalised to a subclass of :class:`IQtecError`.
"""


class IQtecError(Exception):
    """Base class for every error raised by this package."""


class IQtecConnectionError(IQtecError):
    """The controller could not be reached, or replied with a non-200 status."""


class IQtecResponseError(IQtecError):
    """The controller replied with something that could not be understood."""


class ReadOnlyVariableError(IQtecError):
    """A write was attempted on a variable the controller exposes as read-only."""


class RequestTooLongError(IQtecError):
    """A single request cannot be expressed within the controller's limits."""


class InvalidValueError(IQtecError, ValueError):
    """A value cannot be transmitted to the controller.

    Also a :class:`ValueError`, so callers checking arguments the Python way keep
    working.
    """


class MissingVariableError(IQtecError, KeyError):
    """A unit or calendar this installation does not expose was addressed.

    Also a :class:`KeyError`, since that is what a dictionary lookup would have
    raised; rendered as a plain message rather than a quoted key.
    """

    def __str__(self) -> str:
        return Exception.__str__(self)
