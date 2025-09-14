import contextlib
import re
from dataclasses import dataclass, fields

from .api.generic import API, CalendarAPI, DeviceAPI, DriverAPI, PageAPI, ScenarioAPI
from .constants import MAX_RESPONSE_LENGTH
from .type_helpers import Get, RequestSet


@dataclass
class CoerceTypesMixin:
    def __post_init__(self):
        # Try to coerce types
        for field in fields(self):
            if callable(field.type):
                with contextlib.suppress(ValueError):
                    if field.type is bool:
                        setattr(self, field.name, field.type(int(getattr(self, field.name))))
                    else:
                        setattr(self, field.name, field.type(getattr(self, field.name)))


def split_getters_to_chunks(getters: list[Get]) -> list[list[Get]]:
    chunks = []
    current_chunk = []
    current_chunk_length = 0
    for getter in getters:
        expected_length = getter.expected_length if getter.expected_length else 1
        if expected_length > MAX_RESPONSE_LENGTH:
            raise ValueError(
                f"Expected response for {getter.path} is too long ({getter.expected_length}>{MAX_RESPONSE_LENGTH=})"
            )
        if current_chunk_length + expected_length > MAX_RESPONSE_LENGTH:
            path_string = ";".join(g.path for g in current_chunk)
            chunks.append(path_string)
            current_chunk = [getter]
            current_chunk_length = expected_length
        else:
            current_chunk.append(getter)
            current_chunk_length += expected_length
    if current_chunk:
        path_string = ";".join(g.path for g in current_chunk)
        chunks.append(path_string)

    return chunks


def match_api(obj: dict[str, str]) -> API:
    match obj:
        case {"category": "driver", **rest}:
            m = rest.get("mask", None)
            return DriverAPI(
                name=str(rest.get("name")),
                access=str(rest.get("access")),
                param=bool(int(rest.get("param"))),
                typ=str(rest.get("type")),
                structure_id=int(rest.get("structure_id")),
                offset=int(rest.get("offset")),
                mask=int(m) if m else None,
                history=rest.get("history", None),
            )
        case {"category": "calendar", **rest}:
            m = rest.get("mask", None)
            return CalendarAPI(
                name=str(rest.get("name")),
                access=str(rest.get("access")),
                param=bool(int(rest.get("param"))),
                typ=str(rest.get("type")),
                structure_id=int(rest.get("structure_id")),
                offset=int(rest.get("offset")),
                mask=int(m) if m else None,
                calendar_type=rest.get("calendarType", None),
            )
        case {"category": "device", **rest}:
            m = rest.get("mask", None)
            return DeviceAPI(
                name=str(rest.get("name")),
                access=str(rest.get("access")),
                param=bool(int(rest.get("param"))),
                typ=str(rest.get("type")),
                device_id=int(rest.get("device_id")),
                device_structure_id=int(rest.get("device_structure_id")),
                offset=int(rest.get("offset")),
                mask=int(m) if m else None,
            )
        case {"category": "sbScenario", **rest}:
            m = rest.get("mask", None)
            return ScenarioAPI(
                name=str(rest.get("name")),
                access=str(rest.get("access")),
                param=bool(int(rest.get("param"))),
                typ=str(rest.get("type")),
                structure_id=int(rest.get("structure_id")),
                offset=int(rest.get("offset")),
                mask=int(m) if m else None,
            )
        case {"category": "page", **rest}:
            return PageAPI(
                name=str(rest.get("name")),
                access=str(rest.get("access")),
                param=bool(int(rest.get("param"))),
                structure_id=int(rest.get("structure_id")),
            )
        case _:
            raise NotImplementedError(f"Cannot parse driver {obj}")


def merge_requests(request_sets: list[RequestSet]) -> RequestSet:
    getters = []
    for rs in request_sets:
        getters.extend(rs.getters)
    return RequestSet(getters=getters)


def find_ids(apis: dict[str, API], regex: str) -> list[str]:
    ids = set()
    for n in apis:
        prefix = n.split(".")[0]
        if re.match(regex, prefix):
            ids.add(prefix)
    return sorted(ids)


def find_elems(apis: dict[str, API], regex: str) -> list[str]:
    elems = set()
    for n in apis:
        prefix = n.split(".")[0]
        if re.match(regex, prefix):
            elems.add(n)
    return sorted(elems)
