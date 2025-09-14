# Piqtec: An IQtec smart-home Python inteface

[![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

This is a WIP implementation of Python interface to the IQtec / Kobra smart home solutions.
(IQtec is a small smart-home vendor based in the Czech Republic.)

It was written for my specific setup, and therefore might need tweaks before being useful.
The intended use-case is as a backend for Home Assistant Integration.
The functionality of the API this package relies on is reverse-engineered without any access to official documentation,
your mileage may vary.

## Usage

```python
from piqtec.controller import Controller

c = Controller("controller_ip_or_hostname:port")
state = c.update_status()
print(state)  # Prints state of the system, rooms and sunblinds
```

## License

This work is licensed under a
[Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International License][cc-by-nc-sa].

[![CC BY-NC-SA 4.0][cc-by-nc-sa-image]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/

[cc-by-nc-sa-image]: https://licensebuttons.net/l/by-nc-sa/4.0/88x31.png

[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg
