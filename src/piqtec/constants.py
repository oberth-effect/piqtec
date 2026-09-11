"""Protocol constants, variable maps and value decoding rules."""

from collections.abc import Callable
from enum import IntEnum, StrEnum
from typing import Any

API_PATH = "/control/?"

XML_PATH = "/proj/data.xml"

DEFAULT_ENCODING = "Windows-1250"

DEFAULT_TIMEOUT = 5.0

# The firmware reads the request line out of a single TCP segment and replies out
# of a 4 KiB buffer. Measured limits are 1445 bytes of path (a 1460 byte request
# line) and 4092 bytes of response; exceeding the first drops the connection and
# exceeding the second truncates the reply silently, at a line boundary.
MAX_REQUEST_BYTES = 1400

MAX_RESPONSE_BYTES = 3800

# Category prefixes of the /control/? address space.
DRIVER_PREFIX = "1"

CALENDAR_PREFIX = "2"

ROOM_PREFIX = "3"

DEVICE_PREFIX = "5"

SCENARIO_PREFIX = "8"

# A leading "!" marks a variable the controller cannot currently supply,
# for example "!off" for a probe that is switched off.
SENTINEL_PREFIX = "!"

# Characters left un-escaped in a written value. ";" and "=" delimit the
# protocol itself and must stay encoded, as must "&", "+", "#" and "%"; keeping
# the rest raw is what lets a calendar payload fit in the request line.
VALUE_SAFE_CHARS = "[]:,/?@!$'()*"

# Calendars are a fixed 8 days of 8 edges. Day 0 is Monday, days 1-6 run to
# Sunday and day 7 is the separately selectable "day 8". Times are counted in
# 5 minute steps, so a day spans 0..288 and both ends are pinned.
CALENDAR_DAYS = 8
CALENDAR_EDGES = 8
CALENDAR_DAY_END = 288
CALENDAR_TIME_STEP_MINUTES = 5
CALENDAR_TEMPERATURES = 6


class CalendarType(StrEnum):
    TEMPERATURE = "TEMPERATURE"
    BLIND = "BLIND"
    ON_OFF = "ON_OFF"
    VALUE = "VALUE"
    ON_OFF2 = "ON_OFF2"


class CalendarLevel(IntEnum):
    """The three outputs a calendar drives (OutNobody, OutNight, OutDay)."""

    NOBODY = 0
    NIGHT = 1
    DAY = 2


#: Calendar types that only ever show two states; NIGHT reads as NOBODY there.
TWO_STATE_CALENDARS = frozenset({CalendarType.ON_OFF, CalendarType.ON_OFF2})


class REGEXP:
    ROOM = r"^R\d{1,2}$"
    SUNBLIND = r"\w{0,}\_SUNBLIND\w{0,}"
    CALENDAR = r"_CALENDAR_\d{2}$"


FAILURE_VAR = "_Failure"


def _to_bool(value: str) -> bool:
    return bool(int(value))


def _to_str(value: str) -> str:
    return value.strip()


# Decoders keyed on the type attribute declared in data.xml. The controller
# already returns human-readable values, so this only picks the Python type.
VALUE_DECODERS: dict[str, Callable[[str], Any]] = {
    "bool": _to_bool,
    "byte": int,
    "word": int,
    "short": int,
    "long": int,
    "datetime": int,
    "color": int,
    "float": float,
    "Temperature": float,
    "Humidity": float,
    "Percentage": float,
    "AD_DA": float,
    "flow": float,
    "string8": _to_str,
    "string10": _to_str,
    "string16": _to_str,
    "calendar": _to_str,
    "OnOff": int,
    "OnOffAuto": int,
    "RoomMode": int,
    "CorrectionStatus": int,
    "FanCommand": int,
    "KeyLED": int,
    "CalendarIndex": int,
    "FiveMinutes": int,
    "SunSchedule": int,
    "SUNBLIND_STATE": int,
    "SUNBLIND_COMMAND": int,
    "calendarcommand": int,
    "DwType": int,
    "DwTypeExt": int,
    "FaultState": int,
}

