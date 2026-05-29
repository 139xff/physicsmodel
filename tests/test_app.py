from fastapi.testclient import TestClient

from em_workbench.app import app

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
    assert 'src="./app.js?v=20260530-probe-size"' in html


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
