from dataclasses import dataclass
from functools import reduce
from xml.etree import ElementTree

import requests

from .api.generic import API, CalendarAPI, DeviceAPI, DriverAPI, PageAPI
from .constants import API_PATH, REGEXP, XML_PATH
from .type_helpers import RequestSet, Response, ResponseSet
from .unit.calendar import Calendar
from .unit.device import Device, DeviceState
from .unit.room import Room, RoomState
from .unit.sunblind import Sunblind, SunblindState
from .unit.system import System, SystemState
from .utils import find_ids, match_api, split_getters_to_chunks


def parse_responses(r: str) -> ResponseSet:
    lines = r.splitlines()
    responses = [Response(*line.split("=")) for line in lines]
    response_set = {}
    for r in responses:
        response_set[r.path] = r
    return response_set


@dataclass
class State:
    system: SystemState
    rooms: dict[str, RoomState]
    sunblinds: dict[str, SunblindState]
    devices: dict[str, DeviceState]


class Controller:
    name: str
    encoding: str

    _url: str
    _room_ids: list[str]
    _sunblind_ids: list[str]
    _calendar_ids: list[str]
    _device_ids: list[str]

    # Units
    system: System
    rooms: dict[str, Room]
    sunblinds: dict[str, Sunblind]
    calendars: dict[str, Calendar]
    devices: dict[str, Device]

    # APIs
    _driapis_by_name: dict[str, DriverAPI]
    _devapis_by_name: dict[str, DeviceAPI]
    _pagapis_by_name: dict[str, PageAPI]
    _calapis_by_name: dict[str, CalendarAPI]

    def __init__(self, host: str, name: str = "IQtec Controller", proto: str = "http", encoding: str = "Windows-1250"):
        self._url = f"{proto}://{host}"
        self.name = name
        self.encoding = encoding

        # Connect to the Device and set up apis
        apis = self._get_apis()
        self._driapis_by_name = {}
        self._devapis_by_name = {}
        self._pagapis_by_name = {}
        self._calapis_by_name = {}
        for api in apis:
            match api:
                case DriverAPI():
                    self._driapis_by_name[api.name] = api
                case DeviceAPI():
                    self._devapis_by_name[api.name] = api
                case PageAPI():
                    self._pagapis_by_name[api.name] = api
                case CalendarAPI():
                    self._calapis_by_name[api.name] = api
        # Setup System
        self.system = System(self, "SYSTEM", self._driapis_by_name)
        # Setup Rooms
        self._room_ids = find_ids(self._driapis_by_name, REGEXP.ROOM)
        self._create_rooms()
        # Setup Sunblinds
        self._sunblind_ids = find_ids(self._driapis_by_name, REGEXP.SUNBLIND)
        self._create_sunblinds()
        # Setup Calendars
        self._calendar_ids = find_ids(self._calapis_by_name, REGEXP.CALENDAR)
        self._create_calendars()
        # Setup (generic) Devices
        all_prefixes = {idx.split(".")[0] for idx in self._driapis_by_name}
        unused_prefixes = all_prefixes - set(self._room_ids) - set(self._sunblind_ids)
        # unused_prefixes.remove("SYSTEM") # Add SYSTEM to generic Device list as well
        self._device_ids = list(unused_prefixes)
        self._create_devices()

    def _get_xml(self) -> ElementTree.Element:
        response = requests.get(self._url + XML_PATH)
        if response.status_code != 200:
            raise ConnectionError(f"Error getting XML: {response.status_code}")
        return ElementTree.fromstring(response.content)

    def _get_apis(self) -> list[API]:
        xml = self._get_xml()
        apis = []
        for child in xml:
            apis.append(match_api(child.attrib))
        return apis

    def _create_rooms(self):
        self.rooms = {}
        for room_id in self._room_ids:
            room = Room(
                self,
                room_id,
                self._driapis_by_name,
            )
            self.rooms[room_id] = room

    def _create_sunblinds(self):
        self.sunblinds = {}
        for sunblind_id in self._sunblind_ids:
            sunblind = Sunblind(self, sunblind_id, self._driapis_by_name)
            self.sunblinds[sunblind_id] = sunblind

    def _create_calendars(self):
        self.calendars = {}
        for calendar_id in self._calendar_ids:
            calendar = Calendar(self, calendar_id, self._calapis_by_name)
            self.calendars[calendar_id] = calendar

    def _create_devices(self):
        self.devices = {}
        for device_id in self._device_ids:
            device = Device(self, device_id, self._driapis_by_name)
            self.devices[device_id] = device

    def api_call(self, request_set: RequestSet) -> ResponseSet:
        # Split GET to chunks
        chunks = split_getters_to_chunks(request_set.getters)

        path_set = ";".join([f"{r.path}={r.value}" for r in request_set.setters])

        responses = {}
        for chunk in chunks:
            url = f"{self._url}{API_PATH}{chunk}"
            r = requests.get(url)
            r.encoding = self.encoding
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
        request = api.get_request()
        response = self.api_call(request)
        return api.parse(response)

    def update_status(self) -> State:
        get_system = self.system.get_request
        get_rooms = reduce(lambda x, y: x + y, (r.get_request for r in self.rooms.values()))
        get_sunblinds = reduce(lambda x, y: x + y, (r.get_request for r in self.sunblinds.values()))
        get_devices = reduce(lambda x, y: x + y, (r.get_request for r in self.devices.values()))
        request = get_system + get_rooms + get_sunblinds + get_devices
        response = self.api_call(request)
        return State(
            system=self.system.parse_state(response),
            rooms={r_id: r.parse_state(response) for r_id, r in self.rooms.items()},
            sunblinds={s_id: s.parse_state(response) for s_id, s in self.sunblinds.items()},
            devices={d_id: d.parse_state(response) for d_id, d in self.devices.items()},
        )

    def get_calendar_names(self):
        pairs = []
        for idx, c in self.calendars.items():
            n = c.do_update()["Name"]
            pairs.append((idx, n))
        return pairs
