from datetime import datetime
from typing import Callable

from .constants import (
    ROOM_API,
    ROOM_MODE,
    SUNBLIND_API,
    SUNBLIND_COMMANDS,
    SUNBLIND_TILT_CLOSED,
    SUNBLIND_FULL_EXTENDED,
    SUNBLIND_TILT_OPEN,
)
from .exceptions import InvalidSetCommand, UpdateError, ConfigurationError
from .helpers import encode_timeout, decode_timeout


class BaseDevice:
    address: str
    name: str
    _value_setter: Callable  # Function to call for making set requests
    api_addresses: dict
    last_update: datetime = None
    waiting_for_update: bool = True

    def __init__(self, address: str, setter: Callable, name: str):
        self.address = address
        self.name = name
        self._value_setter = setter

    def __repr__(self) -> str:
        props = {prop: getattr(self, prop, t) for prop, t in
                 self.__annotations__.items() | BaseDevice.__annotations__.items()}
        return f"{self.__class__.__name__}:{props}"

    @classmethod
    def get_properties(cls):
        return [attr for attr in cls.__annotations__ if not attr.startswith('_')]

    def parse_update(self, data: dict):
        prop_list = self.get_properties()
        update_key_error = []

        for prop in prop_list:
            try:
                full_address = f"{self.address}/{self.api_addresses[prop]}"
            except KeyError:
                raise ConfigurationError(self.name, self.address, f"Key '{prop}' missing in API addresses")
            try:
                d = data[full_address]
            except KeyError:
                update_key_error.append(prop)
            else:
                fun = getattr(self, f"update_{prop}", None)
                if fun is not None:
                    fun(d)
                else:
                    t = self.__annotations__[prop]
                    if t == bool:
                        t = lambda x: bool(int(x))
                    setattr(self, prop, t(d))

        if len(update_key_error) == 0:
            self.waiting_for_update = False
            self.last_update = datetime.now()
        else:
            raise UpdateError(self.name, self.address, f"Update failed for following values: {update_key_error}")

    def _set_values(self, suffixes: list, values: list):
        self.waiting_for_update = True
        self._value_setter({f"{self.address}/{suf}": val for suf, val in zip(suffixes, values)})

    def _set_value(self, suffix: str, value: str):
        self._set_values([suffix, ], [value, ])


class Room(BaseDevice):
    internal_name: str
    temperature: float
    requested_temperature: float
    mode: int
    timeout: datetime
    _timeout: int
    calendar_number: int
    heating_on: bool

    api_addresses = ROOM_API

    def update_timeout(self, s: str):
        """Function that handles update of timeout property"""
        self._timeout = int(s)
        self.timeout = decode_timeout(self._timeout)

    def set_mode(self, mode: int):
        """Sets the mode of the room. constants.ROOM_MODE is a list of all modes"""
        if mode in ROOM_MODE.values():
            self._set_value(ROOM_API['mode'], str(mode))
        else:
            raise InvalidSetCommand(self.name, self.address, f"Value '{mode}' is not a valid room mode!")

    def set_temperature(self, temp: float):
        """Sets requested_temperature if room is in manual mode"""
        if self.mode == ROOM_MODE['manual']:
            self._set_value(ROOM_API['requested_temperature'], str(temp))
        else:
            raise InvalidSetCommand(self.name, self.address, f"Temperature cannot be set in mode {self.mode}!")

    def set_calendar(self, cal: int):
        """Sets room internal calendar"""
        self._set_value(ROOM_API['calendar_number'], str(cal))

    def set_timeout(self, timeout: datetime):
        """Sets timeout for current mode (not applicable to calendar mode)"""
        if timeout < datetime.now():
            t = encode_timeout(timeout)
            self._set_value(ROOM_API['timeout'], str(t))
        else:
            raise InvalidSetCommand(self.name, self.address, f"Timeout must be in the future!")


class Sunblind(BaseDevice):
    move_time: int
    reverse_time: int
    tilt_time: int
    short_down_time: int
    step_time: int
    full_tilt_time: int
    position: int
    rotation: int
    disabled: bool

    api_addresses = SUNBLIND_API

    def _calculate_tilt_time(self, tilt: int) -> int:
        """Helper function that calculates tilt time"""
        diff = tilt - self.rotation
        return int(diff / SUNBLIND_TILT_CLOSED * self.full_tilt_time)

    def tilt(self, tilt: int):
        """Attempts to send exact timing to reach desired rotation position"""
        if tilt == 0:
            self.open()
        else:
            time = self._calculate_tilt_time(tilt)
            suffixes = [
                SUNBLIND_API['step_time'],
                SUNBLIND_API['command'],
            ]
            values = [
                abs(time),
                SUNBLIND_COMMANDS['step_down'] if time > 0 else SUNBLIND_COMMANDS['step_up']
            ]
            self._set_values(suffixes, values)

    def _calculate_move_time(self, pos):
        """Helper function that calculates move time"""
        diff = pos - self.position
        return int(float(diff) / SUNBLIND_FULL_EXTENDED * self.move_time * 1000 + self._calculate_tilt_time(
            SUNBLIND_TILT_CLOSED if diff > 0 else SUNBLIND_TILT_OPEN))

    def move(self, pos: int):
        """Attempts to send exact timing to reach desired position"""
        if pos == 0:
            self.up()
        elif pos == 1000:
            self.down()
        else:
            time = self._calculate_move_time(pos)
            suffixes = [
                SUNBLIND_API['step_time'],
                SUNBLIND_API['command'],
            ]
            values = [
                abs(time),
                SUNBLIND_COMMANDS['step_down'] if time > 0 else SUNBLIND_COMMANDS['step_up']
            ]
            self._set_values(suffixes, values)

    def stop(self):
        """Stops the sunblind"""
        self._set_value(SUNBLIND_API['command'], SUNBLIND_COMMANDS['stop'])

    def down(self):
        """Moves the sunblind all the way down"""
        self._set_value(SUNBLIND_API['command'], SUNBLIND_COMMANDS['down'])

    def up(self):
        """Moves the sunblind all the way up"""
        self._set_value(SUNBLIND_API['command'], SUNBLIND_COMMANDS['up'])

    def down_open(self):
        """Moves sunblind all the way down and opens it (move_time + reverse_time + tilt_time)"""
        self._set_value(SUNBLIND_API['command'], SUNBLIND_COMMANDS['down_open'])

    def open(self):
        """Opens the sunblind (short_down_time + reverse_time + tilt_time)"""
        self._set_value(SUNBLIND_API['command'], SUNBLIND_COMMANDS['open'])

    def up_and_disable(self):
        """Moves the sunblind all the way up and disables its operation"""
        self._set_value(SUNBLIND_API['command'], SUNBLIND_COMMANDS['up_and_disable'])

    def enable(self):
        """Re-enables sunblind operation"""
        self._set_value(SUNBLIND_API['command'], SUNBLIND_COMMANDS['enable'])

    def open_short(self):
        """Opens the sunblind without short_down_time (tilt_time)"""
        self._set_value(SUNBLIND_API['command'], SUNBLIND_COMMANDS['open_short'])
