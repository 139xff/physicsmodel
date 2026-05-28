import hashlib
import json
import re
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
UV = PROJECT_ROOT / ".tools" / "uv" / "uv.exe"
VENDOR_ROOT = PROJECT_ROOT / "web" / "vendor"
MANIFEST_PATH = VENDOR_ROOT / "manifest.json"
PINNED_VERSION = "0.180.0"
RELATIVE_MODULE_SPECIFIER = re.compile(
    r"""(?:from\s+|import\s*)['"](\./[^'"]+)['"]"""
)


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
    assert set(modules) == {"three", "three-core", "orbit-controls"}
    assert modules["three"]["source_url"] == (
        f"https://cdn.jsdelivr.net/npm/three@{PINNED_VERSION}/build/three.module.js"
    )
    assert modules["three"]["local_path"] == "web/vendor/three.module.js"
    assert modules["three-core"]["source_url"] == (
        f"https://cdn.jsdelivr.net/npm/three@{PINNED_VERSION}/build/three.core.js"
    )
    assert modules["three-core"]["local_path"] == "web/vendor/three.core.js"
    assert modules["orbit-controls"]["source_url"] == (
        f"https://cdn.jsdelivr.net/npm/three@{PINNED_VERSION}/examples/jsm/controls/OrbitControls.js"
    )
    assert modules["orbit-controls"]["local_path"] == "web/vendor/controls/OrbitControls.js"

    for module in modules.values():
        local_path = PROJECT_ROOT / module["local_path"]
        assert local_path.is_file()
        assert re.fullmatch(r"[0-9a-f]{64}", module["sha256"])
        assert module["sha256"] == _sha256(local_path)
        assert module["license"] == {"spdx": "MIT", "source": "license"}


def test_browser_module_resolution_remains_local_and_offline_capable():
    index_html = (PROJECT_ROOT / "web" / "index.html").read_text(encoding="utf-8")
    application_js = (PROJECT_ROOT / "web" / "app.js").read_text(encoding="utf-8")
    orbit_controls_path = VENDOR_ROOT / "controls" / "OrbitControls.js"

    assert '"three": "./vendor/three.module.js"' in index_html
    assert '"three/addons/": "./vendor/"' in index_html
    assert orbit_controls_path.is_file()
    assert not (VENDOR_ROOT / "OrbitControls.js").exists()
    orbit_controls = orbit_controls_path.read_text(encoding="utf-8")
    assert re.search(r"""from\s+['"]three['"]""", orbit_controls)
    assert "cdn.jsdelivr.net" not in index_html
    assert "cdn.jsdelivr.net" not in application_js


def test_manifest_covers_the_relative_es_module_dependency_graph():
    modules = _manifest()["modules"]
    module_paths = {module["local_path"] for module in modules}

    for module in modules:
        local_path = PROJECT_ROOT / module["local_path"]
        if local_path.suffix != ".js":
            continue
        contents = local_path.read_text(encoding="utf-8")
        for specifier in RELATIVE_MODULE_SPECIFIER.findall(contents):
            dependency_path = (local_path.parent / specifier).resolve()
            dependency_manifest_path = dependency_path.relative_to(PROJECT_ROOT).as_posix()
            assert dependency_manifest_path in module_paths
            assert dependency_path.is_file()


def test_vendor_git_attributes_preserve_the_hashed_upstream_bytes():
    attributes = (VENDOR_ROOT / ".gitattributes").read_text(encoding="ascii")

    assert "*.js -text" in attributes
    assert "*.txt -text" in attributes
    assert "controls/OrbitControls.js -text" in attributes
    assert "three.core.js whitespace=-space-before-tab" in attributes


def test_vendor_script_verifies_the_checked_in_runtime_without_network_downloads():
    result = subprocess.run(
        [
            str(UV),
            "run",
            "--locked",
            "--no-sync",
            "python",
            str(PROJECT_ROOT / "scripts" / "vendor_frontend.py"),
            "--verify",
        ],
        cwd=PROJECT_ROOT,
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "Verified Three.js 0.180.0 vendor assets (3 modules and MIT license)." in result.stdout