DEFAULT_VALUE_BYTES = 12

# Upper bound on the encoded length of a value, used to budget response size.
VALUE_MAX_BYTES: dict[str, int] = {
    "bool": 1,
    "byte": 3,
    "word": 5,
    "short": 6,
    "long": 11,
    "datetime": 11,
    "string8": 8,
    "string10": 10,
    "string16": 16,
    "calendar": 1100,
}


class SystemVar(StrEnum):
    failure = "_Failure"
    relay_check = "RelayCheck"
    hdo = "HDO"
    holiday_on = "HolidayON"
    holiday_off = "HolidayOFF"
    holiday_on_confirm = "HolidayONconfirm"
    holiday_off_confirm = "HolidayOFFconfirm"
    system_ok = "SystemOK"
    out_temperature = "OutTempearture"  # Note: Typo in the original XML source
    fltr = "Filter"
    accuracy = "Accuracy"
    no_move_time = "NoMoveTime"
    moving_time = "MovingTime"
    link_t1_can = "LinkT1_CAN"
    link_t2_can = "LinkT2_CAN"
    user1 = "USER1"
    user2 = "USER2"
    user3 = "USER3"
    user4 = "USER4"
    link_t3_can = "LinkT3_CAN"
    open_all_valves = "OpenAllValves"
    latitude = "Latitude"
    longitude = "Longtitude"  # Note: Typo in the original XML source
    system_time = "SystemTime"
    system_time_no_sec = "SystemTimeNoSec"
    departure_time = "DepartureTime"
    departure_active = "DepartureActive"
    arrival_time = "ArrivalTime"
    arrival_active = "ArrivalActive"
    holiday_active = "HolidayActive"
    set_heat = "SET_HEAT"
    set_cool = "SET_COOL"
    set_trunk = "SET_TRUNK"
    trunk_active = "TRUNK_ACTIVE"
    set_user1 = "SET_USER1"
    set_user2 = "SET_USER2"
    set_user3 = "SET_USER3"
    set_user4 = "SET_USER4"
    heat_on = "HeatOn"
    cool_on = "CoolOn"
    on_battery = "OnBattery"
    battery_failure = "BatteryFailure"
    system_on = "SystemOn"
    drivers_ok = "DriversOk"
    devices_ok = "DevicesOk"
    all_ok = "AllOk"
    time_minutes = "TIME_MINUTES"
    time_minutes_ws = "TIME_MINUTES_WS"
    sunrise_minutes = "SUNRISE_MINUTES"
    sunset_minutes = "SUNSET_MINUTES"
    set_person_home = "SET_PERSON_HOME"
    set_coming_home = "SET_COMMING_HOME"  # Note: Typo in original XML source
    set_room_party = "SET_ROOM_PARTY"
    person1_home = "Person1home"
    person2_home = "Person2home"
    person3_home = "Person3home"
    person4_home = "Person4home"
    person5_home = "Person5home"
    person6_home = "Person6home"
    person7_home = "Person7home"
    person8_home = "Person8home"
    open_window = "OpenWindow"
    light_on = "LightOn"
    at_least_one_up = "AtLeastOneUp"
    at_least_one_down = "AtLeastOneDown"
    sw_version = "SWversion"
    sw_subversion = "SWsubversion"
    booter_sw_version = "BooterSWversion"
    cpu_temperature = "CPUtemperature"
    dw_temperature = "DWtemperature"
    vbat = "VBAT"
    u24 = "U24"
    crc32 = "_CRC32"
    crc32_calendars = "_CRC32_Calendars"
    system_command = "SystemCommand"
    loop_time_us = "LoopTime_us"
    fast_drivers_us = "FastDrivers_us"
    slow_drivers_us = "SlowDrivers_us"
    free_time_us = "FreeTime_us"
    skipped_cycles = "SkippedCycles"
    hour = "Hour"
    minute = "Minute"
    second = "Second"
    day = "Day"
    month = "Month"
    year = "Year"
    week_day = "WeekDay"
    summer_time = "SummerTime"
    minute_in_day = "MinuteInDay"
    minute_in_day_corr = "MinuteInDayCorr"


