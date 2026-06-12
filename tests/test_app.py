import math

import pytest
from fastapi.testclient import TestClient

from em_workbench.app import app
from em_workbench.physics.contact import POINT_CHARGE_CONTACT_RADIUS_M
from em_workbench.presets import get_preset

client = TestClient(app)


def test_health_reports_the_static_electrostatics_service():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "em-workbench",
        "module": "static-electrostatics",
    }


def test_config_exposes_supported_views_and_local_browser_runtime():
    response = client.get("/api/config")

    assert response.status_code == 200
    config = response.json()
    assert config["product"] == {
        "name": "EM Workbench",
        "module": "Static Electrostatics",
    }
    assert config["supported_views"] == ["2D", "3D"]
    assert config["capabilities"] == {
        "scene_editing": "available",
        "solver": "available",
        "interaction": "available",
    }
    assert config["runtime"] == {
        "delivery": "local-vendor",
        "manifest_url": "/vendor/manifest.json",
        "three": {
            "version": "0.180.0",
            "module_url": "/vendor/three.module.js",
            "orbit_controls_url": "/vendor/controls/OrbitControls.js",
        },
    }


def test_root_serves_the_explicitly_scoped_workbench_shell():
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    html = response.text
    for expected_copy in (
        "电磁工作台",
        "大学电磁学",
        "2D",
        "3D",
        "源库",
        "场景源",
        "空间视窗",
        "测量面板",
        "所有数值计算都由 Python 求解器统一完成",
    ):
        assert expected_copy in html
    assert '<script type="importmap">' in html
    assert '"three": "./vendor/three.module.js"' in html
    assert 'href="./styles.css?v=20260612-scattering-motion-trails"' in html
    assert 'src="./app.js?v=20260612-scattering-motion-trails"' in html


def test_static_assets_and_vendor_modules_are_served_locally():
    stylesheet = client.get("/styles.css")
    application_module = client.get("/app.js")
    three_module = client.get("/vendor/three.module.js")
    orbit_controls = client.get("/vendor/controls/OrbitControls.js")
    manifest = client.get("/vendor/manifest.json")

    assert stylesheet.status_code == 200
    assert application_module.status_code == 200
    assert three_module.status_code == 200
    assert orbit_controls.status_code == 200
    assert manifest.status_code == 200
    assert "text/css" in stylesheet.headers["content-type"]
    assert "javascript" in application_module.headers["content-type"]
    assert "javascript" in three_module.headers["content-type"]
    assert "javascript" in orbit_controls.headers["content-type"]
    assert manifest.json()["version"] == "0.180.0"
    assert "https://" not in application_module.text


def test_desktop_runtime_disables_blurred_panel_compositing():
    stylesheet = client.get("/styles.css")
    application_module = client.get("/app.js")

    assert 'classList.toggle("desktop-runtime"' in application_module.text
    assert ".desktop-runtime .topbar" in stylesheet.text
    assert ".desktop-runtime .panel" in stylesheet.text
    assert ".desktop-runtime .source-point" in stylesheet.text
    assert "backdrop-filter: none" in stylesheet.text
    assert "filter: none" in stylesheet.text


def test_import_map_standard_orbit_controls_specifier_resolves_to_served_vendor_path():
    response = client.get("/")

    assert response.status_code == 200
    html = response.text
    assert '"three/addons/": "./vendor/"' in html

    resolved_orbit_controls = client.get("/vendor/controls/OrbitControls.js")
    assert resolved_orbit_controls.status_code == 200
    assert "javascript" in resolved_orbit_controls.headers["content-type"]


def test_three_entry_relative_dependency_is_served_locally():
    three_module = client.get("/vendor/three.module.js")

    assert "./three.core.js" in three_module.text
    three_core = client.get("/vendor/three.core.js")
    assert three_core.status_code == 200
    assert "javascript" in three_core.headers["content-type"]


def test_trajectory_endpoint_simulates_test_charge_motion():
    scene = get_preset("electric-dipole").scene.model_dump(mode="json")
    response = client.post(
        "/api/field/trajectory",
        json={
            "request_id": "trajectory-api-test",
            "scene": scene,
            "particle": {
                "charge_c": -1e-9,
                "mass_kg": 6e-6,
                "position": {"x": -0.08, "y": 0.04, "z": 0.0, "unit": "m"},
                "velocity": {"x": 0.06, "y": 0.0, "z": 0.0, "unit": "m"},
            },
            "dt_s": 0.005,
            "steps": 8,
            "quality": "preview",
        },
    )

    assert response.status_code == 200
    trajectory = response.json()
    assert trajectory["request_id"] == "trajectory-api-test"
    assert trajectory["step_count"] == 8
    assert len(trajectory["samples"]) == 9
    assert trajectory["samples"][0]["position"] != trajectory["samples"][-1]["position"]
    assert trajectory["execution"]["backend_effective"] == "cpu-jit"


def test_trajectory_endpoint_prevents_point_charge_contact_penetration():
    response = client.post(
        "/api/field/trajectory",
        json={
            "request_id": "trajectory-contact-test",
            "scene": {
                "id": "contact-scene",
                "title": "Contact scene",
                "sources": [
                    {
                        "id": "point-1",
                        "kind": "point",
                        "label": "Point charge",
                        "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
                        "charge_c": 1e-9,
                    }
                ],
            },
            "particle": {
                "charge_c": -1e-9,
                "mass_kg": 1e-6,
                "position": {"x": -0.012, "y": 0.0, "z": 0.0, "unit": "m"},
                "velocity": {"x": 0.4, "y": 0.0, "z": 0.0, "unit": "m"},
            },
            "dt_s": 0.001,
            "steps": 40,
            "quality": "preview",
        },
    )

    assert response.status_code == 200
    trajectory = response.json()
    distances = [
        math.hypot(
            sample["position"]["x"],
            sample["position"]["y"],
            sample["position"]["z"],
        )
        for sample in trajectory["samples"]
    ]
    assert min(distances) >= POINT_CHARGE_CONTACT_RADIUS_M - 1e-7


def test_compute_status_reports_cpu_and_optional_cuda_runtime() -> None:
    response = client.get("/api/compute/status")

    assert response.status_code == 200
    status = response.json()
    assert status["cpu"]["logical_processors"] >= 1
    assert status["warmup"]["state"] in {"warming", "ready"}
    assert isinstance(status["cuda"]["installed"], bool)
    assert isinstance(status["cuda"]["available"], bool)


def test_scattering_endpoint_simulates_rutherford_beam():
    response = client.post(
        "/api/scattering/evaluate",
        json={
            "request_id": "scatter-api-test",
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
        },
    )

    assert response.status_code == 200
    scatter = response.json()
    assert scatter["request_id"] == "scatter-api-test"
    assert len(scatter["tracks"]) == 3
    assert abs(scatter["tracks"][0]["scattering_angle_deg"]) > 170
    assert scatter["tracks"][1]["scattering_angle_deg"] > 0
    assert scatter["tracks"][2]["scattering_angle_deg"] < 0


def test_scattering_endpoint_can_use_current_scene_sources():
    response = client.post(
        "/api/scattering/evaluate",
        json={
            "request_id": "scatter-scene-api-test",
            "scene": {
                "id": "scatter-scene",
                "title": "Scatter scene",
                "sources": [
                    {
                        "id": "line-1",
                        "kind": "line_segment",
                        "label": "Line target",
                        "position": {"x": -0.04, "y": 0.0, "z": 0.0, "unit": "m"},
                        "orientation": {"x": 1.0, "y": 0.0, "z": 0.0},
                        "length_m": 0.08,
                        "charge_c": 1.0e-9,
                    }
                ],
            },
            "beam": {
                "charge_c": 1.0e-9,
                "mass_kg": 1.0e-6,
                "speed_m_per_s": 1.5,
                "start_x_m": -0.3,
                "impact_parameters_m": [0.03, -0.03],
            },
            "dt_s": 0.001,
            "max_steps": 800,
            "record_every": 20,
        },
    )

    assert response.status_code == 200
    scatter = response.json()
    assert scatter["request_id"] == "scatter-scene-api-test"
    assert scatter["field_model"] == "scene-sources"
    assert scatter["characteristic_distance_m"] == 0.0
    assert len(scatter["tracks"]) == 2
    assert scatter["tracks"][0]["scattering_angle_deg"] > 0.05
    assert scatter["tracks"][1]["scattering_angle_deg"] < -0.05


def test_scattering_endpoint_uses_single_point_scene_as_rutherford_nucleus():
    response = client.post(
        "/api/scattering/evaluate",
        json={
            "request_id": "scatter-point-scene-api-test",
            "scene": {
                "id": "scatter-point-scene",
                "title": "Scatter point scene",
                "sources": [
                    {
                        "id": "point-1",
                        "kind": "point",
                        "label": "Point target",
                        "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
                        "charge_c": 1.0e-9,
                    }
                ],
            },
            "beam": {
                "charge_c": 1.0e-9,
                "mass_kg": 1.0e-6,
                "speed_m_per_s": 1.5,
                "start_x_m": -0.5,
                "impact_parameters_m": [0.02, -0.02],
            },
            "dt_s": 0.001,
            "max_steps": 4000,
            "record_every": 20,
        },
    )

    assert response.status_code == 200
    scatter = response.json()
    assert scatter["field_model"] == "point-nucleus"
    assert scatter["characteristic_distance_m"] > 0
    for track in scatter["tracks"]:
        assert track["rutherford_angle_deg"] != 0
        assert track["scattering_angle_deg"] == pytest.approx(
            track["rutherford_angle_deg"],
            abs=0.4,
        )
