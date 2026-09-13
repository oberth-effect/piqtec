"""Tests for request building and response parsing."""

import pytest

from piqtec.api.generic import CalendarAPI, DeviceAPI, DriverAPI, ScenarioAPI, decode_value, encode_value
from piqtec.constants import MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES
from piqtec.controller import parse_responses
from piqtec.exceptions import InvalidValueError, IQtecError, ReadOnlyVariableError, RequestTooLongError
from piqtec.type_helpers import Get, RequestSet, Set
from piqtec.utils import find_ids, find_names, match_api, merge_requests, pack_chunks


def driver(name="R1.Var", access="PUS", typ="short", structure_id=1, offset=2, mask=None):
    return DriverAPI(
        name=name, access=access, param=False, typ=typ, structure_id=structure_id, offset=offset, mask=mask
    )


class TestAddressing:
    def test_address_without_mask(self):
        assert driver(structure_id=35, offset=8).address == "1/35/8"

    def test_address_with_mask(self):
        assert driver(structure_id=0, offset=2, mask=4).address == "1/0/2/4"

    def test_structure_address_reads_whole_driver(self):
        assert driver(structure_id=35).structure_address == "1/35/"

    def test_calendar_and_device_use_their_own_prefix(self):
        cal = CalendarAPI(
            name="_CALENDAR_00", access="PUS", param=True, typ="calendar", structure_id=3, offset=0, mask=None
        )
        dev = DeviceAPI(
            name="D.X", access="PUS", param=False, typ="short", device_id=1, device_structure_id=7, offset=2, mask=None
        )
        assert cal.address == "2/3/0"
        assert dev.address == "5/7/2"

    def test_readonly_follows_upper_case_u(self):
        assert driver(access="us").readonly
        assert not driver(access="PUS").readonly

    def test_set_request_refused_for_readonly(self):
        with pytest.raises(ReadOnlyVariableError):
            driver(access="us").set_request(1)

    def test_set_request_renders_booleans_as_digits(self):
        assert driver().set_request(True).setters == [Set(path="1/1/2", value="1")]


class TestEncoding:
    @pytest.mark.parametrize(
        ("typ", "value", "expected"),
        [
            ("byte", 3.0, "3"),
            ("word", 500.0, "500"),
            ("bool", 1.0, "1"),
            ("FiveMinutes", 24.0, "24"),
            ("OnOffAuto", 2, "2"),
            ("Temperature", 21.5, "21.5"),
            ("Temperature", 21, "21"),
            ("string16", "Obyvak", "Obyvak"),
        ],
    )
    def test_integer_types_are_written_as_whole_numbers(self, typ, value, expected):
        assert encode_value(typ, value) == expected

    def test_a_fraction_cannot_be_written_to_an_integer_type(self):
        with pytest.raises(InvalidValueError):
            encode_value("byte", 3.5)

    def test_strings_are_passed_through_untouched(self):
        assert encode_value("byte", "3.0") == "3.0"

    def test_what_is_written_can_be_read_back(self):
        for typ, value in [("byte", 3.0), ("bool", 1.0), ("short", -4.0)]:
            assert decode_value(typ, encode_value(typ, value)) == value

    def test_set_request_uses_the_declared_type(self):
        assert driver(typ="byte").set_request(3.0).setters[0].value == "3"


class TestDecoding:
    @pytest.mark.parametrize(
        ("typ", "raw", "expected"),
        [
            ("bool", "1", True),
            ("bool", "0", False),
            ("short", "-12", -12),
            ("Temperature", "13.8", 13.8),
            ("Temperature", "5", 5.0),
            ("string16", " Obyvak ", "Obyvak"),
            ("Humidity", "0", 0.0),
            ("OnOffAuto", "2", 2),
        ],
    )
    def test_declared_type_picks_python_type(self, typ, raw, expected):
        assert decode_value(typ, raw) == expected

    def test_sentinel_becomes_none(self):
        assert decode_value("Temperature", "!off") is None

    def test_undecodable_value_becomes_none(self):
        assert decode_value("short", "not a number") is None

    def test_unknown_type_passes_through(self):
        assert decode_value("mystery", "abc") == "abc"

    def test_api_parse_returns_none_when_absent(self):
        assert driver().parse({}) is None


class TestParseResponses:
    def test_splits_on_first_equals_only(self):
        parsed = parse_responses('2/0/0={"Name":"a=b"}')
        assert parsed["2/0/0"].value == '{"Name":"a=b"}'

    def test_skips_blank_and_malformed_lines(self):
        parsed = parse_responses("1/0/1=5\n\ngarbage\n1/0/2=6\n")
        assert set(parsed) == {"1/0/1", "1/0/2"}

    def test_empty_value_is_kept(self):
        assert parse_responses("1/0/1=").get("1/0/1").value == ""


