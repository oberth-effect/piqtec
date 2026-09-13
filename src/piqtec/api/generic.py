"""Descriptors for the individual variables exposed by the controller."""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

from ..constants import (
    CALENDAR_PREFIX,
    DEFAULT_VALUE_BYTES,
    DEVICE_PREFIX,
    DRIVER_PREFIX,
    INTEGER_TYPES,
    SCENARIO_PREFIX,
    SENTINEL_PREFIX,
    VALUE_DECODERS,
    VALUE_MAX_BYTES,
)
from ..exceptions import InvalidValueError, IQtecError, ReadOnlyVariableError
from ..type_helpers import Get, RequestSet, ResponseSet, Set

_LOGGER = logging.getLogger(__name__)


def decode_value(typ: str, raw: str) -> Any:
    """Convert a raw controller value into a Python value.

    Returns ``None`` for sentinel values ("!off" and friends) and for values that
    do not match their declared type, so that one odd variable cannot take down a
    whole poll.
    """
    if raw.startswith(SENTINEL_PREFIX):
        return None
    decoder = VALUE_DECODERS.get(typ)
    if decoder is None:
        return raw
    try:
        return decoder(raw)
    except (TypeError, ValueError):
        _LOGGER.debug("Cannot decode %r as %s", raw, typ)
        return None


def encode_value(typ: str, value: Any) -> str:
    """Render a Python value the way a variable of ``typ`` is written.

    Strings are sent as given, so raw API usage stays in control of the exact
    bytes. Booleans and every integer type are rendered as whole numbers: a
    slider handing over ``3.0`` must reach a ``byte`` variable as ``3``, which is
    the only form the controller (and :func:`decode_value`) accepts.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return str(int(value))
    if typ in INTEGER_TYPES:
        if isinstance(value, float) and not value.is_integer():
            raise InvalidValueError(f"{value!r} is not a whole number, as a {typ} variable requires")
        try:
            return str(int(value))
        except (TypeError, ValueError) as err:
            raise InvalidValueError(f"{value!r} cannot be written to a {typ} variable") from err
    return str(value)


@dataclass
class API(ABC):
    name: str
    access: str
    param: bool
    typ: str

    @property
    @abstractmethod
    def address(self) -> str:
        """Address of this variable in the /control/? address space."""

    @property
    @abstractmethod
    def structure_address(self) -> str:
        """Address that reads every variable of the owning structure at once."""

    @property
    def readonly(self) -> bool:
        """Whether a *user* may write this variable.

        The access letters name the three roles, upper case for write and lower
        for read: P projectant, U user, S service. Only the user role is assumed
        here, so variables writable solely by a projectant or by service read as
        read-only.
        """
        return "U" not in self.access

    @property
    def response_bytes(self) -> int:
        """Upper bound on the bytes this variable occupies in a reply.

        One line of ``<address>=<value>\\n``.
        """
        value_bytes = VALUE_MAX_BYTES.get(self.typ, DEFAULT_VALUE_BYTES)
        return len(self.address) + value_bytes + 2

    def get_request(self) -> RequestSet:
        return RequestSet(getters=[Get(path=self.address, expected_bytes=self.response_bytes)])

    def set_request(self, value: Any) -> RequestSet:
        if self.readonly:
            raise ReadOnlyVariableError(f"Cannot set read-only variable {self.name}")
        return RequestSet(setters=[Set(path=self.address, value=encode_value(self.typ, value))])

    def parse(self, responses: ResponseSet) -> Any:
        response = responses.get(self.address)
        if response is None:
            return None
        return decode_value(self.typ, response.value)


@dataclass
class _AddressedAPI(API):
    """A variable addressed as ``<prefix>/<structure>/<offset>[/<mask>]``."""

    prefix: ClassVar[str]

    structure_id: int
    offset: int
    mask: int | None

    @property
    def address(self) -> str:
        base = f"{self.prefix}/{self.structure_id}/{self.offset}"
        # 0 is a real mask: scenario records use it as a field index, and
        # dropping it would read the whole row instead of one variable.
        return base if self.mask is None else f"{base}/{self.mask}"

    @property
    def structure_address(self) -> str:
        return f"{self.prefix}/{self.structure_id}/"


@dataclass
class DriverAPI(_AddressedAPI):
    prefix: ClassVar[str] = DRIVER_PREFIX

    history: str | None = None


@dataclass
class CalendarAPI(_AddressedAPI):
    prefix: ClassVar[str] = CALENDAR_PREFIX

    calendar_type: str | None = None


@dataclass
class ScenarioAPI(_AddressedAPI):
    prefix: ClassVar[str] = SCENARIO_PREFIX


@dataclass
class DeviceAPI(API):
    device_id: int
    device_structure_id: int
    offset: int
    mask: int | None

    @property
    def address(self) -> str:
        base = f"{DEVICE_PREFIX}/{self.device_structure_id}/{self.offset}"
        return base if self.mask is None else f"{base}/{self.mask}"

    @property
    def structure_address(self) -> str:
        return f"{DEVICE_PREFIX}/{self.device_structure_id}/"


@dataclass
class PageAPI(API):
    structure_id: int

    @property
    def address(self) -> str:
        raise IQtecError("Page entries are metadata and have no readable address")

    @property
    def structure_address(self) -> str:
        raise IQtecError("Page entries are metadata and have no readable address")
