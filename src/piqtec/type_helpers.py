from dataclasses import dataclass, field
from typing import Self

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
    getters: list[Get] = field(default_factory=list)
    setters: list[Set] = field(default_factory=list)

    def __add__(self, other: Self) -> Self:
        return RequestSet(getters=self.getters + other.getters, setters=self.setters + other.setters)
