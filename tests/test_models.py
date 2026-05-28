import math
import sys

import pytest
from pydantic import TypeAdapter, ValidationError

from em_workbench.models import (
    ElectrostaticSource,
    InfinitePlaneSource,
    LineSegmentSource,
    RingSource,
    Scene,
)
from em_workbench.presets import get_preset, list_presets


def _six_source_scene() -> dict:
    return {
        "id": "scene-six-source-contract",
        "title": "Six source contract",
        "sources": [
            {
                "id": "point-1",
                "kind": "point",
                "label": "Point charge",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "charge_c": 1.2e-9,
            },
            {
                "id": "line-1",
                "kind": "line_segment",
                "label": "Uniform line segment",
                "position": {"x": 0.0, "y": 0.0, "z": 0.1},
                "orientation": {"x": 0.0, "y": 0.0, "z": 2.0},
                "length_m": 0.25,
                "linear_charge_density_c_per_m": -4.0e-9,
            },
            {
                "id": "ring-1",
                "kind": "ring",
                "label": "Charged ring",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "normal": {"x": 0.0, "y": 0.0, "z": 3.0},
                "radius_m": 0.1,
                "charge_c": 2.4e-9,
            },
            {
                "id": "disk-1",
                "kind": "disk",
                "label": "Charged disk",
                "position": {"x": 0.0, "y": 0.0, "z": -0.2},
                "normal": {"x": 0.0, "y": 4.0, "z": 0.0},
                "radius_m": 0.2,
                "surface_charge_density_c_per_m2": 6.0e-9,
            },
            {
                "id": "plane-1",
                "kind": "infinite_plane",
                "label": "Infinite plane",
                "position": {"x": 0.0, "y": 0.0, "z": -0.3},
                "normal": {"x": 5.0, "y": 0.0, "z": 0.0},
                "display_extent_m": 0.75,
                "surface_charge_density_c_per_m2": -1.0e-9,
            },
            {
                "id": "shell-1",
                "kind": "spherical_shell",
                "label": "Spherical shell",
                "position": {"x": 0.0, "y": 0.0, "z": 0.4},
                "radius_m": 0.15,
                "charge_c": 3.0e-9,
            },
        ],
    }


def test_scene_accepts_all_release_one_source_kinds_and_serializes_discriminator():
    scene = Scene.model_validate(_six_source_scene())

    assert [source.kind for source in scene.sources] == [
        "point",
        "line_segment",
        "ring",
        "disk",
        "infinite_plane",
        "spherical_shell",
    ]
    assert scene.sources[0].position.unit == "m"
    assert isinstance(scene.sources[1], LineSegmentSource)
    assert scene.sources[1].orientation.model_dump() == {"x": 0.0, "y": 0.0, "z": 1.0}
    assert isinstance(scene.sources[2], RingSource)
    assert scene.sources[2].normal.model_dump() == {"x": 0.0, "y": 0.0, "z": 1.0}
    assert isinstance(scene.sources[4], InfinitePlaneSource)
    assert scene.sources[4].normal.model_dump() == {"x": 1.0, "y": 0.0, "z": 0.0}

    serialized = scene.model_dump(mode="json")
    assert serialized["schema_version"] == 1
    assert serialized["sources"][0]["kind"] == "point"
    assert serialized["sources"][0]["position"] == {
        "x": 0.0,
        "y": 0.0,
        "z": 0.0,
        "unit": "m",
    }
    assert serialized["sources"][1]["orientation"] == {"x": 0.0, "y": 0.0, "z": 1.0}

    round_tripped = Scene.model_validate_json(scene.model_dump_json())
    assert [source.id for source in round_tripped.sources] == [
        "point-1",
        "line-1",
        "ring-1",
        "disk-1",
        "plane-1",
        "shell-1",
    ]


