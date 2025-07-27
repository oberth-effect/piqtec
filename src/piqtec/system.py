import contextlib
import re
from dataclasses import dataclass, fields
from xml.etree import ElementTree

import requests

from .api.generic import API, CalendarAPI, DeviceAPI, DriverAPI, PageAPI, ScenarioAPI
from .api.room import RoomAPI, RoomState
from .api.sunblind import SunblindAPI, SunblindState
from .constants import API_PATH, MAX_RESPONSE_LENGTH, REGEXP, SYSTEM_VARS, XML_PATH
from .type_helpers import Get, RequestSet, Response, ResponseSet


def parse_responses(r: str) -> ResponseSet:
    lines = r.splitlines()
    responses = [Response(*line.split("=")) for line in lines]
    response_set = {}
    for r in responses:
        response_set[r.path] = r
    return response_set


@dataclass
class SystemState:
    failure: bool
    system_ok: bool
    out_temperature: float
    latitude: float
    longitude: float
    system_time: int
    set_heat: bool
    system_on: bool
    drivers_ok: bool
    devices_ok: bool
    all_ok: bool

    def __post_init__(self):
        # Try to coerce types
        for field in fields(self):
            if callable(field.type):
                with contextlib.suppress(ValueError):
                    if field.type is bool:
                        setattr(self, field.name, field.type(int(getattr(self, field.name))))
                    else:
                        setattr(self, field.name, field.type(getattr(self, field.name)))


@dataclass
class State:
    system: SystemState
    rooms: dict[str, RoomState]
    sunblinds: dict[str, SunblindState]


