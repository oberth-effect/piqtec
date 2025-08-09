from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

from ..constants import CALENDAR_PREFIX, DEVICE_PREFIX, DRIVER_PREFIX
from ..type_helpers import Get, RequestSet, ResponseSet, Set

if TYPE_CHECKING:
    from ..system import Controller


class API(ABC):
    @abstractmethod
    def update_request(self) -> RequestSet:
        raise NotImplementedError()

    @abstractmethod
    def parse(self, responses: ResponseSet):
        raise NotImplementedError()


@dataclass
class _APIBase(API):
    name: str
    access: str
    param: bool

    @property
    def _url(self) -> str:
        raise NotImplementedError()

    def update_request(self) -> RequestSet:
        get_request = Get(path=self._url)
        return RequestSet(getters=[get_request])

    def set_request(self, value: str) -> RequestSet:
        set_request = Set(path=self._url, value=str(value))
        return RequestSet(setters=[set_request])

    def parse(self, responses: ResponseSet) -> str | None:
        r = responses.get(self._url)
        return r.value if r else None


@dataclass
class _APIBaseExt(_APIBase):
    typ: str
    structure_id: int
    offset: int
    mask: int | None


@dataclass
class PageAPI(_APIBase):
    structure_id: int


@dataclass
class ScenarioAPI(_APIBaseExt):
    pass


@dataclass
class DriverAPI(_APIBaseExt):
    history: str | None

    @property
    def _url(self) -> str:
        if self.mask:
            return f"{DRIVER_PREFIX}/{self.structure_id}/{self.offset}/{self.mask}"
        else:
            return f"{DRIVER_PREFIX}/{self.structure_id}/{self.offset}"


@dataclass
class CalendarAPI(_APIBaseExt):
    calendar_type: str | None

    @property
    def _url(self) -> str:
        if self.mask:
            return f"{CALENDAR_PREFIX}/{self.structure_id}/{self.offset}/{self.mask}"
        else:
            return f"{CALENDAR_PREFIX}/{self.structure_id}/{self.offset}"


@dataclass
class DeviceAPI(_APIBase):
    typ: str
    device_id: int
    device_structure_id: int
    offset: int
    mask: int | None

    @property
    def _url(self) -> str:
        if self.mask:
            return f"{DEVICE_PREFIX}/{self.device_structure_id}/{self.offset}/{self.mask}"
        else:
            return f"{DEVICE_PREFIX}/{self.device_structure_id}/{self.offset}"


class StatefulAPI[S: dataclass](API, ABC):
    idx: str
    drivers: dict[str, DriverAPI]

    _url: str
    _controller: "Controller"

    @classmethod
    @abstractmethod
    def _var_map(cls):
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def _state_cls(cls) -> S:
        raise NotImplementedError()

    def __init__(self, controller: "Controller", idx: str, drivers: dict[str, DriverAPI]):
        self._controller = controller
        self.idx = idx
        self.drivers = {}
        for var in self._var_map():
            d = drivers.get(f"{self.idx}.{var.value}")
            if d:
                self.drivers[var.name] = d

        self._url = f"{DRIVER_PREFIX}/{self.drivers['name'].structure_id}"

    def update_request(self) -> RequestSet:
        get_request = Get(path=self._url, expected_length=len(self.drivers))
        return RequestSet(getters=[get_request])

    def parse(self, response_set: ResponseSet) -> S:
        c = self._state_cls()
        return c(**{f.name: self.drivers[f.name].parse(response_set) for f in fields(c)})

    def get_update(self) -> S:
        resp = self._controller.api_call(self.update_request())
        return self.parse(resp)
