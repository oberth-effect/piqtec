import contextlib
from dataclasses import dataclass, fields

from ..constants import DRIVER_PREFIX, SUNBLIND_VARS
from ..type_helpers import Get, ResponseSet
from .generic import API, DriverAPI


@dataclass
class SunblindState:
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

    def __post_init__(self):
        # Try to coerce types
        for field in fields(self):
            if callable(field.type):
                with contextlib.suppress(ValueError):
                    if field.type is bool:
                        setattr(self, field.name, field.type(int(getattr(self, field.name))))
                    else:
                        setattr(self, field.name, field.type(getattr(self, field.name)))


class SunblindAPI(API):
    sunblind_id: str

    _drivers: dict[str, DriverAPI]
    _sunblind_url: str

    def __init__(self, sunblind_id: str, drivers: dict[str, DriverAPI]):
        self.sunblind_id = sunblind_id
        # Map room drivers
        self._drivers = {}
        for var in SUNBLIND_VARS:
            d = drivers.get(f"{sunblind_id}.{var.value}")
            if d:
                self._drivers[var.name] = d

        self._sunblind_url = f"{DRIVER_PREFIX}/{self._drivers['name'].structure_id}"

    def create_get_request(self) -> Get:
        return Get(path=self._sunblind_url, expected_length=len(self._drivers))

    def parse(self, response_set: ResponseSet):
        return SunblindState(**{key: driver.parse(response_set) for key, driver in self._drivers.items()})