class Controller:
    name: str
    rooms: dict[str, RoomAPI]
    sunblinds: dict[str, SunblindAPI]

    _url: str
    _room_ids: list[str]
    _sunblind_ids: list[str]
    _drivers_by_name: dict[str, DriverAPI]
    _devices_by_name: dict[str, DeviceAPI]
    _pages_by_name: dict[str, PageAPI]
    _system_drivers: dict[str, DriverAPI]

    def __init__(self, host: str, name: str = "IQtec Controller", proto: str = "http"):
        self._url = f"{proto}://{host}"
        self.name = name

        # Connect to the Device and set up apis
        apis = self._get_apis()
        self._drivers_by_name = {}
        self._devices_by_name = {}
        self._pages_by_name = {}
        for api in apis:
            match api:
                case DriverAPI():
                    self._drivers_by_name[api.name] = api
                case DeviceAPI():
                    self._devices_by_name[api.name] = api
                case PageAPI():
                    self._pages_by_name[api.name] = api
        # Setup System
        self._system_drivers = {}
        for var in SYSTEM_VARS:
            d = self._drivers_by_name.get(f"SYSTEM.{var.value}")
            if d:
                self._system_drivers[var.name] = d
        # Setup Rooms
        self._find_rooms()
        self._create_rooms()
        # Setup Sunblinds
        self._find_sunblinds()
        self._create_sunblinds()

    def _get_xml(self) -> ElementTree.Element:
        response = requests.get(self._url + XML_PATH)
        return ElementTree.fromstring(response.content)

    def _get_apis(self) -> list[API]:
        xml = self._get_xml()
        drivers = []
        for child in xml:
            match child.attrib:
                case {"category": "driver", **rest}:
                    m = rest.get("mask", None)
                    drivers.append(
                        DriverAPI(
                            name=str(rest.get("name")),
                            access=str(rest.get("access")),
                            param=bool(int(rest.get("param"))),
                            typ=str(rest.get("type")),
                            structure_id=int(rest.get("structure_id")),
                            offset=int(rest.get("offset")),
                            mask=int(m) if m else None,
                            history=rest.get("history", None),
                        )
                    )
                case {"category": "calendar", **rest}:
                    m = rest.get("mask", None)
                    drivers.append(
                        CalendarAPI(
                            name=str(rest.get("name")),
                            access=str(rest.get("access")),
                            param=bool(int(rest.get("param"))),
                            typ=str(rest.get("type")),
                            structure_id=int(rest.get("structure_id")),
                            offset=int(rest.get("offset")),
                            mask=int(m) if m else None,
                            calendar_type=rest.get("history", None),
                        )
                    )
                case {"category": "device", **rest}:
                    m = rest.get("mask", None)
                    drivers.append(
                        DeviceAPI(
                            name=str(rest.get("name")),
                            access=str(rest.get("access")),
                            param=bool(int(rest.get("param"))),
                            typ=str(rest.get("type")),
                            device_id=int(rest.get("device_id")),
                            device_structure_id=int(rest.get("device_structure_id")),
                            offset=int(rest.get("offset")),
                            mask=int(m) if m else None,
                        )
                    )
                case {"category": "sbScenario", **rest}:
                    m = rest.get("mask", None)
                    drivers.append(
                        ScenarioAPI(
                            name=str(rest.get("name")),
                            access=str(rest.get("access")),
                            param=bool(int(rest.get("param"))),
                            typ=str(rest.get("type")),
                            structure_id=int(rest.get("structure_id")),
                            offset=int(rest.get("offset")),
                            mask=int(m) if m else None,
                        )
                    )
                case {"category": "page", **rest}:
                    drivers.append(
                        PageAPI(
                            name=str(rest.get("name")),
                            access=str(rest.get("access")),
                            param=bool(int(rest.get("param"))),
                            structure_id=int(rest.get("structure_id")),
                        )
                    )
                case _:
                    raise NotImplementedError(f"Cannot parse driver {child.attrib}")
        return drivers

    def _find_rooms(self):
        rooms = set()
        self._room_ids = []
        for n in self._drivers_by_name:
            prefix = n.split(".")[0]
            if re.match(REGEXP.ROOM, prefix):
                rooms.add(prefix)
        self._room_ids = sorted(rooms)

    def _create_rooms(self):
        self.rooms = {}
        for room_id in self._room_ids:
            room = RoomAPI(room_id, self._drivers_by_name)
            self.rooms[room_id] = room

    def _find_sunblinds(self):
        blinds = set()
        self._sunblind_ids = []
        for n in self._drivers_by_name:
            prefix = n.split(".")[0]
            if re.match(REGEXP.SUNBLIND, prefix):
                blinds.add(prefix)
        self._sunblind_ids = sorted(blinds)

    def _create_sunblinds(self):
        self.sunblinds = {}
        for sunblind_id in self._sunblind_ids:
            sunblind = SunblindAPI(sunblind_id, self._drivers_by_name)
            self.sunblinds[sunblind_id] = sunblind

    def create_system_requests(self) -> list[Get]:
        return [self._system_drivers[f.name].create_get_request() for f in fields(SystemState)]

    def parse_system(self, response_set: ResponseSet) -> SystemState:
        return SystemState(**{f.name: self._system_drivers[f.name].parse(response_set) for f in fields(SystemState)})

    def api_call(self, request_set: RequestSet) -> ResponseSet:
        # Split GET to chunks
        chunks = []
        current_chunk = []
        current_chunk_length = 0
        for getter in request_set.getters:
            expected_length = getter.expected_length if getter.expected_length else 1
            if expected_length > MAX_RESPONSE_LENGTH:
                raise ValueError(
                    f"Expected response for {getter.path} is too long ({getter.expected_length}>{MAX_RESPONSE_LENGTH=})"
                )
            if current_chunk_length + expected_length > MAX_RESPONSE_LENGTH:
                path_string = ";".join(g.path for g in current_chunk)
                chunks.append(path_string)
                current_chunk = [getter]
                current_chunk_length = expected_length
            else:
                current_chunk.append(getter)
                current_chunk_length += expected_length
        if current_chunk:
            path_string = ";".join(g.path for g in current_chunk)
            chunks.append(path_string)

        path_set = ";".join([f"{r.path}={r.value}" for r in request_set.setters])

        responses = {}
        for chunk in chunks:
            url = f"{self._url}{API_PATH}{chunk}"
            r = requests.get(url)
            responses.update(parse_responses(r.text))

        if path_set:
            url = f"{self._url}{API_PATH}{path_set}"
            r = requests.get(url)
            responses.update(parse_responses(r.text))

        return responses

    def update(self, api: API):
        get = api.create_get_request()
        request = RequestSet([get], [])
        response = self.api_call(request)
        return api.parse(response)

    def update_system(self) -> SystemState:
        get_system = self.create_system_requests()
        request = RequestSet(get_system, [])
        response = self.api_call(request)
        return self.parse_system(response)

    def update_status(self) -> State:
        get_system = self.create_system_requests()
        get_rooms = [r.create_get_request() for r in self.rooms.values()]
        get_sunblinds = [r.create_get_request() for r in self.sunblinds.values()]
        request = RequestSet(get_system + get_rooms + get_sunblinds, [])
        response = self.api_call(request)
        return State(
            system=self.parse_system(response),
            rooms={r_id: r.parse(response) for r_id, r in self.rooms.items()},
            sunblinds={s_id: s.parse(response) for s_id, s in self.sunblinds.items()},
        )
