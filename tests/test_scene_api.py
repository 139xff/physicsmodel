from fastapi.testclient import TestClient

from em_workbench.app import app

client = TestClient(app)


def test_presets_list_is_stable_and_does_not_claim_solver_results():
    response = client.get("/api/presets")

    assert response.status_code == 200
    presets = response.json()
    assert [preset["id"] for preset in presets] == [
        "single-point",
        "electric-dipole",
        "charged-ring-axis",
        "disk-approaching-plane",
        "spherical-shell-inside-outside",
    ]
    assert presets[0] == {
        "id": "single-point",
        "title": "Single point charge",
        "description": "One editable point charge at the origin.",
        "source_count": 1,
        "source_kinds": ["point"],
    }
    assert "field" not in presets[0]
    assert "potential" not in presets[0]


def test_preset_detail_returns_an_editable_scene_payload():
    response = client.get("/api/presets/electric-dipole")

    assert response.status_code == 200
    preset = response.json()
    assert preset["id"] == "electric-dipole"
    assert preset["scene"]["id"] == "preset-electric-dipole"
    assert [source["charge_c"] for source in preset["scene"]["sources"]] == [1.0e-9, -1.0e-9]

    edited_scene = preset["scene"]
    edited_scene["sources"][0]["position"]["x"] = -0.08
    edited_scene["sources"].append(
        {
            "id": "student-third-charge",
            "kind": "point",
            "label": "Student third charge",
            "position": {"x": 0.0, "y": 0.08, "z": 0.0},
            "charge_c": 5.0e-10,
        }
    )
    validation = client.post("/api/scene/validate", json=edited_scene)

    assert validation.status_code == 200
    body = validation.json()
    assert body["valid"] is True
    assert body["source_count"] == 3
    assert body["source_kinds"] == ["point", "point", "point"]
    assert body["scene"]["sources"][0]["position"]["x"] == -0.08


def test_scene_validation_accepts_all_source_kinds_and_normalizes_directions():
    scene = {
        "id": "api-six-source-scene",
        "title": "API six source scene",
        "sources": [
            {
                "id": "point-api",
                "kind": "point",
                "label": "Point",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "charge_c": 1.0e-9,
            },
            {
                "id": "line-api",
                "kind": "line_segment",
                "label": "Line",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "orientation": {"x": 0.0, "y": 0.0, "z": 8.0},
                "length_m": 0.3,
                "linear_charge_density_c_per_m": 2.0e-9,
            },
            {
                "id": "ring-api",
                "kind": "ring",
                "label": "Ring",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "normal": {"x": 0.0, "y": 7.0, "z": 0.0},
                "radius_m": 0.15,
                "charge_c": 4.0e-9,
            },
            {
                "id": "disk-api",
                "kind": "disk",
                "label": "Disk",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "normal": {"x": 1.0, "y": 0.0, "z": 0.0},
                "radius_m": 0.2,
                "surface_charge_density_c_per_m2": -3.0e-9,
            },
            {
                "id": "plane-api",
                "kind": "infinite_plane",
                "label": "Plane",
                "position": {"x": 0.0, "y": 0.0, "z": -0.2},
                "normal": {"x": 0.0, "y": 0.0, "z": -4.0},
                "display_extent_m": 1.0,
                "surface_charge_density_c_per_m2": 1.5e-9,
            },
            {
                "id": "shell-api",
                "kind": "spherical_shell",
                "label": "Shell",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "radius_m": 0.35,
                "surface_charge_density_c_per_m2": 1.1e-9,
            },
        ],
    }

    response = client.post("/api/scene/validate", json=scene)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is True
    assert body["source_count"] == 6
    assert body["source_kinds"] == [
        "point",
        "line_segment",
        "ring",
        "disk",
        "infinite_plane",
        "spherical_shell",
    ]
    assert body["scene"]["sources"][1]["orientation"] == {"x": 0.0, "y": 0.0, "z": 1.0}
    assert body["scene"]["sources"][4]["normal"] == {"x": 0.0, "y": 0.0, "z": -1.0}


def test_scene_validation_rejects_invalid_source_contracts_with_422():
    invalid_scene = {
        "id": "invalid-scene",
        "title": "Invalid scene",
        "sources": [
            {
                "id": "invalid-ring",
                "kind": "ring",
                "label": "Invalid ring",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "normal": {"x": 0.0, "y": 0.0, "z": 0.0},
                "radius_m": 0.0,
                "charge_c": 1.0e-9,
                "linear_charge_density_c_per_m": 2.0e-9,
            }
        ],
    }

    response = client.post("/api/scene/validate", json=invalid_scene)

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert any("zero" in str(item).lower() for item in detail)
    assert any("greater than 0" in str(item).lower() for item in detail)


def test_missing_preset_returns_404_without_falling_through_to_static_shell():
    response = client.get("/api/presets/not-a-preset")

    assert response.status_code == 404
    assert response.json() == {"detail": "Preset not found."}
