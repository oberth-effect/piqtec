"""Tests for the calendar model."""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from piqtec.constants import CALENDAR_DAY_END, CALENDAR_EDGES, CalendarLevel, CalendarType
from piqtec.exceptions import InvalidValueError
from piqtec.unit.calendar import CalendarDay, CalendarEdge, CalendarState

# A real payload read back from a controller.
SAMPLE = {
    "Name": "GeneralProfile",
    "Temperatures": [14.0, 17.0, 20.0, 27.0, 25.0, 22.0],
    "Days": [
        {"AsMonday": d > 0, "Edges": [[0, 1], [72, 2], [96, 2], [119, 1], [143, 1], [182, 2], [240, 1], [288, 1]]}
        for d in range(8)
    ],
    "CRC": 10916,
}


def sample() -> CalendarState:
    return CalendarState.from_json(json.loads(json.dumps(SAMPLE)))


class TestDecode:
    def test_reads_name_and_temperatures(self):
        state = sample()
        assert state.name == "GeneralProfile"
        assert state.heating_temperatures == [14.0, 17.0, 20.0]
        assert state.cooling_temperatures == [27.0, 25.0, 22.0]

    def test_reads_eight_days_of_eight_edges(self):
        state = sample()
        assert len(state.days) == 8
        assert all(len(day.edges) == 8 for day in state.days)

    def test_as_monday_is_preserved(self):
        state = sample()
        assert state.days[0].as_monday is False
        assert state.days[1].as_monday is True

    def test_temperature_for_level_and_season(self):
        state = sample()
        assert state.temperature_for(CalendarLevel.DAY) == 20.0
        assert state.temperature_for(CalendarLevel.DAY, cooling=True) == 22.0

    def test_edge_minutes(self):
        assert CalendarEdge(72, 2).minutes == 360
        assert CalendarEdge.from_minutes(360, 2).time == 72


class TestEncode:
    def test_round_trip_is_lossless(self):
        state = sample()
        assert state.as_json()["Days"] == SAMPLE["Days"]
        assert state.as_json()["Temperatures"] == SAMPLE["Temperatures"]

    def test_crc_is_not_sent_back(self):
        assert "CRC" not in sample().as_json()

    def test_payload_fits_the_request_line(self):
        from urllib.parse import quote

        from piqtec.constants import MAX_REQUEST_BYTES, VALUE_SAFE_CHARS

        payload = json.dumps(sample().as_json(), separators=(",", ":"), ensure_ascii=False)
        encoded = quote(payload, safe=VALUE_SAFE_CHARS)
        assert len("/control/?2/0/0=") + len(encoded) < MAX_REQUEST_BYTES


class TestTransitions:
    def day(self) -> CalendarDay:
        return CalendarDay(edges=[CalendarEdge(*e) for e in SAMPLE["Days"][0]["Edges"]])

    def test_repeated_levels_are_not_transitions(self):
        # [96,2] repeats [72,2] and [143,1] repeats [119,1]
        assert [e.time for e in self.day().transitions] == [0, 72, 119, 182, 240]

    def test_the_terminator_is_not_a_transition(self):
        assert self.day().transitions[-1].time == 240

    def test_level_at_reads_the_schedule(self):
        day = self.day()
        assert day.level_at(0) == 1
        assert day.level_at(80) == 2
        assert day.level_at(120) == 1
        assert day.level_at(CALENDAR_DAY_END) == 1

    def test_set_transitions_round_trips(self):
        day = self.day()
        before = [(e.time, e.level) for e in day.transitions]
        day.set_transitions(day.transitions)
        assert [(e.time, e.level) for e in day.transitions] == before

    def test_set_transitions_always_fills_the_grid(self):
        day = self.day()
        day.set_transitions([CalendarEdge(0, 1), CalendarEdge(100, 2)])
        assert len(day.edges) == CALENDAR_EDGES
        times = [e.time for e in day.edges]
        assert times == sorted(times)
        assert len(set(times)) == len(times), "parked edges must not collide"
        assert day.edges[-1].time == CALENDAR_DAY_END
        assert day.edges[-1].level == day.edges[-2].level

    def test_set_transitions_drops_repeats(self):
        day = self.day()
        day.set_transitions([CalendarEdge(0, 1), CalendarEdge(50, 1), CalendarEdge(100, 2)])
        assert [e.time for e in day.transitions] == [0, 100]

    def test_add_transition_adds_exactly_one(self):
        day = self.day()
        before = len(day.transitions)
        day.add_transition(250, CalendarLevel.NOBODY)
        assert len(day.edges) == CALENDAR_EDGES, "the grid stays at 8 edges"
        assert len(day.transitions) == before + 1
        assert day.level_at(255) == CalendarLevel.NOBODY

    def test_remove_transition_keeps_the_grid_full(self):
        day = self.day()
        day.remove_transition(3)  # the 15:10 switch to DAY
        assert len(day.edges) == CALENDAR_EDGES
        assert [e.time for e in day.transitions] == [0, 72, 119]

    def test_removing_a_transition_extends_the_previous_level(self):
        day = self.day()
        day.remove_transition(1)  # the 06:00 switch to DAY
        assert day.level_at(80) == 1

    def test_removing_a_transition_drops_the_switch_back(self):
        day = self.day()
        # Without the 06:00 switch to DAY there is nothing for 09:55 to switch
        # back from, so that transition goes too.
        day.remove_transition(1)
        assert [e.time for e in day.transitions] == [0, 182, 240]

    def test_move_transition(self):
        day = self.day()
        day.move_transition(1, 90)
        assert [e.time for e in day.transitions] == [0, 90, 119, 182, 240]

    def test_move_cannot_cross_a_neighbour(self):
        with pytest.raises(InvalidValueError):
            self.day().move_transition(1, 119)

    def test_set_transition_level(self):
        day = self.day()
        day.set_transition_level(1, CalendarLevel.NOBODY)
        assert day.level_at(80) == CalendarLevel.NOBODY

    def test_midnight_is_pinned(self):
        with pytest.raises(InvalidValueError):
            self.day().move_transition(0, 10)
        with pytest.raises(InvalidValueError):
            self.day().remove_transition(0)

    def test_add_rejects_a_duplicate_time(self):
        with pytest.raises(InvalidValueError):
            self.day().add_transition(72, CalendarLevel.NOBODY)

    def test_add_rejects_midnight_and_the_day_end(self):
        with pytest.raises(InvalidValueError):
            self.day().add_transition(0, CalendarLevel.NOBODY)
        with pytest.raises(InvalidValueError):
            self.day().add_transition(CALENDAR_DAY_END, CalendarLevel.NOBODY)

    def test_add_fails_past_seven_transitions(self):
        day = CalendarDay()
        day.set_transitions([CalendarEdge(t, i % 3) for i, t in enumerate((0, 40, 80, 120, 160, 200, 240))])
        assert len(day.transitions) == 7
        with pytest.raises(InvalidValueError, match="at most 7"):
            day.add_transition(260, CalendarLevel.DAY)


class TestValidate:
    def test_a_real_calendar_validates(self):
        sample().validate()

    def test_rejects_a_long_name(self):
        state = sample()
        state.name = "x" * 17
        with pytest.raises(InvalidValueError, match="16 characters"):
            state.validate()

    def test_rejects_wrong_temperature_count(self):
        state = sample()
        state.temperatures = [1.0, 2.0]
        with pytest.raises(InvalidValueError, match="temperatures"):
            state.validate()

    def test_rejects_unpinned_endpoints(self):
        state = sample()
        state.days[0].edges[0].time = 5
        with pytest.raises(InvalidValueError, match="midnight"):
            state.validate()

    def test_rejects_non_increasing_times(self):
        state = sample()
        state.days[0].edges[2].time = 10
        with pytest.raises(InvalidValueError, match="strictly increase"):
            state.validate()

    def test_rejects_an_unknown_level(self):
        state = sample()
        state.days[0].edges[1].level = 5
        with pytest.raises(InvalidValueError, match="not 0, 1 or 2"):
            state.validate()

    def test_rejects_a_level_changing_terminator(self):
        state = sample()
        state.days[0].edges[-1].level = 2
        with pytest.raises(InvalidValueError, match="terminates the day"):
            state.validate()

    def test_rejects_a_missing_day(self):
        state = sample()
        state.days.pop()
        with pytest.raises(InvalidValueError, match="days"):
            state.validate()


