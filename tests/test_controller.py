"""Tests driving the real Controller against a canned data.xml and replies."""

from xml.etree import ElementTree

import pytest

from piqtec.api.generic import DeviceAPI, ScenarioAPI
from piqtec.constants import MAX_RESPONSE_BYTES
from piqtec.controller import Controller, base_url
from piqtec.exceptions import IQtecError, MissingVariableError
from piqtec.unit.calendar import CalendarState

SYSTEM = [
    {"name": "SYSTEM.HDO", "category": "driver", "type": "bool", "access": "us", "structure_id": "0", "offset": "2"},
    {
        "name": "SYSTEM.USER1",
        "category": "driver",
        "type": "short",
        "access": "PUS",
        "structure_id": "0",
        "offset": "5",
    },
]


def variable(**attrib: str) -> dict[str, str]:
    return {"category": "driver", "type": "short", "access": "PUS", "param": "0", "structure_id": "1", **attrib}


def connect(monkeypatch, variables, replies=None):
    """A Controller whose data.xml and replies are canned; returns it and the chunks it requested."""
    root = ElementTree.Element("data")
    for attrib in variables:
        ElementTree.SubElement(root, "variable", attrib)
    chunks: list[str] = []

    def call_chunk(self, chunk):
        chunks.append(chunk)
        return replies or {}

    monkeypatch.setattr(Controller, "_get_xml", lambda self: root)
    monkeypatch.setattr(Controller, "_call_chunk", call_chunk)
    return Controller("controller"), chunks


class TestBaseUrl:
    def test_plain_host(self):
        assert base_url("http", "192.168.1.5:80") == "http://192.168.1.5:80"

    def test_trailing_slash_is_dropped(self):
        assert base_url("http", "192.168.1.5/") == "http://192.168.1.5"

    def test_a_scheme_in_the_host_wins(self):
        assert base_url("http", "https://iqtec.home/") == "https://iqtec.home"

    def test_controller_normalises_its_host(self, monkeypatch):
        monkeypatch.setattr(Controller, "_get_xml", lambda self: ElementTree.Element("data"))
        controller = Controller("http://iqtec.home/")
        assert controller.host == "iqtec.home"
        assert controller._base_url == "http://iqtec.home"


class TestDiscovery:
    def test_unsupported_entries_are_skipped_not_fatal(self, monkeypatch):
        controller, _ = connect(
            monkeypatch,
            [
                *SYSTEM,
                {"name": "NEW.Thing", "category": "somethingNew"},
                variable(name="BAD.Param", param="abc", offset="1"),
            ],
        )
        assert set(controller.apis) == {"SYSTEM.HDO", "SYSTEM.USER1"}
        assert controller.system.available

    def test_every_category_is_reachable_by_name(self, monkeypatch):
        controller, _ = connect(
            monkeypatch,
            [
                *SYSTEM,
                {
                    "name": "_sbScenario_00_name",
                    "category": "sbScenario",
                    "type": "string16",
                    "access": "US",
                    "structure_id": "1",
                    "offset": "0",
                    "mask": "0",
                },
                {
                    "name": "DW1.Temp",
                    "category": "device",
                    "type": "Temperature",
                    "access": "us",
                    "device_id": "1",
                    "device_structure_id": "7",
                    "offset": "2",
                },
            ],
        )
        assert isinstance(controller.apis["_sbScenario_00_name"], ScenarioAPI)
        assert controller.apis["_sbScenario_00_name"].address == "8/1/0/0"
        assert isinstance(controller.apis["DW1.Temp"], DeviceAPI)
        assert controller.read(controller.apis["DW1.Temp"]) is None  # requested, nothing canned

    def test_an_unknown_calendar_is_an_iqtec_error(self, monkeypatch):
        controller, _ = connect(monkeypatch, SYSTEM)
        with pytest.raises(MissingVariableError) as err:
            controller.write_calendar("_CALENDAR_99", CalendarState())
        assert isinstance(err.value, IQtecError)


class TestStructureReads:
    def test_a_structure_that_fits_is_read_in_one_go(self, monkeypatch):
        controller, chunks = connect(
            monkeypatch, [*SYSTEM, variable(name="PUMP.A", offset="0"), variable(name="PUMP.B", offset="1")]
        )
        controller.update()
        assert any("1/1/" in chunk.split(";") for chunk in chunks)

    def test_an_oversized_structure_is_read_variable_by_variable(self, monkeypatch):
        big = [
            variable(name=f"BIG.V{i}", type="string16", access="us", structure_id="40", offset=str(i))
            for i in range(170)
        ]
        controller, chunks = connect(monkeypatch, [*SYSTEM, *big])
        assert controller._structure_bytes["1/40/"] > MAX_RESPONSE_BYTES

        state = controller.update()  # must not raise RequestTooLongError

        requested = [path for chunk in chunks for path in chunk.split(";")]
        assert "1/40/" not in requested
        assert {f"1/40/{i}" for i in range(170)} <= set(requested)
        assert len(chunks) > 1, "the members themselves are chunked against the budget"
        assert "BIG" in state.devices

    def test_a_raw_structure_read_keeps_its_own_estimate(self, monkeypatch):
        from piqtec.type_helpers import Get, RequestSet

        big = [
            variable(name=f"BIG.V{i}", type="string16", access="us", structure_id="40", offset=str(i))
            for i in range(170)
        ]
        controller, chunks = connect(monkeypatch, [*SYSTEM, *big])
        controller.api_call(RequestSet(getters=[Get("1/40/", expected_bytes=100)]))
        assert chunks == ["1/40/"]
