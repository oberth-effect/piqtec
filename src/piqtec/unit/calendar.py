"""Heating calendars (weekly schedules).

A calendar is a fixed grid: 8 days of 8 edges. Day 0 is Monday, days 1-6 run to
Sunday and day 7 is the "day 8" the controller selects through a separate input.
Each edge is ``[time, level]`` with time counted in 5 minute steps from midnight,
so a day spans 0..288; the first edge is pinned to 0 and the last to 288, and
times strictly increase in between.

The last edge only terminates the day, and an edge repeating the level before it
changes nothing, so the grid stores between 1 and 7 real transitions and parks
the spares. Work through :attr:`CalendarDay.transitions` and
:meth:`CalendarDay.set_transitions`, which hide that packing.
"""

import json
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Self

from ..api.generic import CalendarAPI
from ..constants import (
    CALENDAR_DAY_END,
    CALENDAR_DAYS,
    CALENDAR_EDGES,
    CALENDAR_TEMPERATURES,
    CALENDAR_TIME_STEP_MINUTES,
    CalendarLevel,
    CalendarType,
)
from ..exceptions import InvalidValueError, IQtecResponseError
from ..type_helpers import RequestSet, ResponseSet

if TYPE_CHECKING:
    from ..controller import Controller

MAX_NAME_LENGTH = 16

#: The last edge only terminates the day, so 7 of the 8 can carry a transition.
MAX_TRANSITIONS = CALENDAR_EDGES - 1

_LEVELS = tuple(CalendarLevel)


def _whole(value: Any, what: str) -> int:
    """``value`` as an int, refusing to truncate or guess."""
    try:
        number = int(value)
    except (TypeError, ValueError) as err:
        raise InvalidValueError(f"{what} must be a whole number, got {value!r}") from err
    if number != value:
        raise InvalidValueError(f"{what} must be a whole number, got {value!r}")
    return number


def _level(value: Any) -> int:
    level = _whole(value, "A level")
    if level not in _LEVELS:
        raise InvalidValueError(f"Level {level} is not 0, 1 or 2")
    return level


@dataclass
class CalendarEdge:
    """One point of a day's schedule."""

    time: int
    level: int

    @property
    def minutes(self) -> int:
        """Minutes from midnight."""
        return self.time * CALENDAR_TIME_STEP_MINUTES

    @classmethod
    def from_minutes(cls, minutes: int, level: int) -> Self:
        return cls(time=round(minutes / CALENDAR_TIME_STEP_MINUTES), level=int(level))

    def as_json(self) -> list[int]:
        return [self.time, self.level]


@dataclass
class CalendarDay:
    """One day of the week, as 8 edges."""

    as_monday: bool = False
    edges: list[CalendarEdge] = field(default_factory=list)

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> Self:
        return cls(
            as_monday=bool(data.get("AsMonday", False)),
            edges=[CalendarEdge(int(e[0]), int(e[1])) for e in data.get("Edges", [])],
        )

    def as_json(self) -> dict[str, Any]:
        return {"AsMonday": self.as_monday, "Edges": [e.as_json() for e in self.edges]}

    @property
    def transitions(self) -> list[CalendarEdge]:
        """The schedule as a user sees it: the moments the level changes.

        The last edge only terminates the day and never shows up here, so a day
        holds between 1 and 7 transitions, the first of which starts at midnight.
        """
        result: list[CalendarEdge] = []
        previous = None
        for edge in self.edges[:-1]:
            if previous is None or edge.level != previous:
                result.append(CalendarEdge(edge.time, edge.level))
            previous = edge.level
        return result

    def set_transitions(self, transitions: list[CalendarEdge]) -> None:
        """Replace the day, packing the transitions back into the 8 edge grid.

        Unused edges are parked in the widest gaps repeating the level before
        them, which is how the controller itself stores a short schedule.
        """
        if not transitions:
            raise InvalidValueError("A day needs at least one transition")
        if len(transitions) > MAX_TRANSITIONS:
            raise InvalidValueError(f"A day holds at most {MAX_TRANSITIONS} transitions")

        packed = [CalendarEdge(_whole(t.time, "A transition time"), _level(t.level)) for t in transitions]
        packed.sort(key=lambda e: e.time)
        # Checked before repeats are dropped, so the verdict does not depend on
        # which of two same-time transitions happened to come first.
        if len({e.time for e in packed}) != len(packed):
            raise InvalidValueError("Two transitions cannot share a time")
        # A repeated level is not a change, so it is not a transition.
        packed = [e for i, e in enumerate(packed) if i == 0 or e.level != packed[i - 1].level]
        if packed[0].time != 0:
            raise InvalidValueError("The first transition of a day must start at midnight")
        if packed[-1].time >= CALENDAR_DAY_END:
            raise InvalidValueError(f"A transition must fall before {CALENDAR_DAY_END}")

        # Park the leftover edges, then terminate the day at midnight.
        while len(packed) < CALENDAR_EDGES - 1:
            packed.append(self._park(packed))
            packed.sort(key=lambda e: e.time)
        packed.append(CalendarEdge(CALENDAR_DAY_END, packed[-1].level))
        self.edges = packed

    @staticmethod
    def _park(packed: list[CalendarEdge]) -> CalendarEdge:
        """A spare edge in the widest gap, repeating the level before it."""
        bounds = [*(e.time for e in packed), CALENDAR_DAY_END]
        widest = max(range(len(bounds) - 1), key=lambda i: bounds[i + 1] - bounds[i])
        time = (bounds[widest] + bounds[widest + 1]) // 2
        if time <= bounds[widest] or time >= bounds[widest + 1]:
            raise InvalidValueError("No room left to park a spare edge")
        return CalendarEdge(time, packed[widest].level)

    def level_at(self, time: int) -> int | None:
        """Level in force at ``time`` (5 minute units)."""
        current = None
        for edge in self.edges:
            if edge.time <= time:
                current = edge.level
            else:
                break
        return current

    def add_transition(self, time: int, level: int) -> None:
        """Add a change of level at ``time``."""
        time = _whole(time, "A transition time")
        if not 0 < time < CALENDAR_DAY_END:
            raise InvalidValueError(f"A transition must fall inside the day, got {time}")
        transitions = self.transitions
        if any(t.time == time for t in transitions):
            raise InvalidValueError(f"There is already a transition at {time}")
        if len(transitions) >= MAX_TRANSITIONS:
            raise InvalidValueError(f"A day holds at most {MAX_TRANSITIONS} transitions")
        self.set_transitions([*transitions, CalendarEdge(time, int(level))])

    def remove_transition(self, index: int) -> None:
        """Drop one transition, so the preceding level runs on through it."""
        transitions = self.transitions
        if index == 0:
            raise InvalidValueError("The transition at midnight cannot be removed")
        if not 0 <= index < len(transitions):
            raise InvalidValueError(f"No transition at index {index}")
        del transitions[index]
        self.set_transitions(transitions)

    def move_transition(self, index: int, time: int) -> None:
        """Move a transition, keeping it between its neighbours."""
        transitions = self.transitions
        if index == 0:
            raise InvalidValueError("The transition at midnight cannot be moved")
        if not 0 <= index < len(transitions):
            raise InvalidValueError(f"No transition at index {index}")
        low = transitions[index - 1].time + 1
        high = transitions[index + 1].time - 1 if index + 1 < len(transitions) else CALENDAR_DAY_END - 1
        if not low <= time <= high:
            raise InvalidValueError(f"Transition {index} must stay between {low} and {high}, got {time}")
        transitions[index].time = _whole(time, "A transition time")
        self.set_transitions(transitions)

    def set_transition_level(self, index: int, level: int) -> None:
        """Change the level a transition switches to."""
        transitions = self.transitions
        if not 0 <= index < len(transitions):
            raise InvalidValueError(f"No transition at index {index}")
        transitions[index].level = _level(level)
        self.set_transitions(transitions)


@dataclass(frozen=True)
class CalendarPeriod:
    """A stretch of wall-clock time during which one level is in force."""

    start: datetime
    end: datetime
    level: int


def _exists(local: datetime) -> bool:
    """Whether an aware wall-clock time actually occurs in its zone."""
    round_trip = local.astimezone(UTC).astimezone(local.tzinfo)
    return round_trip.replace(tzinfo=None) == local.replace(tzinfo=None)


def _gap_end(local: datetime) -> datetime:
    """The instant a clock jumping over ``local`` lands on, in local time.

    ``local`` is a wall-clock time the zone skips. With ``fold=1`` it carries the
    offset from after the jump and so names an instant before it; with the
    default ``fold=0`` an instant after it. The jump itself is found between the
    two, to the minute.
    """
    tzinfo = local.tzinfo
    before = local.replace(fold=1).astimezone(UTC)
    after = local.astimezone(UTC)
    minute = timedelta(minutes=1)
    while after - before > minute:
        middle = before + minute * ((after - before) // minute // 2)
        if middle.astimezone(tzinfo).utcoffset() == after.astimezone(tzinfo).utcoffset():
            after = middle
        else:
            before = middle
    return after.astimezone(tzinfo)


@dataclass
class CalendarState:
    """Everything the controller stores about one calendar."""

    name: str | None = None
    temperatures: list[float] = field(default_factory=list)
    days: list[CalendarDay] = field(default_factory=list)
    color: int | None = None
    calendar_type: CalendarType = CalendarType.TEMPERATURE

    @classmethod
    def from_json(cls, data: dict[str, Any], calendar_type: CalendarType = CalendarType.TEMPERATURE) -> Self:
        return cls(
            name=data.get("Name"),
            temperatures=[float(t) for t in data.get("Temperatures", [])],
            days=[CalendarDay.from_json(d) for d in data.get("Days", [])],
            calendar_type=calendar_type,
        )

    def as_json(self) -> dict[str, Any]:
        """The payload the controller accepts. CRC is read-only and omitted."""
        return {
            "Name": self.name or "",
            "Temperatures": [float(t) for t in self.temperatures],
            "Days": [day.as_json() for day in self.days],
        }

    @property
    def heating_temperatures(self) -> list[float]:
        """Setpoints for Nobody, Night and Day while heating."""
        return self.temperatures[:3]

    @property
    def cooling_temperatures(self) -> list[float]:
        """Setpoints for Nobody, Night and Day while cooling."""
        return self.temperatures[3:6]

    def temperature_for(self, level: int | None, cooling: bool = False) -> float | None:
        """The setpoint for ``level``, or ``None`` when the level or setpoint is unknown."""
        if level is None:
            return None
        index = int(level) + (3 if cooling else 0)
        if 0 <= index < len(self.temperatures):
            return self.temperatures[index]
        return None

    def day_for_weekday(self, weekday: int) -> "CalendarDay | None":
        """The day applying to a weekday (0 Monday), resolving "follows Monday".

        Only days 0-6 are dated. Day 7 is the separately selectable "day 8",
        which the controller switches to through an input rather than a date.
        ``None`` when the calendar holds no such day, as one read back from a
        switched-off variable does.
        """
        if not 0 <= weekday < len(self.days):
            return None
        day = self.days[weekday]
        return self.days[0] if day.as_monday and weekday > 0 else day

    def _at(self, day: date, units: int, tzinfo: Any) -> datetime:
        """Wall-clock local time of a transition, so it survives DST changes.

        A time the clock skips on the spring-forward day is resolved to the
        moment the clock jumps, which is when a clock-driven controller reaches
        it; stamping it with the offset from before the jump would place it
        after transitions that follow it on the wall clock.
        """
        minutes = units * CALENDAR_TIME_STEP_MINUTES
        local = datetime(day.year, day.month, day.day, minutes // 60, minutes % 60, tzinfo=tzinfo)
        if tzinfo is None or _exists(local):
            return local
        return _gap_end(local)

    def periods(self, start: datetime, end: datetime) -> list[CalendarPeriod]:
        """Every level period overlapping ``[start, end)``.

        The weekly pattern is materialised across the window in the time zone of
        ``start``. A period that runs past midnight into a day that opens on the
        same level is merged, so the result is the schedule as experienced rather
        than one entry per stored transition. A calendar without all seven
        weekdays cannot be projected and yields nothing.
        """
        if len(self.days) < CALENDAR_DAYS - 1:
            return []
        tzinfo = start.tzinfo

        # A week either side, so a period reaching into the window is complete
        # even when the neighbouring days hold a single level all day. Only a
        # level in force for more than a week is cut short.
        first = start.date() - timedelta(days=7)
        last = end.date() + timedelta(days=7)

        marks: list[tuple[datetime, int]] = []
        for offset in range((last - first).days + 1):
            current = first + timedelta(days=offset)
            day = self.day_for_weekday(current.weekday())
            if day is None:
                continue
            for edge in day.transitions:
                marks.append((self._at(current, edge.time, tzinfo), edge.level))

        periods: list[list[Any]] = []
        for (began, level), (next_began, _) in zip(marks, marks[1:], strict=False):
            # Within a day a level never repeats, so this only merges at midnight.
            if periods and periods[-1][2] == level:
                periods[-1][1] = next_began
            else:
                periods.append([began, next_began, level])

        return [CalendarPeriod(p[0], p[1], p[2]) for p in periods if p[1] > start and p[0] < end]

    def validate(self) -> None:
        """Raise if the controller would reject this calendar."""
        if self.name is not None and len(self.name) > MAX_NAME_LENGTH:
            raise InvalidValueError(f"A calendar name is at most {MAX_NAME_LENGTH} characters")
        if len(self.temperatures) != CALENDAR_TEMPERATURES:
            raise InvalidValueError(f"Expected {CALENDAR_TEMPERATURES} temperatures, got {len(self.temperatures)}")
        for index, temperature in enumerate(self.temperatures):
            if isinstance(temperature, bool) or not isinstance(temperature, int | float):
                raise InvalidValueError(f"Temperature {index}: {temperature!r} is not a number")
        if len(self.days) != CALENDAR_DAYS:
            raise InvalidValueError(f"Expected {CALENDAR_DAYS} days, got {len(self.days)}")

        for index, day in enumerate(self.days):
            if len(day.edges) != CALENDAR_EDGES:
                raise InvalidValueError(f"Day {index}: expected {CALENDAR_EDGES} edges, got {len(day.edges)}")
            if day.edges[0].time != 0:
                raise InvalidValueError(f"Day {index}: first edge must start at midnight")
            if day.edges[-1].time != CALENDAR_DAY_END:
                raise InvalidValueError(f"Day {index}: last edge must end at {CALENDAR_DAY_END}")
            if day.edges[-1].level != day.edges[-2].level:
                raise InvalidValueError(f"Day {index}: the last edge only terminates the day and cannot change level")
            for slot, edge in enumerate(day.edges):
                if edge.level not in _LEVELS:
                    raise InvalidValueError(f"Day {index} edge {slot}: level {edge.level} is not 0, 1 or 2")
                if slot and edge.time <= day.edges[slot - 1].time:
                    raise InvalidValueError(f"Day {index} edge {slot}: times must strictly increase")


class Calendar:
    """A single calendar, addressed as ``2/<index>/0`` with its colour at ``/1``."""

    idx: str
    api: CalendarAPI
    color_api: CalendarAPI | None

    _controller: "Controller"

    def __init__(
        self,
        controller: "Controller",
        idx: str,
        apis: dict[str, CalendarAPI],
        color_api: CalendarAPI | None = None,
    ) -> None:
        self._controller = controller
        self.idx = idx
        self.api = apis[idx]
        self.color_api = color_api

    @property
    def index(self) -> int:
        """Number the rooms refer to, taken from the address."""
        return self.api.structure_id

    @property
    def calendar_type(self) -> CalendarType:
        try:
            return CalendarType(self.api.calendar_type)
        except ValueError:
            return CalendarType.TEMPERATURE

    @property
    def get_request(self) -> RequestSet:
        request = self.api.get_request()
        if self.color_api:
            request = request + self.color_api.get_request()
        return request

    def parse_state(self, response_set: ResponseSet) -> CalendarState:
        raw = self.api.parse(response_set)
        if raw is None:
            return CalendarState(calendar_type=self.calendar_type)
        try:
            data = json.loads(raw)
            state = CalendarState.from_json(data, self.calendar_type)
        # Invalid JSON is a ValueError; valid JSON of the wrong shape surfaces
        # as any of the others while it is picked apart.
        except (ValueError, TypeError, AttributeError, IndexError, KeyError) as err:
            raise IQtecResponseError(f"Malformed calendar payload for {self.idx}: {err}") from err
        if self.color_api:
            state.color = self.color_api.parse(response_set)
        return state

    def update(self) -> CalendarState:
        return self.parse_state(self._controller.api_call(self.get_request))

    def write(self, state: CalendarState) -> None:
        """Replace the whole calendar. The controller has no partial update."""
        state.validate()
        payload = json.dumps(state.as_json(), separators=(",", ":"), ensure_ascii=False)
        request = self.api.set_request(payload)
        if self.color_api and state.color is not None:
            request = request + self.color_api.set_request(int(state.color))
        self._controller.api_call(request)
