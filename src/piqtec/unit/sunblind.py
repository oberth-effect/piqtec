"""Sunblind / window cover control."""

from dataclasses import dataclass

from ..constants import (
    MOVE_TIME_UNITS,
    SUNBLIND_EXTENDED,
    SUNBLIND_TILT_CLOSED,
    TILT_TIME_OFFSET,
    SunblindCommand,
    SunblindVar,
)
from ..exceptions import InvalidValueError
from .base import StatefulUnit


@dataclass
class SunblindState:
    failure: bool | None = None
    out_up_1: bool | None = None
    out_up_2: bool | None = None
    out_dn_1: bool | None = None
    out_dn_2: bool | None = None
    manual_up: bool | None = None
    manual_dn: bool | None = None
    en: bool | None = None
    dis: bool | None = None
    urgent_up: bool | None = None
    sun_dn: bool | None = None
    dn: bool | None = None
    up: bool | None = None
    step_dn: bool | None = None
    step_up: bool | None = None
    calendar_en: bool | None = None
    move_time: int | None = None
    reverse_time: int | None = None
    tilt_time: int | None = None
    short_down_time: int | None = None
    step_time: int | None = None
    full_time_time: int | None = None
    name: str | None = None
    dead_time: int | None = None
    state: int | None = None
    rotation: int | None = None
    position: int | None = None
    command: int | None = None
    state2: int | None = None


class Sunblind(StatefulUnit[SunblindState]):
    @classmethod
    def _var_map(cls) -> type[SunblindVar]:
        return SunblindVar

    @classmethod
    def _state_cls(cls) -> type[SunblindState]:
        return SunblindState

    def set_command(self, command: SunblindCommand) -> None:
        self.set_value("command", int(command))

    def set_step_time(self, step_time: int) -> None:
        self.set_value("step_time", step_time)

    def _step(self, step_time: int, command: SunblindCommand) -> None:
        """Move for a measured time; both writes go out in one request."""
        request = self._require("step_time").set_request(step_time) + self._require("command").set_request(int(command))
        self._controller.api_call(request)

    def set_rotation(self, rotation: int) -> None:
        if not 0 <= rotation <= SUNBLIND_TILT_CLOSED:
            raise InvalidValueError(f"Rotation must be between 0 and {SUNBLIND_TILT_CLOSED}")

        self.set_command(SunblindCommand.STOP)
        current = self.update()
        if current.rotation is None or current.full_time_time is None or current.rotation == rotation:
            return

        diff = float(rotation - current.rotation)
        step_time = abs(int(diff / SUNBLIND_TILT_CLOSED * current.full_time_time)) + TILT_TIME_OFFSET
        command = SunblindCommand.STEP_DOWN if diff > 0 else SunblindCommand.STEP_UP
        self._step(step_time, command)

    def set_position(self, position: int) -> None:
        if not 0 <= position <= SUNBLIND_EXTENDED:
            raise InvalidValueError(f"Position must be between 0 and {SUNBLIND_EXTENDED}")

        # The endpoints have dedicated commands that also normalise the tilt.
        if position == 0:
            self.set_command(SunblindCommand.UP)
            return
        if position == SUNBLIND_EXTENDED:
            self.set_command(SunblindCommand.DOWN)
            return

        self.set_command(SunblindCommand.STOP)
        current = self.update()
        if current.position is None or current.move_time is None or current.position == position:
            return

        diff = float(position - current.position)
        # Moving also tilts the slats, so the travel time is corrected for the
        # tilt still to come. With the rotation (or its timing) unknown no
        # correction is applied, matching set_rotation, rather than assuming the
        # slats are open and overshooting by a full tilt when they were closed.
        tilt_target = SUNBLIND_TILT_CLOSED if diff > 0 else 0
        if current.rotation is None or current.full_time_time is None:
            tilt_time = 0
        else:
            tilt_time = int((tilt_target - current.rotation) / SUNBLIND_TILT_CLOSED * current.full_time_time)
        move_time = int(diff / SUNBLIND_EXTENDED * current.move_time * MOVE_TIME_UNITS)
        step_time = abs(move_time + tilt_time) + TILT_TIME_OFFSET
        command = SunblindCommand.STEP_DOWN if diff > 0 else SunblindCommand.STEP_UP
        self._step(step_time, command)
