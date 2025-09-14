from dataclasses import dataclass

from ..constants import (
    MOVE_TIME_UNITS,
    SUNBLIND_COMMANDS,
    SUNBLIND_EXTENDED,
    SUNBLIND_TILT_CLOSED,
    SUNBLIND_VARS,
    TILT_TIME_OFFSET,
)
from ..utils import CoerceTypesMixin
from .base import StatefulUnit


@dataclass
class SunblindState(CoerceTypesMixin):
    failure: bool
    out_up_1: bool
    out_up_2: bool
    out_dn_1: bool
    out_dn_2: bool
    manual_up: bool
    manual_dn: bool
    en: bool
    dis: bool
    urgent_up: bool
    sun_dn: bool
    dn: bool
    up: bool
    step_dn: bool
    step_up: bool
    calendar_en: bool
    move_time: int
    reverse_time: int
    tilt_time: int
    short_down_time: int
    step_time: int
    full_time_time: int
    name: str
    dead_time: int
    state: int
    rotation: int
    position: int
    command: int
    state2: int


class Sunblind(StatefulUnit[SunblindState]):
    @classmethod
    def _var_map(cls):
        return SUNBLIND_VARS

    @classmethod
    def _state_cls(cls):
        return SunblindState

    def set_command(self, command: int):
        r = self.apis["command"].set_request(str(command))
        self._controller.api_call(r)

    def set_step_time(self, step_time: int):
        r = self.apis["step_time"].set_request(str(step_time))
        self._controller.api_call(r)

    def set_rotation(self, rotation: int):
        if rotation < 0 or rotation > SUNBLIND_TILT_CLOSED:
            raise ValueError(f"Rotation must be between 0 and {SUNBLIND_TILT_CLOSED}")

        self.set_command(SUNBLIND_COMMANDS.STOP)
        current = self.do_update()
        if current.rotation != rotation:
            diff = float(rotation - current.rotation)
            step_time = abs(int(diff / SUNBLIND_TILT_CLOSED * current.full_time_time)) + TILT_TIME_OFFSET
            self.set_step_time(step_time)
            command = SUNBLIND_COMMANDS.STEP_DOWN if diff > 0 else SUNBLIND_COMMANDS.STEP_UP
            self.set_command(command)

    def set_position(self, position: int):
        if position < 0 or position > SUNBLIND_EXTENDED:
            raise ValueError(f"Position must be between 0 and {SUNBLIND_EXTENDED}")

        # use generic commands
        if position == 0:
            self.set_command(SUNBLIND_COMMANDS.UP)

        if position == SUNBLIND_EXTENDED:
            self.set_command(SUNBLIND_COMMANDS.DOWN)

        self.set_command(SUNBLIND_COMMANDS.STOP)
        current = self.do_update()
        if current.position != position:
            diff = float(position - current.position)
            tilt_target = SUNBLIND_TILT_CLOSED if diff > 0 else 0
            tilt_diff = float(tilt_target - current.rotation)
            step_time = (
                abs(
                    int(diff / SUNBLIND_EXTENDED * current.move_time * MOVE_TIME_UNITS)
                    + int(tilt_diff / SUNBLIND_TILT_CLOSED * current.full_time_time)
                )
                + TILT_TIME_OFFSET
            )
            self.set_step_time(step_time)
            command = SUNBLIND_COMMANDS.STEP_DOWN if diff > 0 else SUNBLIND_COMMANDS.STEP_UP
            self.set_command(command)
