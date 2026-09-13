"""Tests for the unit layer, including partial installations."""

import pytest

from piqtec.api.generic import DriverAPI
from piqtec.constants import TILT_TIME_OFFSET, RoomCorrectionMode, RoomMode, SunblindCommand
from piqtec.exceptions import InvalidValueError, IQtecError, MissingVariableError
from piqtec.type_helpers import Response
from piqtec.unit.device import Device
from piqtec.unit.room import Room, RoomState
from piqtec.unit.sunblind import Sunblind


class FakeController:
    """Records request sets instead of talking to a controller."""

    def __init__(self, responses=None):
        self.calls = []
        self.responses = responses or {}

    def api_call(self, request_set):
        self.calls.append(request_set)
        return self.responses

    @property
    def setter_paths(self):
        return [(s.path, s.value) for call in self.calls for s in call.setters]


def room_apis(*, include=None, exclude=()):
    """Driver APIs for a room, so tests can drop variables at will."""
    from piqtec.constants import RoomVar

    apis = {}
    for offset, var in enumerate(RoomVar):
        if var.name in exclude or (include is not None and var.name not in include):
            continue
        temperatures = {"requested_temperature", "correction_temperature", "actual_temperature"}
        typ = "string16" if var.name == "name" else "Temperature" if var.name in temperatures else "short"
        apis[f"R1.{var.value}"] = DriverAPI(
            name=f"R1.{var.value}", access="PUS", param=False, typ=typ, structure_id=35, offset=offset, mask=None
        )
    return apis


class TestPartialInstallations:
    def test_missing_variables_read_back_as_none(self):
        unit = Room(FakeController(), "R1", room_apis(exclude={"humidity", "eco_mode"}))
        state = unit.parse_state({})
        assert state.humidity is None
        assert state.eco_mode is None

    def test_state_is_complete_even_when_the_controller_is_not(self):
        unit = Room(FakeController(), "R1", room_apis(include={"name", "actual_temperature"}))
        state = unit.parse_state({"1/35/1": Response("1/35/1", "Obyvak")})
        assert isinstance(state, RoomState)
        assert state.name == "Obyvak"

    def test_unit_with_no_variables_requests_nothing(self):
        unit = Room(FakeController(), "R9", {})
        assert not unit.available
        assert unit.get_request.getters == []

    def test_setting_an_absent_variable_raises(self):
        unit = Room(FakeController(), "R1", room_apis(include={"name"}))
        with pytest.raises(MissingVariableError, match="R1 has no variable 'room_mode'") as err:
            unit.set_room_mode(RoomMode.OFF)
        assert isinstance(err.value, IQtecError)
        assert isinstance(err.value, KeyError), "callers catching KeyError keep working"

    def test_batched_writes_report_an_absent_variable_the_same_way(self):
        controller = FakeController()
        unit = Room(controller, "R1", room_apis(exclude={"correction_temperature"}))
        with pytest.raises(MissingVariableError, match="correction_temperature"):
            unit.set_manual_temperature(21.5, 24)
        assert controller.calls == [], "nothing is sent when part of the batch cannot be"

    def test_device_reports_an_absent_variable_as_iqtec_error(self):
        with pytest.raises(MissingVariableError):
            Device(FakeController(), "PUMP", {}).set_value("PUMP.Out", 1)


class TestRoomWrites:
    def test_manual_temperature_is_one_request_in_order(self):
        controller = FakeController()
        unit = Room(controller, "R1", room_apis())
        unit.set_manual_temperature(21.5, 24)

        assert len(controller.calls) == 1, "mode, duration and setpoint must not race"
        values = [value for _, value in controller.setter_paths]
        assert values == [str(int(RoomCorrectionMode.MANUAL)), "24", "21.5"]

    def test_set_room_mode_writes_the_enum_value(self):
        controller = FakeController()
        Room(controller, "R1", room_apis()).set_room_mode(RoomMode.HOLIDAY)
        assert controller.setter_paths[0][1] == "2"


