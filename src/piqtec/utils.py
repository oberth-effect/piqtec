"""Helpers for building requests and interpreting data.xml."""

import logging
import re
from collections.abc import Iterable

from .api.generic import API, CalendarAPI, DeviceAPI, DriverAPI, PageAPI, ScenarioAPI
from .exceptions import RequestTooLongError
from .type_helpers import RequestSet

_LOGGER = logging.getLogger(__name__)


def pack_chunks(
    items: Iterable[tuple[str, int]],
    max_request_bytes: int,
    max_response_bytes: int,
    overhead: int = 0,
) -> list[str]:
    """Group request fragments into as few ``;``-joined chunks as possible.

    Each item is a ``(fragment, expected_response_bytes)`` pair. Both the request
    line and the reply have hard limits in the firmware, and exceeding either
    fails silently, so every chunk is kept under both.
    """
    chunks: list[str] = []
    current: list[str] = []
    current_request = overhead
    current_response = 0

    for fragment, response_bytes in items:
        fragment_request = len(fragment) + 1  # the joining ";"
        if fragment_request + overhead > max_request_bytes or response_bytes > max_response_bytes:
            raise RequestTooLongError(
                f"{fragment!r} cannot be requested on its own "
                f"({fragment_request + overhead}B request, {response_bytes}B response)"
            )
        too_long = current_request + fragment_request > max_request_bytes
        too_big = current_response + response_bytes > max_response_bytes
        if current and (too_long or too_big):
            chunks.append(";".join(current))
            current = []
            current_request = overhead
            current_response = 0
        current.append(fragment)
        current_request += fragment_request
        current_response += response_bytes

    if current:
        chunks.append(";".join(current))
    return chunks


def match_api(obj: dict[str, str]) -> API | None:
    """Build the descriptor for one data.xml entry.

    Discovery is best effort: an entry of a category this package does not
    model, or one with a malformed attribute, is logged and skipped by returning
    ``None`` rather than making the whole controller unusable.
    """
    try:
        return _match_api(obj)
    except ValueError as err:
        _LOGGER.warning("Skipping malformed data.xml entry %r: %s", obj.get("name"), err)
        return None


def _match_api(obj: dict[str, str]) -> API | None:
    mask = obj.get("mask")
    common = {
        "name": str(obj.get("name")),
        "access": str(obj.get("access")),
        "param": bool(int(obj.get("param", 0))),
        "typ": str(obj.get("type", "")),
    }
    addressed = {
        "structure_id": int(obj.get("structure_id", 0)),
        "offset": int(obj.get("offset", 0)),
        "mask": int(mask) if mask else None,
    }
    match obj:
        case {"category": "driver"}:
            return DriverAPI(**common, **addressed, history=obj.get("history"))
        case {"category": "calendar"}:
            return CalendarAPI(**common, **addressed, calendar_type=obj.get("calendarType"))
        case {"category": "sbScenario"}:
            return ScenarioAPI(**common, **addressed)
        case {"category": "device"}:
            return DeviceAPI(
                **common,
                device_id=int(obj.get("device_id", 0)),
                device_structure_id=int(obj.get("device_structure_id", 0)),
                offset=int(obj.get("offset", 0)),
                mask=int(mask) if mask else None,
            )
        case {"category": "page"}:
            return PageAPI(**common, structure_id=int(obj.get("structure_id", 0)))
        case _:
            _LOGGER.debug("Skipping data.xml entry %r of unsupported category %r", obj.get("name"), obj.get("category"))
            return None


def merge_requests(request_sets: Iterable[RequestSet]) -> RequestSet:
    merged = RequestSet()
    for request_set in request_sets:
        merged = merged + request_set
    return merged


def unit_prefix(name: str) -> str:
    """The unit part of a ``UNIT.Variable`` name."""
    return name.split(".")[0]


def find_ids(apis: Iterable[str], regex: str) -> list[str]:
    return sorted({prefix for name in apis if re.match(regex, (prefix := unit_prefix(name)))})


def find_names(apis: Iterable[str], idx: str) -> list[str]:
    """Names of every variable belonging to unit ``idx`` (exact prefix match)."""
    return sorted(name for name in apis if unit_prefix(name) == idx)
