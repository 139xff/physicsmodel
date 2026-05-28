import math

import pytest
from fastapi.testclient import TestClient

from em_workbench.app import app
from em_workbench.physics.solver import COULOMB_CONSTANT

client = TestClient(app)


def _single_point_request(request_id: str = "solver-api-1") -> dict:
    return {
        "request_id": request_id,
        "quality": "preview",
        "scene": {
            "id": "api-solver-scene",
            "title": "API solver scene",
            "sources": [
                {
                    "id": "api-point",
                    "kind": "point",
                    "label": "API point",
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "charge_c": 1.0e-9,
                }
            ],
        },
        "sample_points": [
            {"x": 0.2, "y": 0.0, "z": 0.0},
            {"x": 0.4, "y": 0.0, "z": 0.0},
        ],
    }


def test_config_marks_solver_capability_available():
    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json()["capabilities"]["solver"] == "available"


def test_field_evaluate_batches_sample_points_and_echoes_request_version_and_quality():
    response = client.post("/api/field/evaluate", json=_single_point_request("batch-req-42"))

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "batch-req-42"
    assert body["result_version"].startswith("electrostatic-solver-")
    assert body["quality"] == "preview"
    assert body["sample_count"] == 2
    assert len(body["samples"]) == 2
    assert body["metadata"]["quality"] == "preview"

    first = body["samples"][0]
    second = body["samples"][1]
    assert first["point"] == {"x": 0.2, "y": 0.0, "z": 0.0, "unit": "m"}
    assert first["potential_v"] == pytest.approx(COULOMB_CONSTANT * 1.0e-9 / 0.2)
    assert first["field_v_per_m"]["x"] == pytest.approx(COULOMB_CONSTANT * 1.0e-9 / 0.2**2)
    assert second["potential_v"] == pytest.approx(COULOMB_CONSTANT * 1.0e-9 / 0.4)
    assert first["contributions"][0]["source_id"] == "api-point"
    assert math.isfinite(first["field_magnitude_v_per_m"])


def test_field_evaluate_refined_ring_response_includes_per_source_metadata():
    request = {
        "request_id": "ring-api-request",
        "quality": "refined",
        "scene": {
            "id": "api-ring-scene",
            "title": "API ring scene",
            "sources": [
                {
                    "id": "api-ring",
                    "kind": "ring",
                    "label": "API ring",
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                    "radius_m": 0.12,
                    "charge_c": 4.0e-9,
                }
            ],
        },
        "sample_points": [{"x": 0.0, "y": 0.0, "z": 0.2}],
    }

    response = client.post("/api/field/evaluate", json=request)

    assert response.status_code == 200
    body = response.json()
    contribution = body["samples"][0]["contributions"][0]
    assert body["quality"] == "refined"
    assert body["metadata"]["ring_segments"] >= 256
    assert contribution["source_kind"] == "ring"
    assert contribution["metadata"]["method"] == "discrete-ring"
    assert contribution["metadata"]["segments"] == body["metadata"]["ring_segments"]


def test_field_evaluate_rejects_unknown_quality_without_static_fallback():
    request = _single_point_request()
    request["quality"] = "fast-ish"

    response = client.post("/api/field/evaluate", json=request)

    assert response.status_code == 422
    assert "fast-ish" in str(response.json()["detail"])
