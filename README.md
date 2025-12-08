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
The API requests are batched so the endpoint is not overloaded, and the return does not overflow the buffer (see:
`piqtec.controller.Controller.api_call` and `piqtec.constants.MAX_RESPONSE_LENGTH`).

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
from piqtec.controller import Controller

c = Controller("controller_ip_or_hostname:port")
state = c.update_status()
print(state)
```

### Example commands

(for all possible "nice" commands see unit modules)

```python
from piqtec.controller import Controller
from piqtec.constants import ROOM_MODES

c = Controller("controller_ip_or_hostname:port")

c.rooms["<ROOM_ID>"].set_room_mode(ROOM_MODES.CALENDAR)
```

### Example raw API usage

```python
from piqtec.controller import Controller

c = Controller("controller_ip_or_hostname:port")
r = c.devices["<DEVICE_ID>"].switch_apis["<SWITCH_ID>"].set_request("<VALUE>")
c.api_call(r)
```

## License

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

For non-commercial use only. Relicensing is available upon request.

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]


[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/

[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png

[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg
