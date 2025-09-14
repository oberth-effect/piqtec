from dataclasses import dataclass

from ..constants import SYSTEM_VARS
from ..utils import CoerceTypesMixin
from .base import StatefulUnit


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


class System(StatefulUnit[SystemState]):
    @classmethod
    def _var_map(cls):
        return SYSTEM_VARS

    @classmethod
    def _state_cls(cls):
        return SystemState
