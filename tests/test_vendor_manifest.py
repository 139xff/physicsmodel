import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
VENDOR_ROOT = PROJECT_ROOT / "web" / "vendor"
MANIFEST_PATH = VENDOR_ROOT / "manifest.json"
PINNED_VERSION = "0.180.0"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_manifest_pins_module_sources_hashes_and_mit_license():
    manifest = _manifest()

    assert manifest["schema_version"] == 1
    assert manifest["runtime"] == "Three.js browser ES modules"
    assert manifest["version"] == PINNED_VERSION
    assert manifest["license"] == {
        "spdx": "MIT",
        "name": "MIT License",
        "source_url": f"https://cdn.jsdelivr.net/npm/three@{PINNED_VERSION}/LICENSE",
        "local_path": "web/vendor/LICENSE.three.txt",
        "sha256": _sha256(VENDOR_ROOT / "LICENSE.three.txt"),
    }

    modules = {module["id"]: module for module in manifest["modules"]}
    assert set(modules) == {"three", "orbit-controls"}
    assert modules["three"]["source_url"] == (
        f"https://cdn.jsdelivr.net/npm/three@{PINNED_VERSION}/build/three.module.js"
    )
    assert modules["three"]["local_path"] == "web/vendor/three.module.js"
    assert modules["orbit-controls"]["source_url"] == (
        f"https://cdn.jsdelivr.net/npm/three@{PINNED_VERSION}/examples/jsm/controls/OrbitControls.js"
    )
    assert modules["orbit-controls"]["local_path"] == "web/vendor/OrbitControls.js"

    for module in modules.values():
        local_path = PROJECT_ROOT / module["local_path"]
        assert local_path.is_file()
        assert re.fullmatch(r"[0-9a-f]{64}", module["sha256"])
        assert module["sha256"] == _sha256(local_path)
        assert module["license"] == {"spdx": "MIT", "source": "license"}


def test_browser_module_resolution_remains_local_and_offline_capable():
    index_html = (PROJECT_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    application_js = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    orbit_controls = (VENDOR_ROOT / "OrbitControls.js").read_text(encoding="utf-8")

    assert '"three": "/vendor/three.module.js"' in index_html
    assert re.search(r"""from\s+['"]three['"]""", orbit_controls)
    assert "cdn.jsdelivr.net" not in index_html
    assert "cdn.jsdelivr.net" not in application_js


def test_vendor_git_attributes_preserve_the_hashed_upstream_bytes():
    attributes = (VENDOR_ROOT / ".gitattributes").read_text(encoding="ascii")

    assert "*.js -text" in attributes
    assert "*.txt -text" in attributes


def test_vendor_script_verifies_the_checked_in_runtime_without_network_downloads():
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "scripts" / "vendor_frontend.py"), "--verify"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Verified Three.js 0.180.0 vendor assets (2 modules and MIT license)." in result.stdout
