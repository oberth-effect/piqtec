from dataclasses import dataclass

type Request = Get | Set

type ResponseSet = dict[str, Response]


@dataclass
class Response:
    path: str
    value: str


@dataclass
class Get:
    path: str
    expected_length: int | None = None


@dataclass
class Set:
    path: str
    value: str


@dataclass
class RequestSet:
    getters: list[Get]
    setters: list[Set]