class RoomVar(StrEnum):
    fan_command = "FanCommand"
    name = "_RoomName"
    eco_mode = "EcoMode"
    holiday = "InHoliday"
    important = "ImportantRoom"
    calendar_number = "CalendarNumber"
    room_mode = "RoomMode"
    corr_time = "CorrTime"
    winter_holiday = "WinterHoliday"
    summer_holiday = "SummerHoliday"
    min_humidity = "MinHumidity"
    max_humidity = "MaxHumidity"
    actual_temperature = "ActualTemperature"
    requested_temperature = "RequestedTemperature"
    failure = "Failure"
    humidity_problem = "HumidityProblem"
    open_window = "OpenWindow"
    open_window_time = "OpenWindowTime"
    open_window_midnight = "OpenWindowMidnight"
    at_home = "AtHome"
    weekend = "WeekEnd"
    key = "Key"
    humidity_low = "HumidityLow"
    humidity_high = "HumidityHigh"
    heating = "Heating"
    cooling = "Cooling"
    cooling_enabled = "CoolingEnabled"
    heating_enabled = "HeatingEnabled"
    cooling_mode = "CoolingMode"
    manual_correction = "ManualCorrection"
    light_on = "LightOn"
    at_least_one_up = "AtLeastOneUp"
    at_least_one_down = "AtLeastOneDown"
    humidity = "Humidity"
    first_symbol = "FirstSymbol"
    last_symbol = "LastSymbol"
    heating_type = "HeatingType"
    correction_status = "CorrectionStatus"
    correction_time = "CorrectionTime"
    correction_temperature = "CorrectionTemp"
    calendar_temperature = "CalendarTemperature"


class RoomMode(IntEnum):
    CALENDAR = 0
    ANTIFREEZE = 1
    HOLIDAY = 2
    OFF = 3


class RoomCorrectionMode(IntEnum):
    NONE = 0
    DAY = 1
    NIGHT = 2
    MANUAL = 3


class SunblindVar(StrEnum):
    failure = "_Failure"
    out_up_1 = "OutUP_1"
    out_up_2 = "OutUP_2"
    out_dn_1 = "OutDN_1"
    out_dn_2 = "OutDN_2"
    manual_up = "Manual_UP"
    manual_dn = "Manual_DN"
    en = "EN"
    dis = "DIS"
    urgent_up = "Urgent_UP"
    sun_dn = "Sun_DN"
    dn = "DN"
    up = "UP"
    step_dn = "StepDN"
    step_up = "StepUP"
    calendar_en = "CalendarEN"
    move_time = "MoveTime"  # tracks position
    reverse_time = "ReverseTime"  # waiting between changes of a direction
    tilt_time = "TiltTime"
    short_down_time = "ShortDownTime"
    step_time = "StepTime"
    full_time_time = "FullTimeTime"  # tracks tilt
    name = "Name"
    dead_time = "DeadTime"  # added to every movement
    state = "State"
    rotation = "Rotation"
    position = "Position"
    command = "COMMAND"
    state2 = "_state"


class SunblindCommand(IntEnum):
    UP = 0  # move_time, forces position and rotation to 0
    DOWN = 1  # move_time, forces position and rotation to max
    DOWN_TILT = 2  # move_time + reverse_time (waiting) + tilt_time
    STOP = 3
    TILT_OPEN = 4  # short_down_time + reverse_time + tilt_time
    STEP_UP = 5  # step_time
    STEP_DOWN = 6  # step_time
    UP_AND_DISABLE = 7  # move_time
    ENABLE = 8
    TILT_OPEN_SHORT = 9  # tilt_time


SUNBLIND_TILT_CLOSED = 180
SUNBLIND_EXTENDED = 1000

MOVE_TIME_UNITS = 1000
TILT_TIME_OFFSET = 25
