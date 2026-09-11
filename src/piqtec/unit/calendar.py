"""Heating calendars (weekly temperature profiles)."""

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..api.generic import CalendarAPI
from ..exceptions import IQtecResponseError
from ..type_helpers import RequestSet, ResponseSet

if TYPE_CHECKING:
    from ..controller import Controller


@dataclass
class CalendarState:
    name: str | None = None
    temperatures: list[float] = field(default_factory=list)
    days: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


class Calendar:
    idx: str
    api: CalendarAPI

    _controller: "Controller"

    def __init__(self, controller: "Controller", idx: str, apis: dict[str, CalendarAPI]) -> None:
        self._controller = controller
        self.idx = idx
        self.api = apis[idx]

    @property
    def get_request(self) -> RequestSet:
        return self.api.get_request()

    def set_request(self, value: str) -> RequestSet:
        return self.api.set_request(value)

    def parse_state(self, response_set: ResponseSet) -> CalendarState:
        raw = self.api.parse(response_set)
        if raw is None:
            return CalendarState()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as err:
            raise IQtecResponseError(f"Malformed calendar payload for {self.idx}: {err}") from err
        return CalendarState(
            name=data.get("Name"),
            temperatures=data.get("Temperatures", []),
            days=data.get("Days", []),
            raw=data,
        )

    def update(self) -> CalendarState:
        return self.parse_state(self._controller.api_call(self.get_request))
