"""Fetch and verify pinned Three.js browser modules for offline application serving."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
VENDOR_ROOT = PROJECT_ROOT / "web" / "vendor"
MANIFEST_PATH = VENDOR_ROOT / "manifest.json"
VERSION = "0.180.0"
CDN_BASE = f"https://cdn.jsdelivr.net/npm/three@{VERSION}"


@dataclass(frozen=True)
class VendorAsset:
    """One pinned upstream file copied into the local browser runtime."""

    identifier: str
    local_name: str
    source_url: str
    sha256: str

    @property
    def path(self) -> Path:
        return VENDOR_ROOT / self.local_name

    @property
    def manifest_path(self) -> str:
        return f"web/vendor/{self.local_name}"


MODULES = (
    VendorAsset(
        identifier="three",
        local_name="three.module.js",
        source_url=f"{CDN_BASE}/build/three.module.js",
        sha256="c8211c69345d2e9949dc7a8ac969380497aa0600a5a8ac6a459c8cd02dd9cb8a",
    ),
    VendorAsset(
        identifier="three-core",
        local_name="three.core.js",
        source_url=f"{CDN_BASE}/build/three.core.js",
        sha256="eb077d2417f61d3e6d9264c317cabc4ea35769ed6b0ab533067292a550784c20",
    ),
    VendorAsset(
        identifier="orbit-controls",
        local_name="OrbitControls.js",
        source_url=f"{CDN_BASE}/examples/jsm/controls/OrbitControls.js",
        sha256="b97879c748170baadeb3fb84cea1ffdf4674e283dc06042f34e2acb95a76042c",
    ),
)
LICENSE = VendorAsset(
    identifier="license",
    local_name="LICENSE.three.txt",
    source_url=f"{CDN_BASE}/LICENSE",
    sha256="bfe119ea4fd413f5f7ca3fcd63adb0c4a073ed39daa2fe7d3e6b769e21272601",
)


def _digest(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


def _verify_digest(asset: VendorAsset, contents: bytes, source: str) -> None:
    actual_digest = _digest(contents)
    if actual_digest != asset.sha256:
        raise ValueError(
            f"SHA-256 mismatch for {asset.local_name} from {source}: "
            f"expected {asset.sha256}, got {actual_digest}."
        )


def _obtain_asset(asset: VendorAsset, *, download_missing: bool) -> str:
    if asset.path.exists():
        _verify_digest(asset, asset.path.read_bytes(), "local vendor directory")
        return "verified"
    if not download_missing:
        raise FileNotFoundError(
            f"Missing local vendor asset {asset.path}. Run this script without --verify first."
        )

    with urllib.request.urlopen(asset.source_url, timeout=30) as response:
        contents = response.read()
    _verify_digest(asset, contents, asset.source_url)
    asset.path.write_bytes(contents)
    return "downloaded"


def _manifest() -> dict[str, object]:
    return {
        "schema_version": 1,
        "runtime": "Three.js browser ES modules",
        "version": VERSION,
        "license": {
            "spdx": "MIT",
            "name": "MIT License",
            "source_url": LICENSE.source_url,
            "local_path": LICENSE.manifest_path,
            "sha256": LICENSE.sha256,
        },
        "modules": [
            {
                "id": module.identifier,
                "source_url": module.source_url,
                "local_path": module.manifest_path,
                "sha256": module.sha256,
                "license": {"spdx": "MIT", "source": "license"},
            }
            for module in MODULES
        ],
    }


def _write_or_verify_manifest(*, write: bool) -> None:
    expected = _manifest()
    if write:
        MANIFEST_PATH.write_text(
            json.dumps(expected, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
        return
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(f"Missing local vendor manifest {MANIFEST_PATH}.")
    actual = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if actual != expected:
        raise ValueError("Vendor manifest does not match the pinned script contract.")


def vendor_runtime(*, verify_only: bool) -> None:
    """Obtain missing assets, or verify a complete existing local runtime."""
    if not verify_only:
        VENDOR_ROOT.mkdir(parents=True, exist_ok=True)

    results = [
        _obtain_asset(asset, download_missing=not verify_only) for asset in (*MODULES, LICENSE)
    ]
    _write_or_verify_manifest(write=not verify_only)

    if verify_only:
        print(
            f"Verified Three.js {VERSION} vendor assets "
            f"({len(MODULES)} modules and MIT license)."
        )
        return
    downloaded = results.count("downloaded")
    print(
        f"Vendored Three.js {VERSION}: downloaded {downloaded} asset(s), "
        f"verified {len(results)} asset(s), wrote web/vendor/manifest.json."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify local files and manifest only; do not request upstream URLs.",
    )
    args = parser.parse_args(argv)
    try:
        vendor_runtime(verify_only=args.verify)
    except (FileNotFoundError, OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Vendor runtime validation failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
