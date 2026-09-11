"""Generic devices discovered from data.xml on a best-effort basis."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..api.generic import DriverAPI
from ..type_helpers import Get, RequestSet, ResponseSet
from ..utils import find_names, merge_requests

if TYPE_CHECKING:
    from ..controller import Controller


@dataclass
class DeviceState:
    sensors: dict[str, Any] = field(default_factory=dict)
    switches: dict[str, Any] = field(default_factory=dict)


class Device:
    """Every variable sharing a name prefix, split by writability."""

    idx: str
    sensor_apis: dict[str, DriverAPI]
    switch_apis: dict[str, DriverAPI]

    _address: str | None
    _controller: "Controller"

    def __init__(self, controller: "Controller", idx: str, apis: dict[str, DriverAPI]) -> None:
        self._controller = controller
        self.idx = idx

        self.sensor_apis = {}
        self.switch_apis = {}
        for name in find_names(apis, idx):
            api = apis[name]
            target = self.sensor_apis if api.readonly else self.switch_apis
            target[name] = api

        addresses = {api.structure_address for api in self.all_apis.values()}
        self._address = addresses.pop() if len(addresses) == 1 else None

    @property
    def all_apis(self) -> dict[str, DriverAPI]:
        return {**self.sensor_apis, **self.switch_apis}

    @property
    def available(self) -> bool:
        return bool(self.sensor_apis or self.switch_apis)

    @property
    def get_request(self) -> RequestSet:
        if self._address:
            return RequestSet(getters=[Get(path=self._address)])
        return merge_requests(api.get_request() for api in self.all_apis.values())

    def parse_state(self, response_set: ResponseSet) -> DeviceState:
        return DeviceState(
            sensors={name: api.parse(response_set) for name, api in self.sensor_apis.items()},
            switches={name: api.parse(response_set) for name, api in self.switch_apis.items()},
        )

    def update(self) -> DeviceState:
        return self.parse_state(self._controller.api_call(self.get_request))

    def set_value(self, name: str, value: Any) -> None:
        api = self.switch_apis.get(name)
        if api is None:
            raise KeyError(f"{self.idx} has no writable variable {name!r}")
        self._controller.api_call(api.set_request(value))
