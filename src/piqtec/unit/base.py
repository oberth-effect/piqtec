"""Shared behaviour of the units built on top of the raw variable APIs."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, fields
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from ..api.generic import API
from ..type_helpers import Get, RequestSet, ResponseSet
from ..utils import merge_requests

if TYPE_CHECKING:
    from ..controller import Controller


class StatefulUnit[S: dataclass](ABC):
    """A named group of variables that maps onto one state dataclass.

    Only the variables the controller actually exposes are bound, so a unit stays
    usable on installations that do not implement the full variable set; missing
    fields read back as ``None``.
    """

    idx: str
    apis: dict[str, API]

    _address: str | None
    _controller: "Controller"

    @classmethod
    @abstractmethod
    def _var_map(cls) -> type[StrEnum]:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def _state_cls(cls) -> type[S]:
        raise NotImplementedError

    def __init__(self, controller: "Controller", idx: str, apis: dict[str, API]) -> None:
        self._controller = controller
        self.idx = idx
        self.apis = {}
        for var in self._var_map():
            api = apis.get(f"{idx}.{var.value}")
            if api:
                self.apis[var.name] = api

        addresses = {api.structure_address for api in self.apis.values()}
        # A unit maps onto a single structure, which can be read in one go; if it
        # ever spans several, fall back to reading each variable individually.
        self._address = addresses.pop() if len(addresses) == 1 else None

    @property
    def available(self) -> bool:
        return bool(self.apis)

    @property
    def get_request(self) -> RequestSet:
        if self._address:
            return RequestSet(getters=[Get(path=self._address)])
        return merge_requests(api.get_request() for api in self.apis.values())

    def parse_state(self, response_set: ResponseSet) -> S:
        state_cls = self._state_cls()
        values = {}
        for field in fields(state_cls):
            api = self.apis.get(field.name)
            values[field.name] = api.parse(response_set) if api else None
        return state_cls(**values)

    def update(self) -> S:
        return self.parse_state(self._controller.api_call(self.get_request))

    def set_value(self, field_name: str, value: Any) -> None:
        """Write a single variable, addressed by its state field name."""
        api = self.apis.get(field_name)
        if api is None:
            raise KeyError(f"{self.idx} has no variable {field_name!r}")
        self._controller.api_call(api.set_request(value))