class TestCalendarType:
    def test_defaults_to_temperature(self):
        assert sample().calendar_type is CalendarType.TEMPERATURE

    def test_type_is_carried_through(self):
        state = CalendarState.from_json(SAMPLE, CalendarType.BLIND)
        assert state.calendar_type is CalendarType.BLIND


class TestPeriods:
    TZ = ZoneInfo("Europe/Prague")
    MONDAY = datetime(2026, 9, 14, tzinfo=TZ)

    def test_periods_are_contiguous(self):
        periods = sample().periods(self.MONDAY, self.MONDAY + timedelta(days=7))
        assert all(a.end == b.start for a, b in zip(periods, periods[1:], strict=False))

    def test_periods_cover_the_whole_window(self):
        end = self.MONDAY + timedelta(days=3)
        periods = sample().periods(self.MONDAY, end)
        assert periods[0].start <= self.MONDAY
        assert periods[-1].end >= end

    def test_no_empty_periods(self):
        periods = sample().periods(self.MONDAY, self.MONDAY + timedelta(days=7))
        assert all(p.end > p.start for p in periods)

    def test_a_period_is_merged_across_midnight(self):
        # The sample ends every day on NIGHT and opens the next on NIGHT.
        periods = sample().periods(self.MONDAY, self.MONDAY + timedelta(days=2))
        overnight = [p for p in periods if p.start.date() != p.end.date()]
        assert overnight, "an evening period must run into the next morning"
        assert all(p.level == CalendarLevel.NIGHT for p in overnight)

    def test_levels_follow_the_schedule(self):
        periods = sample().periods(self.MONDAY, self.MONDAY + timedelta(days=1))
        inside = [p for p in periods if p.start.date() == self.MONDAY.date()]
        assert [(f"{p.start:%H:%M}", p.level) for p in inside] == [
            ("06:00", 2),
            ("09:55", 1),
            ("15:10", 2),
            ("20:00", 1),
        ]

    def test_as_monday_resolves_to_monday(self):
        state = sample()
        state.days[2].as_monday = True
        state.days[2].set_transitions([CalendarEdge(0, 0)])  # would be all-Nobody on its own
        wednesday = state.day_for_weekday(2)
        assert [e.time for e in wednesday.transitions] == [e.time for e in state.days[0].transitions]

    def test_a_day_of_its_own_is_kept(self):
        state = sample()
        state.days[5].as_monday = False
        state.days[5].set_transitions([CalendarEdge(0, 0), CalendarEdge(120, 2)])
        assert [e.time for e in state.day_for_weekday(5).transitions] == [0, 120]

    def test_day_eight_is_never_dated(self):
        state = sample()
        state.days[7].set_transitions([CalendarEdge(0, 0)])
        periods = state.periods(self.MONDAY, self.MONDAY + timedelta(days=7))
        assert all(p.level != 0 for p in periods), "day 8 must not reach the week"

    def test_a_single_transition_day_is_one_period(self):
        state = sample()
        for day in state.days:
            day.as_monday = False
            day.set_transitions([CalendarEdge(0, 2)])
        periods = state.periods(self.MONDAY, self.MONDAY + timedelta(days=3))
        assert len(periods) == 1
        assert periods[0].level == 2

    def test_wall_clock_times_survive_a_dst_change(self):
        # 2026-03-29 is the European spring forward, 02:00 -> 03:00.
        start = datetime(2026, 3, 28, tzinfo=self.TZ)
        periods = sample().periods(start, start + timedelta(days=2))
        starts = {f"{p.start:%H:%M}" for p in periods}
        assert starts <= {"06:00", "09:55", "15:10", "20:00"}
        assert all(p.end > p.start for p in periods)

    def test_the_time_zone_of_the_window_is_used(self):
        periods = sample().periods(self.MONDAY, self.MONDAY + timedelta(days=1))
        assert all(p.start.tzinfo is self.TZ for p in periods)
