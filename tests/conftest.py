import pytest

from em_workbench.models import Position, Scene
from em_workbench.physics.dynamics import TestCharge


@pytest.fixture
def representative_scene() -> Scene:
    return Scene.model_validate(
        {
            "id": "representative",
            "title": "Representative compute scene",
            "sources": [
                {
                    "id": "q1",
                    "kind": "point",
                    "label": "q1",
                    "position": {"x": -0.08, "y": 0.0, "z": 0.0},
                    "charge_c": 2e-9,
                },
                {
                    "id": "q2",
                    "kind": "point",
                    "label": "q2",
                    "position": {"x": 0.08, "y": 0.0, "z": 0.0},
                    "charge_c": -2e-9,
                },
                {
                    "id": "line",
                    "kind": "line_segment",
                    "label": "line",
                    "position": {"x": 0.0, "y": -0.12, "z": 0.0},
                    "orientation": {"x": 1.0, "y": 0.0, "z": 0.0},
                    "length_m": 0.18,
                    "charge_c": 1.5e-9,
                },
                {
                    "id": "ring",
                    "kind": "ring",
                    "label": "ring",
                    "position": {"x": 0.0, "y": 0.1, "z": 0.0},
                    "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                    "radius_m": 0.06,
                    "charge_c": -1.2e-9,
                },
                {
                    "id": "disk",
                    "kind": "disk",
                    "label": "disk",
                    "position": {"x": 0.0, "y": 0.0, "z": -0.08},
                    "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                    "radius_m": 0.08,
                    "charge_c": 1e-9,
                },
            ],
        }
    )


@pytest.fixture
def sample_points() -> list[Position]:
    return [
        Position(x=-0.20, y=-0.15, z=0.04),
        Position(x=0.00, y=0.00, z=0.04),
        Position(x=0.22, y=0.18, z=0.04),
    ]


@pytest.fixture
def particle() -> TestCharge:
    return TestCharge.model_validate(
        {
            "charge_c": -1e-9,
            "mass_kg": 6e-6,
            "position": {"x": -0.08, "y": 0.04, "z": 0.0},
            "velocity": {"x": 0.06, "y": 0.0, "z": 0.0},
        }
    )
