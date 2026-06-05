from __future__ import annotations

import json

from em_workbench.desktop import _bridge_bootstrap_script, _retain_desktop_objects
from em_workbench.desktop_bridge import DesktopComputeQueue, WorkbenchDesktopBridge
from em_workbench.presets import get_preset


def test_desktop_bridge_exposes_config_without_http_server() -> None:
    bridge = WorkbenchDesktopBridge()

    config = json.loads(bridge.config())

    assert config["product"]["name"] == "EM Workbench"
    assert config["supported_views"] == ["2D", "3D"]


def test_desktop_bridge_lists_and_loads_presets_without_http_server() -> None:
    bridge = WorkbenchDesktopBridge()

    presets = json.loads(bridge.list_presets())
    dipole = json.loads(bridge.get_preset(json.dumps({"preset_id": "electric-dipole"})))

    assert any(preset["id"] == "electric-dipole" for preset in presets)
    assert dipole["scene"]["id"] == get_preset("electric-dipole").scene.id


def test_desktop_bridge_evaluates_field_without_http_server() -> None:
    bridge = WorkbenchDesktopBridge()
    preset = json.loads(bridge.get_preset(json.dumps({"preset_id": "electric-dipole"})))

    result = json.loads(
        bridge.evaluate_field(
            json.dumps(
                {
                    "request_id": "desktop-test",
                    "scene": preset["scene"],
                    "sample_points": [{"x": 0.2, "y": 0.0, "z": 0.0, "unit": "m"}],
                    "quality": "preview",
                }
            )
        )
    )

    assert result["request_id"] == "desktop-test"
    assert result["sample_count"] == 1
    assert result["samples"][0]["field_magnitude_v_per_m"] > 0


def test_desktop_bridge_simulates_trajectory_without_http_server() -> None:
    bridge = WorkbenchDesktopBridge()
    preset = json.loads(bridge.get_preset(json.dumps({"preset_id": "electric-dipole"})))

    result = json.loads(
        bridge.evaluate_trajectory(
            json.dumps(
                {
                    "request_id": "desktop-trajectory-test",
                    "scene": preset["scene"],
                    "particle": {
                        "charge_c": -1e-9,
                        "mass_kg": 6e-6,
                        "position": {"x": -0.08, "y": 0.04, "z": 0.0, "unit": "m"},
                        "velocity": {"x": 0.06, "y": 0.0, "z": 0.0, "unit": "m"},
                    },
                    "dt_s": 0.005,
                    "steps": 8,
                    "quality": "preview",
                }
            )
        )
    )

    assert result["request_id"] == "desktop-trajectory-test"
    assert result["step_count"] == 8
    assert len(result["samples"]) == 9


def test_desktop_bridge_evaluates_field_lines_without_http_server() -> None:
    bridge = WorkbenchDesktopBridge()
    preset = json.loads(bridge.get_preset(json.dumps({"preset_id": "electric-dipole"})))

    result = json.loads(
        bridge.evaluate_field_lines(
            json.dumps(
                {
                    "request_id": "desktop-field-lines-test",
                    "scene": preset["scene"],
                    "bounds": {"min_x": -0.2, "max_x": 0.2, "min_y": -0.2, "max_y": 0.2},
                    "quality": "preview",
                    "backend": "cpu",
                }
            )
        )
    )

    assert result["request_id"] == "desktop-field-lines-test"
    assert result["lines"]


def test_desktop_queue_returns_ticket_then_result() -> None:
    queue = DesktopComputeQueue()

    ticket = queue.submit("status", "")
    result = queue.wait(ticket, timeout_s=5)

    assert json.loads(result)["cpu"]["logical_processors"] >= 1


def test_desktop_bridge_simulates_scattering_without_http_server() -> None:
    bridge = WorkbenchDesktopBridge()

    result = json.loads(
        bridge.evaluate_scattering(
            json.dumps(
                {
                    "request_id": "desktop-scatter-test",
                    "nucleus": {
                        "charge_c": 1.0e-9,
                        "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
                    },
                    "beam": {
                        "charge_c": 1.0e-9,
                        "mass_kg": 1.0e-6,
                        "speed_m_per_s": 1.5,
                        "start_x_m": -0.5,
                        "impact_parameters_m": [0.0, 0.02, -0.02],
                    },
                    "dt_s": 0.001,
                    "max_steps": 4000,
                    "record_every": 20,
                }
            )
        )
    )

    assert result["request_id"] == "desktop-scatter-test"
    assert len(result["tracks"]) == 3
    assert abs(result["tracks"][0]["scattering_angle_deg"]) > 170


def test_desktop_bridge_bootstrap_waits_for_document_root() -> None:
    script = _bridge_bootstrap_script()

    assert "function appendBridgeScript()" in script
    assert "if (!document.documentElement)" in script
    assert "const retryDelayMs = 16;" in script
    assert "window.setTimeout(appendBridgeScript, retryDelayMs);" in script
    assert "window.setTimeout(attachBridge, retryDelayMs);" in script


def test_desktop_window_retains_bridge_objects() -> None:
    class View:
        pass

    view = View()
    channel = object()
    bridge = object()

    _retain_desktop_objects(view, channel, bridge)

    assert view._em_workbench_channel is channel
    assert view._em_workbench_bridge is bridge
