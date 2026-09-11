"""Connection to an IQtec / Kobra controller."""

import logging
from collections.abc import Iterable
from dataclasses import dataclass, field
from urllib.parse import quote
from xml.etree import ElementTree

import requests

from .api.generic import API, CalendarAPI, DeviceAPI, DriverAPI, PageAPI
from .constants import (
    API_PATH,
    DEFAULT_ENCODING,
    DEFAULT_TIMEOUT,
    DEFAULT_VALUE_BYTES,
    MAX_REQUEST_BYTES,
    MAX_RESPONSE_BYTES,
    REGEXP,
    XML_PATH,
)
from .exceptions import InvalidValueError, IQtecConnectionError, IQtecResponseError
from .type_helpers import Get, RequestSet, Response, ResponseSet, Set
from .unit.calendar import Calendar, CalendarState
from .unit.device import Device, DeviceState
from .unit.room import Room, RoomState
from .unit.sunblind import Sunblind, SunblindState
from .unit.system import System, SystemState
from .utils import find_ids, match_api, pack_chunks, unit_prefix

_LOGGER = logging.getLogger(__name__)

# Replies are cut off at 4092 bytes without any error; anything close to that
# means the budgeting was wrong and values are missing.
_TRUNCATION_WARNING_BYTES = 4000


def parse_responses(payload: str) -> ResponseSet:
    """Parse a ``path=value`` reply body, tolerating odd lines and values."""
    response_set: ResponseSet = {}
    for line in payload.splitlines():
        line = line.strip()
        if not line:
            continue
        path, separator, value = line.partition("=")
        if not separator:
            _LOGGER.debug("Ignoring malformed response line %r", line)
            continue
        response_set[path] = Response(path=path, value=value)
    return response_set


@dataclass
class State:
    system: SystemState = field(default_factory=SystemState)
    rooms: dict[str, RoomState] = field(default_factory=dict)
    sunblinds: dict[str, SunblindState] = field(default_factory=dict)
    devices: dict[str, DeviceState] = field(default_factory=dict)


