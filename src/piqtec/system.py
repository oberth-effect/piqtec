import re
from dataclasses import dataclass, fields
from functools import reduce
from xml.etree import ElementTree

import requests

from .api.generic import API, DeviceAPI, DriverAPI, PageAPI
from .api.room import RoomAPI, RoomState
from .api.sunblind import SunblindAPI, SunblindState
from .constants import API_PATH, REGEXP, SYSTEM_VARS, XML_PATH
from .type_helpers import RequestSet, Response, ResponseSet
from .utils import CoerceTypesMixin, match_api, split_getters_to_chunks


def parse_responses(r: str) -> ResponseSet:
    lines = r.splitlines()
    responses = [Response(*line.split("=")) for line in lines]
    response_set = {}
    for r in responses:
        response_set[r.path] = r
    return response_set


@dataclass
class SystemState(CoerceTypesMixin):
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
        self._room_ids = self._find_ids(REGEXP.ROOM)
        self._create_rooms()
        # Setup Sunblinds
        self._sunblind_ids = self._find_ids(REGEXP.SUNBLIND)
        self._create_sunblinds()

    def _get_xml(self) -> ElementTree.Element:
        response = requests.get(self._url + XML_PATH)
        if response.status_code != 200:
            raise ConnectionError(f"Error getting XML: {response.status_code}")
        return ElementTree.fromstring(response.content)

    def _get_apis(self) -> list[API]:
        xml = self._get_xml()
        drivers = []
        for child in xml:
            drivers.append(match_api(child.attrib))
        return drivers

    def _find_ids(self, regex: str):
        ids = set()
        for n in self._drivers_by_name:
            prefix = n.split(".")[0]
            if re.match(regex, prefix):
                ids.add(prefix)
        return sorted(ids)

    def _create_rooms(self):
        self.rooms = {}
        for room_id in self._room_ids:
            room = RoomAPI(self, room_id, self._drivers_by_name)
            self.rooms[room_id] = room

    def _create_sunblinds(self):
        self.sunblinds = {}
        for sunblind_id in self._sunblind_ids:
            sunblind = SunblindAPI(self, sunblind_id, self._drivers_by_name)
            self.sunblinds[sunblind_id] = sunblind

    def create_system_requests(self) -> RequestSet:
        return reduce(lambda x, y: x + y, (self._system_drivers[f.name].update_request() for f in fields(SystemState)))

    def parse_system(self, response_set: ResponseSet) -> SystemState:
        return SystemState(**{f.name: self._system_drivers[f.name].parse(response_set) for f in fields(SystemState)})

    def api_call(self, request_set: RequestSet) -> ResponseSet:
        # Split GET to chunks
        chunks = split_getters_to_chunks(request_set.getters)

        path_set = ";".join([f"{r.path}={r.value}" for r in request_set.setters])

        responses = {}
        for chunk in chunks:
            url = f"{self._url}{API_PATH}{chunk}"
            r = requests.get(url)
            if r.status_code != 200:
                raise ConnectionError(f"HTTP ERROR: {r.status_code}")
            responses.update(parse_responses(r.text))

        if path_set:
            url = f"{self._url}{API_PATH}{path_set}"
            r = requests.get(url)
            if r.status_code != 200:
                raise ConnectionError(f"HTTP ERROR: {r.status_code}")
            responses.update(parse_responses(r.text))

        return responses

    def update(self, api: API):
        request = api.update_request()
        response = self.api_call(request)
        return api.parse(response)

    def update_system(self) -> SystemState:
        request = self.create_system_requests()
        response = self.api_call(request)
        return self.parse_system(response)

    def update_status(self) -> State:
        get_system = self.create_system_requests()
        get_rooms = reduce(lambda x, y: x + y, (r.update_request() for r in self.rooms.values()))
        get_sunblinds = reduce(lambda x, y: x + y, (r.update_request() for r in self.sunblinds.values()))
        request = get_system + get_rooms + get_sunblinds
        response = self.api_call(request)
        return State(
            system=self.parse_system(response),
            rooms={r_id: r.parse(response) for r_id, r in self.rooms.items()},
            sunblinds={s_id: s.parse(response) for s_id, s in self.sunblinds.items()},
        )
