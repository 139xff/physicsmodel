from __future__ import annotations

import json

from em_workbench.desktop_bridge import WorkbenchDesktopBridge
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
