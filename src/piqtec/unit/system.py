"""System-wide controller state."""

from dataclasses import dataclass

from ..constants import SystemVar
from .base import StatefulUnit


@dataclass
class SystemState:
    failure: bool | None = None
    relay_check: bool | None = None
    hdo: bool | None = None
    holiday_on: bool | None = None
    holiday_off: bool | None = None
    holiday_on_confirm: bool | None = None
    holiday_off_confirm: bool | None = None
    system_ok: bool | None = None
    out_temperature: float | None = None
    fltr: int | None = None
    accuracy: float | None = None
    no_move_time: int | None = None
    moving_time: int | None = None
    link_t1_can: int | None = None
    link_t2_can: int | None = None
    user1: int | None = None
    user2: int | None = None
    user3: int | None = None
    user4: int | None = None
    link_t3_can: int | None = None
    open_all_valves: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    system_time: int | None = None
    system_time_no_sec: int | None = None
    departure_time: int | None = None
    departure_active: int | None = None
    arrival_time: int | None = None
    arrival_active: int | None = None
    holiday_active: int | None = None
    set_heat: int | None = None
    set_cool: int | None = None
    set_trunk: int | None = None
    trunk_active: int | None = None
    set_user1: int | None = None
    set_user2: int | None = None
    set_user3: int | None = None
    set_user4: int | None = None
    heat_on: bool | None = None
    cool_on: bool | None = None
    on_battery: bool | None = None
    battery_failure: bool | None = None
    system_on: bool | None = None
    drivers_ok: bool | None = None
    devices_ok: bool | None = None
    all_ok: bool | None = None
    time_minutes: int | None = None
    time_minutes_ws: int | None = None
    sunrise_minutes: int | None = None
    sunset_minutes: int | None = None
    set_person_home: int | None = None
    set_coming_home: int | None = None
    set_room_party: int | None = None
    person1_home: bool | None = None
    person2_home: bool | None = None
    person3_home: bool | None = None
    person4_home: bool | None = None
    person5_home: bool | None = None
    person6_home: bool | None = None
    person7_home: bool | None = None
    person8_home: bool | None = None
    open_window: bool | None = None
    light_on: bool | None = None
    at_least_one_up: bool | None = None
    at_least_one_down: bool | None = None
    sw_version: int | None = None
    sw_subversion: int | None = None
    booter_sw_version: int | None = None
    cpu_temperature: float | None = None
    dw_temperature: float | None = None
    vbat: float | None = None
    u24: float | None = None
    crc32: float | None = None
    crc32_calendars: float | None = None
    system_command: int | None = None
    loop_time_us: int | None = None
    fast_drivers_us: int | None = None
    slow_drivers_us: int | None = None
    free_time_us: int | None = None
    skipped_cycles: int | None = None
    hour: int | None = None
    minute: int | None = None
    second: int | None = None
    day: int | None = None
    month: int | None = None
    year: int | None = None
    week_day: int | None = None
    summer_time: bool | None = None
    minute_in_day: int | None = None
    minute_in_day_corr: int | None = None


class System(StatefulUnit[SystemState]):
    @classmethod
    def _var_map(cls) -> type[SystemVar]:
        return SystemVar

    @classmethod
    def _state_cls(cls) -> type[SystemState]:
        return SystemState
