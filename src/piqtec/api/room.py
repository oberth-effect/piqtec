import contextlib
from dataclasses import dataclass, fields

from ..constants import DRIVER_PREFIX, ROOM_VARS
from ..type_helpers import Get, ResponseSet
from .generic import API, DriverAPI


@dataclass
class RoomState:
    fan_command: int
    name: str
    eco_mode: bool
    holiday: bool
    important: bool
    calendar_number: int
    room_mode: int
    corr_time: int
    winter_holiday: float
    summer_holiday: float
    min_humidity: float
    max_humidity: float
    actual_temperature: float
    requested_temperature: float | str
    failure: bool
    humidity_problem: bool
    open_window: bool
    open_window_time: int
    open_window_midnight: bool
    at_home: bool
    weekend: bool
    key: bool
    humidity_low: bool
    humidity_high: bool
    heating: bool
    cooling: bool
    cooling_enabled: bool
    heating_enabled: bool
    cooling_mode: bool
    manual_correction: bool
    light_on: bool
    at_least_one_up: bool
    at_least_one_down: bool
    humidity: float
    first_symbol: int
    last_symbol: int
    heating_type: int
    correction_status: int
    correction_time: int
    correction_temperature: float
    calendar_temperature: float

    def __post_init__(self):
        # Try to coerce types
        for field in fields(self):
            if callable(field.type):
                with contextlib.suppress(ValueError):
                    if field.type is bool:
                        setattr(self, field.name, field.type(int(getattr(self, field.name))))
                    else:
                        setattr(self, field.name, field.type(getattr(self, field.name)))

        with contextlib.suppress(ValueError):
            # handle self.requested_temperature separately
            self.requested_temperature = float(self.requested_temperature)


class RoomAPI(API):
    room_id: str

    _drivers: dict[str, DriverAPI]
    _room_url: str

    def __init__(self, room_id: str, drivers: dict[str, DriverAPI]):
        self.room_id = room_id
        # Map room drivers
        self._drivers = {}
        for var in ROOM_VARS:
            d = drivers.get(f"{room_id}.{var.value}")
            if d:
                self._drivers[var.name] = d
                # # Dynamically create methods
                # setattr(self, f"get_{var.name}_request", self._drivers[var.name].create_get_request)
                # setattr(self, f"set_{var.name}_request", self._drivers[var.name].create_set_request)
                # setattr(self, f"parse_{var.name}t", self._drivers[var.name].parse)

        self._room_url = f"{DRIVER_PREFIX}/{self._drivers['name'].structure_id}"

    def create_get_request(self) -> Get:
        return Get(path=self._room_url, expected_length=len(self._drivers))

    def parse(self, response_set: ResponseSet):
        return RoomState(**{key: driver.parse(response_set) for key, driver in self._drivers.items()})
