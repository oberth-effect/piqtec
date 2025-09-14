from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from typing import TYPE_CHECKING

from ..api.generic import API
from ..type_helpers import Get, RequestSet, ResponseSet
from ..utils import merge_requests

if TYPE_CHECKING:
    from ..controller import Controller


class StatefulUnit[S: dataclass](ABC):
    idx: str
    apis: dict[str, API]

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

    def __init__(self, controller: "Controller", idx: str, apis: dict[str, API], get_url: str | None = None):
        self._controller = controller
        self.idx = idx
        self.apis = {}
        for var in self._var_map():
            d = apis.get(f"{self.idx}.{var.value}")
            if d:
                self.apis[var.name] = d

        if not get_url:
            # Assume common structure url
            self._url = list(self.apis.values())[0].structure_url

    @property
    def get_request(self) -> RequestSet:
        if self._url:
            get_request = Get(path=self._url, expected_length=len(self.apis))
            return RequestSet(getters=[get_request])
        else:
            r = merge_requests([a.get_request() for a in self.apis.values()])
            return r

    def parse_state(self, response_set: ResponseSet) -> S:
        c = self._state_cls()
        return c(**{f.name: self.apis[f.name].parse(response_set) for f in fields(c)})

    def do_update(self) -> S:
        resp = self._controller.api_call(self.get_request)
        return self.parse_state(resp)
