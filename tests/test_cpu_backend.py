import numpy as np
import pytest

from em_workbench.models import Position, Scene
from em_workbench.physics.compute.cpu_backend import (
    evaluate_contributions_cpu,
    evaluate_totals_cpu,
)
from em_workbench.physics.compute.packed_scene import compile_scene
from em_workbench.physics.solver import evaluate_scene_scalar


def _points_array(sample_points: list[Position], dtype: np.dtype) -> np.ndarray:
    return np.asarray([[point.x, point.y, point.z] for point in sample_points], dtype=dtype)


@pytest.mark.parametrize("quality,rtol", [("preview", 2e-5), ("refined", 1e-10)])
def test_cpu_totals_match_scalar_reference(
    representative_scene: Scene,
    sample_points: list[Position],
    quality: str,
    rtol: float,
) -> None:
    packed = compile_scene(representative_scene, quality=quality)
    points = _points_array(sample_points, packed.dtype)

    potential, field = evaluate_totals_cpu(packed, points)
    scalar = evaluate_scene_scalar(representative_scene, sample_points, quality=quality)

    assert potential == pytest.approx(
        [sample.potential_v for sample in scalar.samples],
        rel=rtol,
    )
    np.testing.assert_allclose(
        field,
        np.asarray(
            [
            [sample.field_v_per_m.x, sample.field_v_per_m.y, sample.field_v_per_m.z]
            for sample in scalar.samples
            ]
        ),
        rtol=rtol,
        atol=1e-7,
    )


def test_cpu_contributions_sum_to_cpu_totals(
    representative_scene: Scene,
    sample_points: list[Position],
) -> None:
    packed = compile_scene(representative_scene, quality="preview")
    points = _points_array(sample_points, packed.dtype)

    potential, field = evaluate_totals_cpu(packed, points)
    contributions = evaluate_contributions_cpu(packed, points)

    assert contributions.shape == (len(sample_points), len(representative_scene.sources), 4)
    assert contributions[:, :, 0].sum(axis=1) == pytest.approx(potential, rel=2e-5)
    assert contributions[:, :, 1:4].sum(axis=1) == pytest.approx(field, rel=2e-5, abs=1e-7)


@pytest.mark.parametrize(
    "source,sample",
    [
        (
            {
                "id": "point",
                "kind": "point",
                "label": "point",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "charge_c": 1e-9,
            },
            Position(x=0.2, y=0.1, z=0.05),
        ),
        (
            {
                "id": "line",
                "kind": "line_segment",
                "label": "line",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "orientation": {"x": 1.0, "y": 0.0, "z": 0.0},
                "length_m": 0.2,
                "charge_c": 2e-9,
            },
            Position(x=0.2, y=0.1, z=0.05),
        ),
        (
            {
                "id": "ring",
                "kind": "ring",
                "label": "ring",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "radius_m": 0.12,
                "charge_c": 3e-9,
            },
            Position(x=0.2, y=0.1, z=0.05),
        ),
        (
            {
                "id": "disk",
                "kind": "disk",
                "label": "disk",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "radius_m": 0.12,
                "charge_c": 4e-9,
            },
            Position(x=0.2, y=0.1, z=0.05),
        ),
        (
            {
                "id": "plane",
                "kind": "infinite_plane",
                "label": "plane",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "display_extent_m": 1.0,
                "surface_charge_density_c_per_m2": 5e-9,
            },
            Position(x=0.2, y=0.1, z=0.05),
        ),
        (
            {
                "id": "shell",
                "kind": "spherical_shell",
                "label": "shell",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "radius_m": 0.12,
                "charge_c": 6e-9,
            },
            Position(x=0.2, y=0.1, z=0.05),
        ),
    ],
)
def test_cpu_totals_match_scalar_for_each_source_kind(source: dict, sample: Position) -> None:
    scene = Scene.model_validate(
        {
            "id": f"cpu-{source['id']}",
            "title": f"CPU {source['id']}",
            "sources": [source],
        }
    )
    packed = compile_scene(scene, quality="refined")
    points = _points_array([sample], packed.dtype)

    potential, field = evaluate_totals_cpu(packed, points)
    scalar = evaluate_scene_scalar(scene, [sample], quality="refined").samples[0]

    assert potential == pytest.approx([scalar.potential_v], rel=1e-10)
    np.testing.assert_allclose(
        field,
        [[scalar.field_v_per_m.x, scalar.field_v_per_m.y, scalar.field_v_per_m.z]],
        rtol=1e-10,
        atol=1e-9,
    )
