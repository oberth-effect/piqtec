"""Room (heating zone) control."""

from dataclasses import dataclass

from ..constants import RoomCorrectionMode, RoomMode, RoomVar
from .base import StatefulUnit


@dataclass
class RoomState:
    fan_command: int | None = None
    name: str | None = None
    eco_mode: bool | None = None
    holiday: bool | None = None
    important: bool | None = None
    calendar_number: int | None = None
    room_mode: int | None = None
    corr_time: int | None = None
    winter_holiday: float | None = None
    summer_holiday: float | None = None
    min_humidity: float | None = None
    max_humidity: float | None = None
    actual_temperature: float | None = None
    requested_temperature: float | None = None
    failure: bool | None = None
    humidity_problem: bool | None = None
    open_window: bool | None = None
    open_window_time: int | None = None
    open_window_midnight: bool | None = None
    at_home: bool | None = None
    weekend: bool | None = None
    key: bool | None = None
    humidity_low: bool | None = None
    humidity_high: bool | None = None
    heating: bool | None = None
    cooling: bool | None = None
    cooling_enabled: bool | None = None
    heating_enabled: bool | None = None
    cooling_mode: bool | None = None
    manual_correction: bool | None = None
    light_on: bool | None = None
    at_least_one_up: bool | None = None
    at_least_one_down: bool | None = None
    humidity: float | None = None
    first_symbol: int | None = None
    last_symbol: int | None = None
    heating_type: int | None = None
    correction_status: int | None = None
    correction_time: int | None = None
    correction_temperature: float | None = None
    calendar_temperature: float | None = None


class Room(StatefulUnit[RoomState]):
    @classmethod
    def _var_map(cls) -> type[RoomVar]:
        return RoomVar

    @classmethod
    def _state_cls(cls) -> type[RoomState]:
        return RoomState

    def set_room_mode(self, room_mode: RoomMode) -> None:
        self.set_value("room_mode", int(room_mode))

    def set_correction_mode(self, correction_mode: RoomCorrectionMode) -> None:
        self.set_value("correction_status", int(correction_mode))

    def set_correction_time(self, correction_time: int) -> None:
        """Set correction time in 5-minute intervals."""
        self.set_value("correction_time", correction_time)

    def set_correction_temperature(self, correction_temperature: float) -> None:
        self.set_value("correction_temperature", correction_temperature)

    def set_calendar(self, calendar_number: int) -> None:
        self.set_value("calendar_number", calendar_number)

    def set_manual_temperature(self, temperature: float, correction_time: int) -> None:
        """Hold ``temperature`` for ``correction_time`` 5-minute intervals.

        Mode, duration and setpoint are written in a single request so the
        controller applies them in order and never observes a half-set state.
        """
        request = (
            self.apis["correction_status"].set_request(int(RoomCorrectionMode.MANUAL))
            + self.apis["correction_time"].set_request(correction_time)
            + self.apis["correction_temperature"].set_request(temperature)
        )
        self._controller.api_call(request)
