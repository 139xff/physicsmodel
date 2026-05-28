import math

import pytest

from em_workbench.models import Scene
from em_workbench.physics.solver import COULOMB_CONSTANT, evaluate_scene


def _scene(sources: list[dict]) -> Scene:
    return Scene.model_validate(
        {
            "id": "solver-test-scene",
            "title": "Solver test scene",
            "sources": sources,
        }
    )


def _point_source(
    source_id: str,
    charge_c: float,
    position: tuple[float, float, float],
) -> dict:
    return {
        "id": source_id,
        "kind": "point",
        "label": source_id,
        "position": {"x": position[0], "y": position[1], "z": position[2]},
        "charge_c": charge_c,
    }


def test_point_charge_matches_analytic_potential_and_field():
    charge_c = 2.0e-9
    sample = (0.2, 0.0, 0.0)
    scene = _scene([_point_source("q1", charge_c, (0.0, 0.0, 0.0))])

    evaluation = evaluate_scene(scene, [sample], quality="refined")

    result = evaluation.samples[0]
    assert result.potential_v == pytest.approx(COULOMB_CONSTANT * charge_c / 0.2)
    assert result.field_v_per_m.x == pytest.approx(COULOMB_CONSTANT * charge_c / 0.2**2)
    assert result.field_v_per_m.y == pytest.approx(0.0, abs=1.0e-12)
    assert result.field_v_per_m.z == pytest.approx(0.0, abs=1.0e-12)
    assert result.field_magnitude_v_per_m == pytest.approx(abs(result.field_v_per_m.x))
    assert [contribution.source_id for contribution in result.contributions] == ["q1"]
    assert result.contributions[0].source_kind == "point"


def test_multiple_point_charges_superpose_potential_and_field():
    scene = _scene(
        [
            _point_source("positive", 1.0e-9, (0.0, 0.0, 0.0)),
            _point_source("negative", -2.0e-9, (0.1, 0.0, 0.0)),
        ]
    )

    evaluation = evaluate_scene(scene, [(0.3, 0.0, 0.0)], quality="refined")

    result = evaluation.samples[0]
    expected_potential = COULOMB_CONSTANT * (1.0e-9 / 0.3 - 2.0e-9 / 0.2)
    expected_field_x = COULOMB_CONSTANT * (1.0e-9 / 0.3**2 - 2.0e-9 / 0.2**2)
    assert result.potential_v == pytest.approx(expected_potential)
    assert result.field_v_per_m.x == pytest.approx(expected_field_x)
    assert len(result.contributions) == 2


def test_opposite_symmetric_point_charges_cancel_midpoint_potential_and_push_field_positive_x():
    separation_m = 0.05
    charge_c = 1.0e-9
    scene = _scene(
        [
            _point_source("left-positive", charge_c, (-separation_m, 0.0, 0.0)),
            _point_source("right-negative", -charge_c, (separation_m, 0.0, 0.0)),
        ]
    )

    evaluation = evaluate_scene(scene, [(0.0, 0.0, 0.0)], quality="refined")

    result = evaluation.samples[0]
    assert result.potential_v == pytest.approx(0.0, abs=1.0e-12)
    expected_field_x = 2 * COULOMB_CONSTANT * charge_c / separation_m**2
    assert result.field_v_per_m.x == pytest.approx(expected_field_x)
    assert result.field_v_per_m.x > 0.0
    assert result.field_v_per_m.y == pytest.approx(0.0, abs=1.0e-12)
    assert result.field_v_per_m.z == pytest.approx(0.0, abs=1.0e-12)


def test_ring_on_axis_matches_analytic_potential_and_field():
    radius_m = 0.12
    charge_c = 4.0e-9
    axis_z_m = 0.2
    scene = _scene(
        [
            {
                "id": "axis-ring",
                "kind": "ring",
                "label": "Axis ring",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "radius_m": radius_m,
                "charge_c": charge_c,
            }
        ]
    )

    evaluation = evaluate_scene(scene, [(0.0, 0.0, axis_z_m)], quality="refined")

    result = evaluation.samples[0]
    distance = math.sqrt(radius_m**2 + axis_z_m**2)
    expected_potential = COULOMB_CONSTANT * charge_c / distance
    expected_field_z = COULOMB_CONSTANT * charge_c * axis_z_m / distance**3
    assert result.potential_v == pytest.approx(expected_potential, rel=1.0e-6)
    assert result.field_v_per_m.z == pytest.approx(expected_field_z, rel=1.0e-6)
    assert result.field_v_per_m.x == pytest.approx(0.0, abs=1.0e-9)
    assert result.field_v_per_m.y == pytest.approx(0.0, abs=1.0e-9)
    assert result.contributions[0].metadata["method"] == "discrete-ring"


def test_arbitrary_orientation_ring_is_rotation_equivalent_on_its_axis():
    radius_m = 0.1
    charge_c = 3.0e-9
    axis_distance_m = 0.18
    normal_length = math.sqrt(1.0**2 + 2.0**2 + 3.0**2)
    normal = (1.0 / normal_length, 2.0 / normal_length, 3.0 / normal_length)
    sample = tuple(axis_distance_m * component for component in normal)
    scene = _scene(
        [
            {
                "id": "tilted-ring",
                "kind": "ring",
                "label": "Tilted ring",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "normal": {"x": 1.0, "y": 2.0, "z": 3.0},
                "radius_m": radius_m,
                "charge_c": charge_c,
            }
        ]
    )

    evaluation = evaluate_scene(scene, [sample], quality="refined")

    result = evaluation.samples[0]
    axis_distance = math.sqrt(radius_m**2 + axis_distance_m**2)
    expected_potential = COULOMB_CONSTANT * charge_c / axis_distance
    expected_axis_field = COULOMB_CONSTANT * charge_c * axis_distance_m / axis_distance**3
    assert result.potential_v == pytest.approx(expected_potential, rel=1.0e-6)
    assert result.field_v_per_m.x == pytest.approx(expected_axis_field * normal[0], rel=1.0e-6)
    assert result.field_v_per_m.y == pytest.approx(expected_axis_field * normal[1], rel=1.0e-6)
    assert result.field_v_per_m.z == pytest.approx(expected_axis_field * normal[2], rel=1.0e-6)


def test_near_point_charge_singularity_is_bounded_and_warned():
    scene = _scene([_point_source("singular-point", 1.0e-9, (0.0, 0.0, 0.0))])

    evaluation = evaluate_scene(scene, [(0.0, 0.0, 0.0)], quality="refined")

    result = evaluation.samples[0]
    assert math.isfinite(result.potential_v)
    assert math.isfinite(result.field_magnitude_v_per_m)
    assert result.potential_v == 0.0
    assert result.field_magnitude_v_per_m == 0.0
    assert any("singular" in warning.lower() for warning in result.warnings)
    assert any("singular" in warning.lower() for warning in result.contributions[0].warnings)


def test_preview_and_refined_ring_modes_report_quality_metadata():
    ring_source = {
        "id": "quality-ring",
        "kind": "ring",
        "label": "Quality ring",
        "position": {"x": 0.0, "y": 0.0, "z": 0.0},
        "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
        "radius_m": 0.1,
        "charge_c": 2.0e-9,
    }
    scene = _scene([ring_source])

    preview = evaluate_scene(scene, [(0.04, 0.02, 0.11)], quality="preview")
    refined = evaluate_scene(scene, [(0.04, 0.02, 0.11)], quality="refined")

    assert preview.quality == "preview"
    assert refined.quality == "refined"
    assert preview.result_version == refined.result_version
    assert preview.metadata["ring_segments"] < refined.metadata["ring_segments"]
    assert (
        preview.samples[0].contributions[0].metadata["segments"]
        == preview.metadata["ring_segments"]
    )
    assert (
        refined.samples[0].contributions[0].metadata["segments"]
        == refined.metadata["ring_segments"]
    )


def test_all_release_one_sources_are_reported_with_contributions_or_limitations():
    scene = _scene(
        [
            _point_source("point", 1.0e-9, (0.0, 0.0, 0.0)),
            {
                "id": "line",
                "kind": "line_segment",
                "label": "Line",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "orientation": {"x": 0.0, "y": 0.0, "z": 1.0},
                "length_m": 0.2,
                "charge_c": 1.0e-9,
            },
            {
                "id": "ring",
                "kind": "ring",
                "label": "Ring",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "normal": {"x": 0.0, "y": 1.0, "z": 0.0},
                "radius_m": 0.1,
                "charge_c": 1.0e-9,
            },
            {
                "id": "disk",
                "kind": "disk",
                "label": "Disk",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "normal": {"x": 1.0, "y": 0.0, "z": 0.0},
                "radius_m": 0.15,
                "surface_charge_density_c_per_m2": 2.0e-9,
            },
            {
                "id": "plane",
                "kind": "infinite_plane",
                "label": "Plane",
                "position": {"x": 0.0, "y": 0.0, "z": -0.2},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "display_extent_m": 1.0,
                "surface_charge_density_c_per_m2": 1.0e-9,
            },
            {
                "id": "shell",
                "kind": "spherical_shell",
                "label": "Shell",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "radius_m": 0.1,
                "charge_c": 1.0e-9,
            },
        ]
    )

    evaluation = evaluate_scene(scene, [(0.3, 0.1, 0.2)], quality="preview")

    result = evaluation.samples[0]
    assert [contribution.source_id for contribution in result.contributions] == [
        "point",
        "line",
        "ring",
        "disk",
        "plane",
        "shell",
    ]
    assert all(math.isfinite(contribution.potential_v) for contribution in result.contributions)
    assert any("numerical approximation" in warning.lower() for warning in result.warnings)