@pytest.mark.parametrize(
    ("source", "expected_message"),
    [
        (
            {
                "id": "line-missing-charge",
                "kind": "line_segment",
                "label": "Missing line charge",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "orientation": {"x": 1.0, "y": 0.0, "z": 0.0},
                "length_m": 0.5,
            },
            "exactly one",
        ),
        (
            {
                "id": "ring-conflicting-charge",
                "kind": "ring",
                "label": "Conflicting ring charge",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "radius_m": 0.25,
                "charge_c": 1.0e-9,
                "linear_charge_density_c_per_m": 2.0e-9,
            },
            "exactly one",
        ),
        (
            {
                "id": "disk-conflicting-charge",
                "kind": "disk",
                "label": "Conflicting disk charge",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "normal": {"x": 0.0, "y": 1.0, "z": 0.0},
                "radius_m": 0.25,
                "charge_c": 1.0e-9,
                "surface_charge_density_c_per_m2": 2.0e-9,
            },
            "exactly one",
        ),
        (
            {
                "id": "shell-missing-charge",
                "kind": "spherical_shell",
                "label": "Missing shell charge",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "radius_m": 0.25,
            },
            "exactly one",
        ),
        (
            {
                "id": "plane-with-total-charge",
                "kind": "infinite_plane",
                "label": "Impossible finite total charge",
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                "display_extent_m": 0.5,
                "surface_charge_density_c_per_m2": 2.0e-9,
                "charge_c": 1.0e-9,
            },
            "Extra inputs",
        ),
    ],
)
def test_sources_reject_missing_or_conflicting_total_charge_and_density_inputs(
    source: dict, expected_message: str
):
    adapter = TypeAdapter(ElectrostaticSource)

    with pytest.raises(ValidationError, match=expected_message):
        adapter.validate_python(source)


@pytest.mark.parametrize(
    "source",
    [
        {
            "id": "line-zero-orientation",
            "kind": "line_segment",
            "label": "Zero orientation",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 0.0},
            "length_m": 0.5,
            "charge_c": 1.0e-9,
        },
        {
            "id": "ring-negative-radius",
            "kind": "ring",
            "label": "Negative radius",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
            "radius_m": -0.25,
            "charge_c": 1.0e-9,
        },
        {
            "id": "plane-zero-display-extent",
            "kind": "infinite_plane",
            "label": "Zero display extent",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "normal": {"x": 0.0, "y": 1.0, "z": 0.0},
            "display_extent_m": 0.0,
            "surface_charge_density_c_per_m2": 1.0e-9,
        },
        {
            "id": "point-non-finite-charge",
            "kind": "point",
            "label": "Non-finite charge",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "charge_c": math.inf,
        },
    ],
)
def test_sources_validate_finite_si_values_positive_dimensions_and_nonzero_directions(
    source: dict,
):
    adapter = TypeAdapter(ElectrostaticSource)

    with pytest.raises(ValidationError):
        adapter.validate_python(source)


@pytest.mark.parametrize(
    "source",
    [
        {
            "id": "line-huge-orientation",
            "kind": "line_segment",
            "label": "Huge finite orientation",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "orientation": {"x": 1e308, "y": 1e308, "z": 0.0},
            "length_m": 1.0,
            "charge_c": 1.0,
        },
        {
            "id": "ring-huge-normal",
            "kind": "ring",
            "label": "Huge finite normal",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "normal": {"x": 0.0, "y": -1e308, "z": 1e308},
            "radius_m": 1.0,
            "charge_c": 1.0,
        },
    ],
)
def test_huge_finite_direction_vectors_normalize_without_collapsing_to_zero(source: dict):
    adapter = TypeAdapter(ElectrostaticSource)

    validated = adapter.validate_python(source)
    vector = validated.orientation if isinstance(validated, LineSegmentSource) else validated.normal
    magnitude = math.hypot(vector.x, vector.y, vector.z)

    assert magnitude == pytest.approx(1.0)
    assert any(component != 0.0 for component in (vector.x, vector.y, vector.z))


@pytest.mark.parametrize(
    "source",
    [
        {
            "id": "line-max-float-orientation",
            "kind": "line_segment",
            "label": "Max finite orientation",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "orientation": {"x": sys.float_info.max, "y": sys.float_info.max, "z": 0.0},
            "length_m": 1.0,
            "charge_c": 1.0,
        },
        {
            "id": "ring-max-float-normal",
            "kind": "ring",
            "label": "Max finite normal",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "normal": {"x": 0.0, "y": -sys.float_info.max, "z": sys.float_info.max},
            "radius_m": 1.0,
            "charge_c": 1.0,
        },
    ],
)
def test_max_finite_direction_vectors_normalize_without_overflow_rejection(source: dict):
    adapter = TypeAdapter(ElectrostaticSource)

    validated = adapter.validate_python(source)
    vector = validated.orientation if isinstance(validated, LineSegmentSource) else validated.normal
    components = (vector.x, vector.y, vector.z)

    assert all(math.isfinite(component) for component in components)
    assert math.hypot(*components) == pytest.approx(1.0)
    assert any(component != 0.0 for component in components)


