from __future__ import annotations

import pytest

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
