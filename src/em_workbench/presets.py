"""Editable scene presets for Release 1 electrostatics source contracts."""

from em_workbench.models import Preset, PresetSummary

_PRESET_PAYLOADS = [
    {
        "id": "single-point",
        "title": "Single point charge",
        "description": "One editable point charge at the origin.",
        "scene": {
            "id": "preset-single-point",
            "title": "Single point charge",
            "sources": [
                {
                    "id": "point-origin-positive",
                    "kind": "point",
                    "label": "Positive point charge",
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "charge_c": 1.0e-9,
                }
            ],
        },
    },
    {
        "id": "electric-dipole",
        "title": "Electric dipole",
        "description": "Equal and opposite point charges separated along the x-axis.",
        "scene": {
            "id": "preset-electric-dipole",
            "title": "Electric dipole",
            "sources": [
                {
                    "id": "dipole-positive",
                    "kind": "point",
                    "label": "Positive pole",
                    "position": {"x": -0.05, "y": 0.0, "z": 0.0},
                    "charge_c": 1.0e-9,
                },
                {
                    "id": "dipole-negative",
                    "kind": "point",
                    "label": "Negative pole",
                    "position": {"x": 0.05, "y": 0.0, "z": 0.0},
                    "charge_c": -1.0e-9,
                },
            ],
        },
    },
    {
        "id": "charged-ring-axis",
        "title": "Charged ring axis",
        "description": "A uniformly charged ring with its symmetry axis on z.",
        "scene": {
            "id": "preset-charged-ring-axis",
            "title": "Charged ring axis",
            "sources": [
                {
                    "id": "axis-ring",
                    "kind": "ring",
                    "label": "Uniform charged ring",
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                    "radius_m": 0.12,
                    "charge_c": 4.0e-9,
                }
            ],
        },
    },
    {
        "id": "disk-approaching-plane",
        "title": "Disk approaching plane",
        "description": "A finite display disk near a theoretical infinite charged plane.",
        "scene": {
            "id": "preset-disk-approaching-plane",
            "title": "Disk approaching plane",
            "sources": [
                {
                    "id": "comparison-disk",
                    "kind": "disk",
                    "label": "Uniform charged disk",
                    "position": {"x": 0.0, "y": 0.0, "z": -0.08},
                    "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                    "radius_m": 0.18,
                    "surface_charge_density_c_per_m2": 2.0e-9,
                },
                {
                    "id": "comparison-infinite-plane",
                    "kind": "infinite_plane",
                    "label": "Infinite charged plane",
                    "position": {"x": 0.0, "y": 0.0, "z": 0.12},
                    "normal": {"x": 0.0, "y": 0.0, "z": 1.0},
                    "display_extent_m": 0.6,
                    "surface_charge_density_c_per_m2": 2.0e-9,
                },
            ],
        },
    },
    {
        "id": "spherical-shell-inside-outside",
        "title": "Spherical shell inside/outside",
        "description": "A uniformly charged spherical shell for radial inside/outside exploration.",
        "scene": {
            "id": "preset-spherical-shell-inside-outside",
            "title": "Spherical shell inside/outside",
            "sources": [
                {
                    "id": "uniform-spherical-shell",
                    "kind": "spherical_shell",
                    "label": "Uniform spherical shell",
                    "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                    "radius_m": 0.16,
                    "charge_c": 5.0e-9,
                }
            ],
        },
    },
]

_PRESETS = tuple(Preset.model_validate(payload) for payload in _PRESET_PAYLOADS)


def list_presets() -> list[PresetSummary]:
    """Return stable preset summaries in display order."""
    return [preset.to_summary() for preset in _PRESETS]


def get_preset(preset_id: str) -> Preset:
    """Return a deep copy of an editable preset scene."""
    for preset in _PRESETS:
        if preset.id == preset_id:
            return preset.model_copy(deep=True)
    raise KeyError(preset_id)
