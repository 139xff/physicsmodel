from __future__ import annotations

import pytest

from em_workbench.models import Scene
from em_workbench.physics.scattering import (
    AlphaBeam,
    Nucleus,
    rutherford_angle_deg,
    simulate_scattering,
)


def test_rutherford_formula_preserves_impact_parameter_sign() -> None:
    assert rutherford_angle_deg(0.0, 0.008) == 180.0
    assert rutherford_angle_deg(0.02, 0.008) == pytest.approx(22.619864948)
    assert rutherford_angle_deg(-0.02, 0.008) == pytest.approx(-22.619864948)


def test_scattering_tracks_match_rutherford_angles() -> None:
    nucleus = Nucleus(charge_c=1.0e-9)
    beam = AlphaBeam(
        charge_c=1.0e-9,
        mass_kg=1.0e-6,
        speed_m_per_s=1.5,
        start_x_m=-0.5,
        impact_parameters_m=[0.0, 0.02, -0.02],
    )

    result = simulate_scattering(
        nucleus,
        beam,
        dt_s=0.001,
        max_steps=4000,
        record_every=20,
        request_id="scatter-physics-test",
    )

    assert result.request_id == "scatter-physics-test"
    assert result.characteristic_distance_m == pytest.approx(0.0079889349)
    assert len(result.tracks) == 3

    head_on, upper, lower = result.tracks
    assert head_on.impact_parameter_m == 0.0
    assert abs(head_on.scattering_angle_deg) == pytest.approx(180.0, abs=0.2)
    assert head_on.closest_approach_m == pytest.approx(
        result.characteristic_distance_m,
        rel=0.03,
    )

    assert upper.scattering_angle_deg == pytest.approx(upper.rutherford_angle_deg, abs=0.4)
    assert lower.scattering_angle_deg == pytest.approx(lower.rutherford_angle_deg, abs=0.4)
    assert upper.scattering_angle_deg == pytest.approx(-lower.scattering_angle_deg, abs=0.1)
    assert len(upper.samples) > 2


def test_scattering_can_use_integrated_scene_sources() -> None:
    scene = Scene(
        id="ring-scatter-scene",
        title="Ring scatter scene",
        sources=[
            {
                "id": "ring-1",
                "kind": "ring",
                "label": "Ring target",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "radius_m": 0.04,
                "charge_c": 1.0e-9,
            }
        ],
    )
    beam = AlphaBeam(
        charge_c=1.0e-9,
        mass_kg=1.0e-6,
        speed_m_per_s=1.5,
        start_x_m=-0.3,
        impact_parameters_m=[0.03, -0.03],
    )

    result = simulate_scattering(
        None,
        beam,
        scene=scene,
        dt_s=0.001,
        max_steps=800,
        exit_radius_m=0.5,
        record_every=20,
    )

    upper, lower = result.tracks
    assert result.field_model == "scene-sources"
    assert result.characteristic_distance_m == 0.0
    assert upper.rutherford_angle_deg == 0.0
    assert upper.scattering_angle_deg > 0.05
    assert lower.scattering_angle_deg < -0.05
    assert upper.scattering_angle_deg == pytest.approx(-lower.scattering_angle_deg, rel=0.08)
    assert upper.closest_approach_m < abs(beam.start_x_m)


def test_single_point_scene_scattering_uses_rutherford_model() -> None:
    scene = Scene(
        id="point-nucleus-scene",
        title="Point nucleus scene",
        sources=[
            {
                "id": "point-nucleus",
                "kind": "point",
                "label": "Point nucleus",
                "position": {"x": 0.0, "y": 0.01, "z": 0.0, "unit": "m"},
                "charge_c": 1.0e-9,
            }
        ],
    )
    beam = AlphaBeam(
        charge_c=1.0e-9,
        mass_kg=1.0e-6,
        speed_m_per_s=1.5,
        start_x_m=-0.5,
        impact_parameters_m=[0.03, -0.01],
    )

    result = simulate_scattering(
        None,
        beam,
        scene=scene,
        dt_s=0.001,
        max_steps=4000,
        record_every=20,
    )

    upper, lower = result.tracks
    assert result.field_model == "point-nucleus"
    assert result.characteristic_distance_m == pytest.approx(0.0079889349)
    assert upper.rutherford_angle_deg == pytest.approx(rutherford_angle_deg(0.02, 0.0079889349))
    assert lower.rutherford_angle_deg == pytest.approx(rutherford_angle_deg(-0.02, 0.0079889349))
    assert upper.scattering_angle_deg == pytest.approx(upper.rutherford_angle_deg, abs=0.4)
    assert lower.scattering_angle_deg == pytest.approx(lower.rutherford_angle_deg, abs=0.4)


@pytest.mark.parametrize(
    ("source_kind", "source"),
    [
        (
            "point",
            {
                "id": "point-1",
                "kind": "point",
                "label": "Point target",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
                "charge_c": 1.0e-9,
            },
        ),
        (
            "line_segment",
            {
                "id": "line-1",
                "kind": "line_segment",
                "label": "Line target",
                "position": {"x": -0.04, "y": 0.0, "z": 0.0, "unit": "m"},
                "orientation": {"x": 1.0, "y": 0.0, "z": 0.0},
                "length_m": 0.08,
                "charge_c": 1.0e-9,
            },
        ),
        (
            "ring",
            {
                "id": "ring-1",
                "kind": "ring",
                "label": "Ring target",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "radius_m": 0.04,
                "charge_c": 1.0e-9,
            },
        ),
        (
            "disk",
            {
                "id": "disk-1",
                "kind": "disk",
                "label": "Disk target",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "radius_m": 0.04,
                "charge_c": 1.0e-9,
            },
        ),
        (
            "infinite_plane",
            {
                "id": "plane-1",
                "kind": "infinite_plane",
                "label": "Plane target",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
                "normal": {"x": 0.0, "y": 1.0, "z": 0.0},
                "display_extent_m": 0.1,
                "surface_charge_density_c_per_m2": 1.0e-10,
            },
        ),
        (
            "spherical_shell",
            {
                "id": "shell-1",
                "kind": "spherical_shell",
                "label": "Shell target",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0, "unit": "m"},
                "radius_m": 0.04,
                "charge_c": 1.0e-9,
            },
        ),
    ],
)
def test_scene_scattering_accepts_every_source_kind(source_kind: str, source: dict) -> None:
    scene = Scene(
        id=f"{source_kind}-scatter-scene",
        title=f"{source_kind} scatter scene",
        sources=[source],
    )
    beam = AlphaBeam(
        charge_c=1.0e-9,
        mass_kg=1.0e-6,
        speed_m_per_s=1.5,
        start_x_m=-0.3,
        impact_parameters_m=[0.06],
    )

    result = simulate_scattering(
        None,
        beam,
        scene=scene,
        dt_s=0.001,
        max_steps=600,
        exit_radius_m=0.5,
        record_every=20,
    )

    if source_kind == "point":
        assert result.field_model == "point-nucleus"
        assert result.tracks[0].scattering_angle_deg == pytest.approx(
            result.tracks[0].rutherford_angle_deg,
            abs=0.4,
        )
    else:
        assert result.field_model == "scene-sources"
        assert result.tracks[0].scattering_angle_deg > 0.01
    assert result.tracks[0].closest_approach_m < abs(beam.start_x_m)
    assert len(result.tracks[0].samples) > 2
