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

    failure: bool
    relay_check: bool
    hdo: bool
    holiday_on: bool
    holiday_off: bool
    holiday_on_confirm: bool
    holiday_off_confirm: bool
    system_ok: bool
    out_temperature: float  # Note: Typo in the original XML source
    fltr: float
    accuracy: float
    no_move_time: float
    moving_time: float
    link_t1_can: str
    link_t2_can: str
    user1: bool
    user2: bool
    user3: bool
    user4: bool
    link_t3_can: str
    open_all_valves: str
    latitude: float
    longitude: float
    system_time: int
    system_time_no_sec: int
    departure_time: int
    departure_active: bool
    arrival_time: int
    arrival_active: bool
    holiday_active: bool
    set_heat: bool
    set_cool: bool
    set_trunk: bool
    trunk_active: bool
    set_user1: bool
    set_user2: bool
    set_user3: bool
    set_user4: bool
    heat_on: bool
    cool_on: bool
    on_battery: bool
    battery_failure: bool
    system_on: bool
    drivers_ok: bool
    devices_ok: bool
    all_ok: bool
    time_minutes: float
    time_minutes_ws: float
    sunrise_minutes: float
    sunset_minutes: float
    set_person_home: int
    set_coming_home: int
    set_room_party: int
    person1_home: bool
    person2_home: bool
    person3_home: bool
    person4_home: bool
    person5_home: bool
    person6_home: bool
    person7_home: bool
    person8_home: bool
    open_window: bool
    light_on: bool
    at_least_one_up: bool
    at_least_one_down: bool
    sw_version: str
    sw_subversion: str
    booter_sw_version: str
    cpu_temperature: float
    dw_temperature: float
    vbat: float
    u24: str
    crc32: str
    crc32_calendars: str
    system_command: str
    loop_time_us: int
    fast_drivers_us: int
    slow_drivers_us: int
    free_time_us: int
    skipped_cycles: int
    hour: int
    minute: int
    second: int
    day: int
    month: int
    year: int
    week_day: int
    summer_time: int
    minute_in_day: int
    minute_in_day_corr: int


class System(StatefulUnit[SystemState]):
    @classmethod
    def _var_map(cls):
        return SYSTEM_VARS

    @classmethod
    def _state_cls(cls):
        return SystemState