@pytest.mark.parametrize(
    "source",
    [
        {
            "id": "point-position-string",
            "kind": "point",
            "label": "String position",
            "position": {"x": "0.0", "y": 0.0, "z": 0.0},
            "charge_c": 1.0e-9,
        },
        {
            "id": "point-position-bool",
            "kind": "point",
            "label": "Bool position",
            "position": {"x": True, "y": 0.0, "z": 0.0},
            "charge_c": 1.0e-9,
        },
        {
            "id": "point-charge-string",
            "kind": "point",
            "label": "String charge",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "charge_c": "1e-9",
        },
        {
            "id": "point-charge-bool",
            "kind": "point",
            "label": "Bool charge",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "charge_c": True,
        },
        {
            "id": "line-dimension-string",
            "kind": "line_segment",
            "label": "String length",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 1.0},
            "length_m": "1.0",
            "charge_c": 1.0e-9,
        },
        {
            "id": "line-dimension-bool",
            "kind": "line_segment",
            "label": "Bool length",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "orientation": {"x": 0.0, "y": 0.0, "z": 1.0},
            "length_m": True,
            "charge_c": 1.0e-9,
        },
        {
            "id": "plane-density-string",
            "kind": "infinite_plane",
            "label": "String density",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
            "display_extent_m": 1.0,
            "surface_charge_density_c_per_m2": "1e-9",
        },
        {
            "id": "plane-density-bool",
            "kind": "infinite_plane",
            "label": "Bool density",
            "position": {"x": 0.0, "y": 0.0, "z": 0.0},
            "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
            "display_extent_m": 1.0,
            "surface_charge_density_c_per_m2": False,
        },
    ],
)
def test_si_numeric_fields_reject_bool_and_string_coercion(source: dict):
    adapter = TypeAdapter(ElectrostaticSource)

    with pytest.raises(ValidationError):
        adapter.validate_python(source)


def test_si_numeric_fields_accept_integer_json_numbers_without_string_coercion():
    source = {
        "id": "line-integer-json-numbers",
        "kind": "line_segment",
        "label": "Integer JSON values",
        "position": {"x": 0, "y": 0, "z": 0},
        "orientation": {"x": 0, "y": 0, "z": 2},
        "length_m": 1,
        "charge_c": 1,
    }

    validated = TypeAdapter(ElectrostaticSource).validate_python(source)

    assert isinstance(validated, LineSegmentSource)
    assert validated.position.x == 0.0
    assert validated.length_m == 1.0
    assert validated.charge_c == 1.0
    assert validated.orientation.model_dump() == {"x": 0.0, "y": 0.0, "z": 1.0}


def test_scene_rejects_duplicate_source_ids():
    scene = _six_source_scene()
    scene["sources"][1]["id"] = scene["sources"][0]["id"]

    with pytest.raises(ValidationError, match="Duplicate source id"):
        Scene.model_validate(scene)


def test_presets_are_stable_editable_scene_json_with_required_release_one_cases():
    summaries = list_presets()

    assert [summary.id for summary in summaries] == [
        "single-point",
        "electric-dipole",
        "charged-ring-axis",
        "disk-approaching-plane",
        "spherical-shell-inside-outside",
    ]
    assert summaries[0].source_count == 1
    assert summaries[3].source_kinds == ["disk", "infinite_plane"]

    preset = get_preset("charged-ring-axis")
    editable_scene_json = preset.scene.model_dump(mode="json")
    editable_scene_json["sources"].append(
        {
            "id": "student-extra-point",
            "kind": "point",
            "label": "Student extra point",
            "position": {"x": 0.2, "y": 0.0, "z": 0.0},
            "charge_c": -1.0e-9,
        }
    )

    edited_scene = Scene.model_validate(editable_scene_json)
    assert edited_scene.sources[-1].id == "student-extra-point"
