from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..api.generic import DriverAPI
from ..type_helpers import Get, RequestSet, ResponseSet
from ..utils import find_elems

if TYPE_CHECKING:
    from ..controller import Controller


@dataclass
class DeviceState:
    sensors: dict[str, str]
    switches: dict[str, str]


class Device:
    idx: str
    sensor_apis: dict[str, DriverAPI]
    switch_apis: dict[str, DriverAPI]

    _url: str
    _controller: "Controller"

    def __init__(self, controller: "Controller", idx: str, apis: dict[str, DriverAPI]):
        self._controller = controller
        self.idx = idx
        api_ids = find_elems(apis, rf"^{idx}$")

        self.sensor_apis = {}
        self.switch_apis = {}

        for x in api_ids:
            d = apis.get(x)
            if d:
                if d.readonly:
                    self.sensor_apis[d.name] = d
                else:
                    self.switch_apis[d.name] = d

        if self.sensor_apis:
            self._url = list(self.sensor_apis.values())[0].structure_url
        elif self.switch_apis:
            self._url = list(self.switch_apis.values())[0].structure_url

    @property
    def get_request(self) -> RequestSet:
        if self._url:
            get_request = Get(path=self._url, expected_length=len(self.sensor_apis) + len(self.switch_apis))
            return RequestSet(getters=[get_request])
        else:
            return RequestSet()  # fail silently

    def parse_state(self, response_set: ResponseSet):
        sensors = {n: a.parse(response_set) for n, a in self.sensor_apis.items()}
        switches = {n: a.parse(response_set) for n, a in self.switch_apis.items()}
        return DeviceState(sensors=sensors, switches=switches)

    def do_update(self):
        resp = self._controller.api_call(self.get_request)
        return self.parse_state(resp)