class TestPackChunks:
    def test_packs_into_one_chunk_when_it_fits(self):
        items = [(f"1/{i}/", 10) for i in range(5)]
        assert pack_chunks(items, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES) == ["1/0/;1/1/;1/2/;1/3/;1/4/"]

    def test_splits_on_the_response_budget(self):
        items = [("1/0/", 3000), ("1/1/", 3000)]
        assert pack_chunks(items, MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES) == ["1/0/", "1/1/"]

    def test_splits_on_the_request_budget(self):
        items = [("1/0/0", 1), ("1/1/1", 1), ("1/2/2", 1)]
        chunks = pack_chunks(items, max_request_bytes=13, max_response_bytes=MAX_RESPONSE_BYTES)
        assert chunks == ["1/0/0;1/1/1", "1/2/2"]

    def test_request_overhead_is_counted(self):
        items = [("1/0/0", 1), ("1/1/1", 1)]
        # Both fit in 13 bytes on their own, but not once the path prefix is added.
        assert pack_chunks(items, 13, MAX_RESPONSE_BYTES) == ["1/0/0;1/1/1"]
        assert pack_chunks(items, 20, MAX_RESPONSE_BYTES, overhead=10) == ["1/0/0", "1/1/1"]

    def test_single_item_over_budget_raises(self):
        with pytest.raises(RequestTooLongError):
            pack_chunks([("1/0/", 99_999)], MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES)

    def test_empty_input_makes_no_requests(self):
        assert pack_chunks([], MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES) == []


class TestMatchApi:
    def test_driver(self):
        api = match_api(
            {
                "name": "SYSTEM.HDO",
                "category": "driver",
                "type": "bool",
                "access": "Pus",
                "param": "0",
                "structure_id": "0",
                "offset": "2",
                "mask": "4",
            }
        )
        assert isinstance(api, DriverAPI)
        assert api.address == "1/0/2/4"

    def test_page_has_no_address(self):
        api = match_api({"name": "P", "category": "page", "access": "s", "param": "0", "structure_id": "1"})
        with pytest.raises(IQtecError):
            _ = api.address

    def test_unknown_category_is_skipped(self):
        assert match_api({"name": "X", "category": "nonsense"}) is None

    def test_malformed_attribute_is_skipped(self):
        assert match_api({"name": "X", "category": "driver", "param": "abc"}) is None
        assert match_api({"name": "X", "category": "driver", "offset": "two"}) is None


class TestRequestSet:
    def test_addition_keeps_both_sides(self):
        a = RequestSet(getters=[Get("1/0/")], setters=[Set("1/0/1", "1")])
        b = RequestSet(getters=[Get("1/1/")], setters=[Set("1/1/1", "2")])
        combined = a + b
        assert len(combined.getters) == 2
        assert len(combined.setters) == 2

    def test_merge_requests_keeps_setters(self):
        merged = merge_requests([RequestSet(getters=[Get("1/0/")], setters=[Set("1/0/1", "1")])])
        assert merged.setters == [Set("1/0/1", "1")]

    def test_sum_starts_from_zero(self):
        assert sum([RequestSet(getters=[Get("1/0/")])], RequestSet()).getters == [Get("1/0/")]


class TestNameLookup:
    NAMES = ["R1.A", "R1.B", "R10.A", "R1_SUNBLIND_1.A", "SYSTEM.A"]

    def test_find_ids_matches_on_the_unit_prefix(self):
        assert find_ids(self.NAMES, r"^R\d{1,2}$") == ["R1", "R10"]

    def test_find_names_is_an_exact_prefix_match(self):
        assert find_names(self.NAMES, "R1") == ["R1.A", "R1.B"]

    def test_find_names_does_not_treat_the_id_as_a_pattern(self):
        assert find_names(["A.B", "A+B.C"], "A+B") == ["A+B.C"]


class TestMaskZero:
    """Scenario records use the fourth path component as a field index, so a
    mask of 0 is meaningful and must not be dropped."""

    def test_mask_zero_is_kept(self):
        api = ScenarioAPI(
            name="_sbScenario_00_name", access="US", param=False, typ="string16", structure_id=1, offset=0, mask=0
        )
        assert api.address == "8/1/0/0"

    def test_absent_mask_is_omitted(self):
        assert driver(structure_id=1, offset=0, mask=None).address == "1/1/0"

    def test_device_keeps_mask_zero(self):
        api = DeviceAPI(
            name="D.X", access="US", param=False, typ="short", device_id=1, device_structure_id=7, offset=2, mask=0
        )
        assert api.address == "5/7/2/0"

    def test_match_api_reads_a_zero_mask(self):
        api = match_api(
            {
                "name": "_sbScenario_00_name",
                "category": "sbScenario",
                "type": "string16",
                "access": "US",
                "param": "0",
                "structure_id": "1",
                "offset": "0",
                "mask": "0",
            }
        )
        assert api.mask == 0
        assert api.address == "8/1/0/0"