class TestSunblind:
    def _sunblind(self, controller, **state):
        from piqtec.constants import SunblindVar

        apis = {}
        for offset, var in enumerate(SunblindVar):
            apis[f"SB.{var.value}"] = DriverAPI(
                name=f"SB.{var.value}", access="PUS", param=False, typ="short", structure_id=9, offset=offset, mask=None
            )
        unit = Sunblind(controller, "SB", apis)
        controller.responses = {
            unit.apis[name].address: Response(unit.apis[name].address, str(value)) for name, value in state.items()
        }
        return unit

    def test_full_open_uses_the_dedicated_command(self):
        controller = FakeController()
        unit = self._sunblind(controller)
        unit.set_position(0)
        assert controller.setter_paths == [(unit.apis["command"].address, str(int(SunblindCommand.UP)))]
        assert len(controller.calls) == 1, "endpoint commands must not fall through to stepping"

    def test_full_close_uses_the_dedicated_command(self):
        controller = FakeController()
        unit = self._sunblind(controller)
        unit.set_position(1000)
        assert controller.setter_paths == [(unit.apis["command"].address, str(int(SunblindCommand.DOWN)))]
        assert len(controller.calls) == 1

    def test_step_writes_time_and_command_together(self):
        controller = FakeController()
        unit = self._sunblind(controller, position=0, move_time=20, rotation=0, full_time_time=100)
        unit.set_position(500)
        # stop, read, then one request carrying both step_time and command
        assert len(controller.calls[-1].setters) == 2

    def _step_time(self, **state) -> int:
        controller = FakeController()
        unit = self._sunblind(controller, **state)
        unit.set_position(500)
        return int(dict(controller.setter_paths)[unit.apis["step_time"].address])

    def test_step_time_corrects_for_the_tilt_still_to_come(self):
        # Half the travel at 20 s, plus closing the slats fully from open.
        assert (
            self._step_time(position=0, move_time=20, rotation=0, full_time_time=100) == 10000 + 100 + TILT_TIME_OFFSET
        )
        # Slats already closed: nothing to correct.
        assert self._step_time(position=0, move_time=20, rotation=180, full_time_time=100) == 10000 + TILT_TIME_OFFSET

    def test_unknown_rotation_is_not_assumed_open(self):
        # With the rotation unreadable no tilt correction is applied, the same
        # policy set_rotation follows, instead of overshooting on closed slats.
        assert self._step_time(position=0, move_time=20, full_time_time=100) == 10000 + TILT_TIME_OFFSET
        assert self._step_time(position=0, move_time=20, rotation=0) == 10000 + TILT_TIME_OFFSET

    def test_out_of_range_is_rejected(self):
        unit = self._sunblind(FakeController())
        with pytest.raises(InvalidValueError) as err:
            unit.set_position(5000)
        assert isinstance(err.value, ValueError), "callers catching ValueError keep working"
        with pytest.raises(InvalidValueError):
            unit.set_rotation(-1)

    def test_missing_step_time_variable_is_an_iqtec_error(self):
        from piqtec.constants import SunblindVar

        apis = {
            f"SB.{var.value}": DriverAPI(
                name=f"SB.{var.value}", access="PUS", param=False, typ="short", structure_id=9, offset=i, mask=None
            )
            for i, var in enumerate(SunblindVar)
            if var.name != "step_time"
        }
        controller = FakeController()
        unit = Sunblind(controller, "SB", apis)
        controller.responses = {
            unit.apis[name].address: Response(unit.apis[name].address, str(value))
            for name, value in {"position": 0, "move_time": 20, "rotation": 0, "full_time_time": 100}.items()
        }
        with pytest.raises(MissingVariableError, match="step_time"):
            unit.set_position(500)

    def test_unknown_position_does_not_move(self):
        controller = FakeController()
        unit = self._sunblind(controller)  # no state at all
        unit.set_position(500)
        assert all(len(call.setters) <= 1 for call in controller.calls)


class TestDevice:
    def _apis(self):
        return {
            "PUMP.Out": DriverAPI(
                name="PUMP.Out", access="us", param=False, typ="bool", structure_id=5, offset=0, mask=None
            ),
            "PUMP.Set": DriverAPI(
                name="PUMP.Set", access="PUS", param=False, typ="Temperature", structure_id=5, offset=2, mask=None
            ),
            "PUMP2.Out": DriverAPI(
                name="PUMP2.Out", access="us", param=False, typ="bool", structure_id=6, offset=0, mask=None
            ),
        }

    def test_splits_by_writability(self):
        device = Device(FakeController(), "PUMP", self._apis())
        assert set(device.sensor_apis) == {"PUMP.Out"}
        assert set(device.switch_apis) == {"PUMP.Set"}

    def test_prefix_match_is_exact(self):
        device = Device(FakeController(), "PUMP", self._apis())
        assert "PUMP2.Out" not in device.all_apis

    def test_reads_the_whole_structure_in_one_getter(self):
        device = Device(FakeController(), "PUMP", self._apis())
        assert device.get_request.getters[0].path == "1/5/"

    def test_writing_a_readonly_variable_raises(self):
        device = Device(FakeController(), "PUMP", self._apis())
        with pytest.raises(MissingVariableError):
            device.set_value("PUMP.Out", 1)

    def test_a_float_from_a_slider_is_written_as_the_declared_type(self):
        controller = FakeController()
        apis = self._apis()
        apis["PUMP.Speed"] = DriverAPI(
            name="PUMP.Speed", access="PUS", param=False, typ="byte", structure_id=5, offset=3, mask=None
        )
        Device(controller, "PUMP", apis).set_value("PUMP.Speed", 3.0)
        assert controller.setter_paths == [("1/5/3", "3")]

    def test_values_are_decoded_by_declared_type(self):
        device = Device(FakeController(), "PUMP", self._apis())
        state = device.parse_state(
            {"1/5/0": Response("1/5/0", "1"), "1/5/2": Response("1/5/2", "21.5")},
        )
        assert state.sensors["PUMP.Out"] is True
        assert state.switches["PUMP.Set"] == 21.5
