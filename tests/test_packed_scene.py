import numpy as np

from em_workbench.models import Scene
from em_workbench.physics.compute.packed_scene import PackedSceneCache, compile_scene


def _scene(scene_id: str = "packed-scene") -> Scene:
    return Scene.model_validate(
        {
            "id": scene_id,
            "title": "Packed scene",
            "sources": [
                {
                    "id": "q",
                    "kind": "point",
                    "label": "q",
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "charge_c": 1e-9,
                },
                {
                    "id": "line",
                    "kind": "line_segment",
                    "label": "line",
                    "position": {"x": 0.0, "y": 0.1, "z": 0.0},
                    "orientation": {"x": 1.0, "y": 0.0, "z": 0.0},
                    "length_m": 0.2,
                    "charge_c": 2e-9,
                },
            ],
        }
    )


def _all_source_kinds_scene() -> Scene:
    return Scene.model_validate(
        {
            "id": "packed-all-kinds",
            "title": "Packed all kinds",
            "sources": [
                {
                    "id": "q",
                    "kind": "point",
                    "label": "q",
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "charge_c": 1e-9,
                },
                {
                    "id": "line",
                    "kind": "line_segment",
                    "label": "line",
                    "position": {"x": 0.0, "y": 0.1, "z": 0.0},
                    "orientation": {"x": 1.0, "y": 0.0, "z": 0.0},
                    "length_m": 0.2,
                    "charge_c": 2e-9,
                },
                {
                    "id": "ring",
                    "kind": "ring",
                    "label": "ring",
                    "position": {"x": 0.0, "y": 0.0, "z": 0.1},
                    "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                    "radius_m": 0.12,
                    "charge_c": 3e-9,
                },
                {
                    "id": "disk",
                    "kind": "disk",
                    "label": "disk",
                    "position": {"x": 0.0, "y": 0.0, "z": -0.1},
                    "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                    "radius_m": 0.18,
                    "charge_c": 4e-9,
                },
                {
                    "id": "plane",
                    "kind": "infinite_plane",
                    "label": "plane",
                    "position": {"x": 0.0, "y": 0.0, "z": 0.2},
                    "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                    "display_extent_m": 0.6,
                    "surface_charge_density_c_per_m2": 5e-9,
                },
                {
                    "id": "shell",
                    "kind": "spherical_shell",
                    "label": "shell",
                    "position": {"x": 0.0, "y": 0.0, "z": -0.2},
                    "radius_m": 0.16,
                    "charge_c": 6e-9,
                },
            ],
        }
    )


def test_compile_scene_uses_preview_float32_and_owner_indexes() -> None:
    packed = compile_scene(_scene(), quality="preview")

    assert packed.dtype == np.dtype(np.float32)
    assert packed.element_positions.shape == (49, 3)
    assert packed.element_charges.shape == (49,)
    assert packed.element_source_indexes.tolist() == [0] + [1] * 48
    assert packed.source_ids == ("q", "line")
    assert not packed.element_positions.flags.writeable


def test_compile_scene_packs_discrete_and_analytic_sources() -> None:
    packed = compile_scene(_all_source_kinds_scene(), quality="preview")

    assert packed.element_positions.shape == (497, 3)
    assert packed.element_source_indexes.tolist() == (
        [0] + [1] * 48 + [2] * 64 + [3] * (8 * 48)
    )
    assert packed.plane_positions.shape == (1, 3)
    assert packed.plane_normals.tolist() == [[0.0, 0.0, 1.0]]
    assert packed.plane_densities.tolist() == [np.float32(5e-9)]
    assert packed.plane_source_indexes.tolist() == [4]
    assert packed.shell_positions.shape == (1, 3)
    assert packed.shell_radii.tolist() == [np.float32(0.16)]
    assert packed.shell_charges.tolist() == [np.float32(6e-9)]
    assert packed.shell_source_indexes.tolist() == [5]
    assert np.isclose(packed.element_charges.sum(), 10e-9)
    assert not packed.plane_positions.flags.writeable
    assert not packed.shell_positions.flags.writeable


def test_compile_scene_uses_refined_float64() -> None:
    packed = compile_scene(_scene(), quality="refined")

    assert packed.dtype == np.dtype(np.float64)
    assert packed.element_positions.shape == (257, 3)


def test_cache_returns_same_immutable_scene_for_same_key() -> None:
    cache = PackedSceneCache(limit=2)

    first, first_hit = cache.get_or_compile(_scene(), quality="refined")
    second, second_hit = cache.get_or_compile(_scene(), quality="refined")

    assert first_hit is False
    assert second_hit is True
    assert second is first


def test_cache_evicts_least_recently_used_scene() -> None:
    cache = PackedSceneCache(limit=2)

    first, _hit = cache.get_or_compile(_scene("first"), quality="preview")
    cache.get_or_compile(_scene("second"), quality="preview")
    cache.get_or_compile(_scene("third"), quality="preview")
    recompiled, hit = cache.get_or_compile(_scene("first"), quality="preview")

    assert len(cache) == 2
    assert hit is False
    assert recompiled is not first