class Controller:
    """Reads and writes the controller's variables over its HTTP interface."""

    name: str
    host: str
    encoding: str
    timeout: float

    system: System
    rooms: dict[str, Room]
    sunblinds: dict[str, Sunblind]
    calendars: dict[str, Calendar]
    devices: dict[str, Device]

    def __init__(
        self,
        host: str,
        name: str = "IQtec Controller",
        proto: str = "http",
        encoding: str = DEFAULT_ENCODING,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.host = host
        self.name = name
        self.encoding = encoding
        self.timeout = timeout
        self._base_url = f"{proto}://{host}"
        self._session = requests.Session()

        apis = self._get_apis()
        self._driver_apis: dict[str, DriverAPI] = {}
        self._device_apis: dict[str, DeviceAPI] = {}
        self._page_apis: dict[str, PageAPI] = {}
        self._calendar_apis: dict[str, CalendarAPI] = {}
        for api in apis:
            match api:
                case DriverAPI():
                    self._driver_apis[api.name] = api
                case DeviceAPI():
                    self._device_apis[api.name] = api
                case PageAPI():
                    self._page_apis[api.name] = api
                case CalendarAPI():
                    self._calendar_apis[api.name] = api

        self._index_addresses(apis)

        self.system = System(self, "SYSTEM", self._driver_apis)
        self.rooms = {idx: Room(self, idx, self._driver_apis) for idx in find_ids(self._driver_apis, REGEXP.ROOM)}
        self.sunblinds = {
            idx: Sunblind(self, idx, self._driver_apis) for idx in find_ids(self._driver_apis, REGEXP.SUNBLIND)
        }
        self.calendars = {
            idx: Calendar(self, idx, self._calendar_apis) for idx in find_ids(self._calendar_apis, REGEXP.CALENDAR)
        }
        # Whatever is left over is exposed generically. SYSTEM is kept so its
        # writable variables remain reachable.
        device_ids = {unit_prefix(name) for name in self._driver_apis} - set(self.rooms) - set(self.sunblinds)
        self.devices = {idx: Device(self, idx, self._driver_apis) for idx in sorted(device_ids)}

    def close(self) -> None:
        self._session.close()

    def __enter__(self) -> "Controller":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    # -- discovery ---------------------------------------------------------

    def _index_addresses(self, apis: Iterable[API]) -> None:
        """Pre-compute how large a reply each readable address produces."""
        self._address_bytes: dict[str, int] = {}
        self._structure_bytes: dict[str, int] = {}
        for api in apis:
            if isinstance(api, PageAPI):
                continue
            self._address_bytes[api.address] = api.response_bytes
            structure = api.structure_address
            self._structure_bytes[structure] = self._structure_bytes.get(structure, 0) + api.response_bytes

    def _get_xml(self) -> ElementTree.Element:
        response = self._get(self._base_url + XML_PATH)
        try:
            return ElementTree.fromstring(response.content)
        except ElementTree.ParseError as err:
            raise IQtecResponseError(f"Malformed {XML_PATH}: {err}") from err

    def _get_apis(self) -> list[API]:
        return [match_api(child.attrib) for child in self._get_xml()]

    # -- transport ---------------------------------------------------------

    def _get(self, url: str) -> requests.Response:
        try:
            response = self._session.get(url, timeout=self.timeout)
        except requests.RequestException as err:
            raise IQtecConnectionError(f"Cannot reach {self.host}: {err}") from err
        if response.status_code != 200:
            raise IQtecConnectionError(f"{self.host} replied HTTP {response.status_code}")
        response.encoding = self.encoding
        return response

    def _call_chunk(self, chunk: str) -> ResponseSet:
        response = self._get(f"{self._base_url}{API_PATH}{chunk}")
        if len(response.content) >= _TRUNCATION_WARNING_BYTES:
            _LOGGER.warning(
                "Reply to %r is %d bytes and was probably truncated by the controller",
                chunk,
                len(response.content),
            )
        return parse_responses(response.text)

    def _expected_bytes(self, getter: Get) -> int:
        if getter.expected_bytes is not None:
            return getter.expected_bytes
        if getter.path.endswith("/"):
            return self._structure_bytes.get(getter.path, MAX_RESPONSE_BYTES)
        return self._address_bytes.get(getter.path, len(getter.path) + DEFAULT_VALUE_BYTES + 2)

    def _encode(self, value: str) -> str:
        try:
            return quote(value, safe="", encoding=self.encoding)
        except UnicodeEncodeError as err:
            raise InvalidValueError(f"{value!r} is not representable in {self.encoding}") from err

    def _setter_fragment(self, setter: Set) -> tuple[str, int]:
        fragment = f"{setter.path}={self._encode(setter.value)}"
        # The controller echoes the variable back with its decoded value.
        return fragment, len(setter.path) + len(setter.value) + 2

    def api_call(self, request_set: RequestSet) -> ResponseSet:
        """Run a request set, split into as few round-trips as the limits allow."""
        responses: ResponseSet = {}
        overhead = len(API_PATH)

        # Units can overlap (SYSTEM is also exposed as a generic device), so the
        # same address may be asked for twice in one set.
        seen: set[str] = set()
        getters = [
            (getter.path, self._expected_bytes(getter))
            for getter in request_set.getters
            if not (getter.path in seen or seen.add(getter.path))
        ]
        setters = [self._setter_fragment(setter) for setter in request_set.setters]

        for chunk in pack_chunks(getters, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, overhead):
            responses.update(self._call_chunk(chunk))
        # Writes go out after reads so a read in the same set never observes a
        # half-applied write.
        for chunk in pack_chunks(setters, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, overhead):
            responses.update(self._call_chunk(chunk))

        return responses

    # -- reading -----------------------------------------------------------

    def read(self, api: API):
        return api.parse(self.api_call(api.get_request()))

    def update(self) -> State:
        """Read the whole house."""
        request = (
            self.system.get_request
            + sum((room.get_request for room in self.rooms.values()), RequestSet())
            + sum((sunblind.get_request for sunblind in self.sunblinds.values()), RequestSet())
            + sum((device.get_request for device in self.devices.values()), RequestSet())
        )
        responses = self.api_call(request)
        return State(
            system=self.system.parse_state(responses),
            rooms={idx: room.parse_state(responses) for idx, room in self.rooms.items()},
            sunblinds={idx: sunblind.parse_state(responses) for idx, sunblind in self.sunblinds.items()},
            devices={idx: device.parse_state(responses) for idx, device in self.devices.items()},
        )

    def read_calendars(self) -> dict[str, CalendarState]:
        request = sum((calendar.get_request for calendar in self.calendars.values()), RequestSet())
        responses = self.api_call(request)
        return {idx: calendar.parse_state(responses) for idx, calendar in self.calendars.items()}

    def get_calendar_names(self) -> list[tuple[str, str | None]]:
        return [(idx, state.name) for idx, state in self.read_calendars().items()]
