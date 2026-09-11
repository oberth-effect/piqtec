# Piqtec: An IQtec smart-home Python inteface

[![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa] ![PyPI - Version](https://img.shields.io/pypi/v/piqtec)

A Python interface for the IQtec / Kobra smart home solutions.  
(IQtec is a small smart-home vendor based in the Czech Republic.)

It was written for my home use, and while I tried to keep things general might need some tweaks before being useful (PRs
welcome).
The functionality of the API this package relies on is reverse-engineered without any access to official documentation,
your mileage may vary.

The package aims to make the API accessible in Python and convert the values to correct datatypes, based on descriptions
from the `data.xml` file fetched from the endpoint.

Intended to be used
with [this custom Home Assistant integration.](https://github.com/oberth-effect/iqtec-ha-integration)

## Supported Devices

- System Controls (`piqtec.unit.system`),
- Room Controls (`piqtec.unit.room`),
- Covers/Window Controls (`piqtec.unit.sunblind`),
- Calendars (`piqtec.unit.calendar`),
- Other devices mapped from `data.xml` on the best effort basis (`piqtec.unit.device`).

## Usage

### Print whole current state

```python
from piqtec import Controller

with Controller("controller_ip_or_hostname:port") as c:
    print(c.update())
```

### Example commands

(for all possible "nice" commands see unit modules)

```python
from piqtec import Controller, RoomMode

c = Controller("controller_ip_or_hostname:port")

c.rooms["<ROOM_ID>"].set_room_mode(RoomMode.CALENDAR)
c.rooms["<ROOM_ID>"].set_manual_temperature(21.5, correction_time=24)
```

### Example raw API usage

```python
from piqtec import Controller

c = Controller("controller_ip_or_hostname:port")

api = c.devices["<DEVICE_ID>"].switch_apis["<VARIABLE_NAME>"]
c.api_call(api.set_request("<VALUE>"))
print(c.read(api))
```

### Editing a calendar

A calendar is a fixed grid of 8 days by 8 edges, but the useful view is the list
of transitions: the moments the level changes. `piqtec` packs that list back into
the grid for you.

```python
from piqtec import CalendarLevel, Controller

c = Controller("controller_ip_or_hostname:port")
cal = c.calendars["_CALENDAR_00"]

state = cal.update()
monday = state.days[0]
print([(e.minutes, CalendarLevel(e.level).name) for e in monday.transitions])

monday.add_transition(250, CalendarLevel.NOBODY)   # 20:50
monday.move_transition(1, 90)                      # 07:30
state.temperatures[2] = 21.0                       # heating "Day" setpoint
state.name = "Weekdays"

cal.write(state)     # validates, then replaces the whole calendar
```

Levels are `NOBODY = 0`, `NIGHT = 1` and `DAY = 2`, matching the controller's
`OutNobody`, `OutNight` and `OutDay` outputs. `Temperatures` holds six setpoints:
those three while heating, then the same three while cooling. Day 0 is Monday,
days 1-6 run to Sunday, and day 7 is the separately selectable "day 8".

Times are counted in 5 minute steps from midnight, so a day spans 0..288. The
first transition is pinned to midnight, the final edge only terminates the day,
and a day therefore holds between 1 and 7 transitions.

`CalendarState.periods()` projects the weekly pattern onto real dates, resolving
"follows Monday", merging a period that runs past midnight, and keeping
wall-clock times across a daylight-saving change:

```python
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

monday = datetime(2026, 9, 14, tzinfo=ZoneInfo("Europe/Prague"))
for period in state.periods(monday, monday + timedelta(days=1)):
    print(period.start, period.end, CalendarLevel(period.level).name)
```

Day 7 is never dated: the controller selects it through an input, not a weekday.

## Notes on the protocol

The controller's HTTP interface has two hard limits, both of which fail *silently*:

- the request line must fit in a single TCP segment — 1445 bytes of path,
  beyond which the connection is dropped without a reply;
- a reply is produced from a 4 KiB buffer and is cut off at 4092 bytes, at a
  line boundary and without any error.

`Controller.api_call` therefore packs a request set into as few round-trips as
both budgets allow, estimating the reply size from the types declared in
`data.xml` (see `piqtec.constants.MAX_REQUEST_BYTES` and `MAX_RESPONSE_BYTES`).

Written values are percent-encoded, but only as far as the protocol requires:
escaping everything would push a calendar payload past the request limit.

Values are decoded according to the `type` attribute of `data.xml`. Variables the
controller cannot currently supply come back as `"!off"` and are decoded to
`None`, as are variables absent from a given installation.

The `access` attribute names three roles, upper case for write and lower case for
read: `P` projectant, `U` user, `S` service. This package assumes the user role,
so a variable writable only by a projectant or by service (`PS`, `Ps`, `S`) is
treated as read-only even though the control interface itself has no
authentication and would very likely accept the write.

## Versioning

Releases are numbered in step with
[the Home Assistant integration](https://github.com/oberth-effect/iqtec-ha-integration),
which pins the matching version exactly. A release of one is a release of both,
even when only one of them changed.

## Errors

Everything raised by this package derives from `piqtec.IQtecError`; `requests`
exceptions never escape. Connection problems surface as `IQtecConnectionError`.

## License

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

For non-commercial use only. Relicensing is available upon request.

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]


[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/

[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png

[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg
