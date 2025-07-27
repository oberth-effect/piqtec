from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..constants import CALENDAR_PREFIX, DEVICE_PREFIX, DRIVER_PREFIX
from ..type_helpers import Get, ResponseSet, Set


class API(ABC):
    @abstractmethod
    def create_get_request(self) -> Get:
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

    def create_get_request(self) -> Get:
        return Get(path=self._url)

    def create_set_request(self, value: str) -> Set:
        return Set(path=self._url, value=str(value))

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
