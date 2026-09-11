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


class InvalidValueError(IQtecError):
    """A value cannot be transmitted to the controller."""
