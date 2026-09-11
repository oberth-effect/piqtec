"""Small value types describing requests and responses."""

from dataclasses import dataclass, field
from typing import Self

type Request = Get | Set

type ResponseSet = dict[str, Response]


@dataclass(frozen=True)
class Response:
    path: str
    value: str


@dataclass(frozen=True)
class Get:
    path: str
    # Overrides the controller's own estimate when the address is not known
    # from data.xml (raw reads).
    expected_bytes: int | None = None


@dataclass(frozen=True)
class Set:
    path: str
    value: str


@dataclass
class RequestSet:
    getters: list[Get] = field(default_factory=list)
    setters: list[Set] = field(default_factory=list)

    def __add__(self, other: Self) -> "RequestSet":
        return RequestSet(
            getters=self.getters + other.getters,
            setters=self.setters + other.setters,
        )

    def __radd__(self, other: "RequestSet | int") -> "RequestSet":
        # Supports sum() over request sets.
        if other == 0:
            return self
        return other.__add__(self)

    def __bool__(self) -> bool:
        return bool(self.getters or self.setters)
