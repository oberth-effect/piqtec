from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..constants import CALENDAR_PREFIX, DEVICE_PREFIX, DRIVER_PREFIX
from ..type_helpers import Get, RequestSet, ResponseSet, Set

if TYPE_CHECKING:
    pass


@dataclass
class API(ABC):
    name: str
    access: str
    param: bool

    @property
    @abstractmethod
    def _url(self) -> str:
        raise NotImplementedError()

    @property
    @abstractmethod
    def structure_url(self) -> str:
        raise NotImplementedError()

    @property
    def readonly(self) -> bool:
        return "U" not in self.access

    def get_request(self) -> RequestSet:
        get_request = Get(path=self._url)
        return RequestSet(getters=[get_request])

    def set_request(self, value: str) -> RequestSet:
        if self.readonly:
            raise Exception(f"Cannot set read-only variable {self.name}")
        set_request = Set(path=self._url, value=str(value))
        return RequestSet(setters=[set_request])

    def parse(self, responses: ResponseSet) -> str | None:
        r = responses.get(self._url)
        return r.value if r else None


@dataclass
class _APIBaseExt(API):
    typ: str
    structure_id: int
    offset: int
    mask: int | None


@dataclass
class PageAPI(API):
    structure_id: int

    @property
    def _url(self) -> str:
        raise NotImplementedError()

    @property
    def structure_url(self) -> str:
        raise NotImplementedError()


@dataclass
class ScenarioAPI(_APIBaseExt):
    @property
    def _url(self) -> str:
        raise NotImplementedError()

    @property
    def structure_url(self) -> str:
        raise NotImplementedError()


@dataclass
class DriverAPI(_APIBaseExt):
    history: str | None

    @property
    def _url(self) -> str:
        if self.mask:
            return f"{DRIVER_PREFIX}/{self.structure_id}/{self.offset}/{self.mask}"
        else:
            return f"{DRIVER_PREFIX}/{self.structure_id}/{self.offset}"

    @property
    def structure_url(self):
        return f"{DRIVER_PREFIX}/{self.structure_id}/"


@dataclass
class CalendarAPI(_APIBaseExt):
    calendar_type: str | None

    @property
    def _url(self) -> str:
        if self.mask:
            return f"{CALENDAR_PREFIX}/{self.structure_id}/{self.offset}/{self.mask}"
        else:
            return f"{CALENDAR_PREFIX}/{self.structure_id}/{self.offset}"

    @property
    def structure_url(self):
        return f"{CALENDAR_PREFIX}/{self.structure_id}/"


@dataclass
class DeviceAPI(API):
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

    @property
    def structure_url(self):
        return f"{DEVICE_PREFIX}/{self.device_structure_id}/"
