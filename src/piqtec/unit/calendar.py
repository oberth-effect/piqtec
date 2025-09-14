import json
from typing import TYPE_CHECKING

from ..api.generic import CalendarAPI
from ..type_helpers import ResponseSet

if TYPE_CHECKING:
    from ..controller import Controller


class Calendar:
    idx: str
    api: CalendarAPI

    _url: str
    _controller: "Controller"

    def __init__(self, controller: "Controller", idx: str, apis: dict[str, CalendarAPI]):
        self._controller = controller
        self.idx = idx
        self.api = apis[self.idx]

        self._url = self.api._url

    @property
    def get_request(self):
        return self.api.get_request()

    def set_request(self, value: str):
        return self.api.set_request(value)

    def parse_state(self, response_set: ResponseSet):
        raw = self.api.parse(response_set)
        return json.loads(raw)

    def do_update(self):
        resp = self._controller.api_call(self.get_request)
        return self.parse_state(resp)
