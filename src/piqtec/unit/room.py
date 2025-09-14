import contextlib
from dataclasses import dataclass

from ..constants import ROOM_VARS
from ..utils import CoerceTypesMixin
from .base import StatefulUnit


@dataclass
class RoomState(CoerceTypesMixin):
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
        super().__post_init__()
        # Handle requested_temperature separately
        with contextlib.suppress(ValueError):
            self.requested_temperature = float(self.requested_temperature)


class Room(StatefulUnit[RoomState]):
    @classmethod
    def _var_map(cls):
        return ROOM_VARS

    @classmethod
    def _state_cls(cls):
        return RoomState

    def set_room_mode(self, room_mode: int):
        r = self.apis["room_mode"].set_request(str(room_mode))
        self._controller.api_call(r)

    def set_correction_mode(self, correction_mode: int):
        r = self.apis["correction_status"].set_request(str(correction_mode))
        self._controller.api_call(r)

    def set_correction_time(self, correction_time: int):
        """Set correction time in 5-minute intervals."""
        r = self.apis["correction_time"].set_request(str(correction_time))
        self._controller.api_call(r)

    def set_correction_temperature(self, correction_temperature: float):
        r = self.apis["correction_temperature"].set_request(str(correction_temperature))
        self._controller.api_call(r)

    def set_calendar(self, calendar_number: int):
        r = self.apis["calendar_number"].set_request(str(calendar_number))
        self._controller.api_call(r)
