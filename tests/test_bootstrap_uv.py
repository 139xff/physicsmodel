import hashlib
import shutil
import subprocess
from pathlib import Path


def test_bootstrap_rejects_tampered_existing_uv_before_execution(tmp_path):
    project_root = Path(__file__).parents[1]
    source_script = project_root / "scripts" / "bootstrap_uv.ps1"
    source_uv = project_root / ".tools" / "uv" / "uv.exe"
    original_digest = hashlib.sha256(source_uv.read_bytes()).hexdigest()

    temporary_script = tmp_path / "scripts" / "bootstrap_uv.ps1"
    temporary_uv = tmp_path / ".tools" / "uv" / "uv.exe"
    temporary_script.parent.mkdir(parents=True)
    temporary_uv.parent.mkdir(parents=True)
    shutil.copy2(source_script, temporary_script)
    temporary_uv.write_bytes(source_uv.read_bytes() + b"\ntampered-copy-for-bootstrap-test")

    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(temporary_script),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    combined_output = result.stdout + result.stderr
    assert result.returncode != 0
    assert "uv executable SHA-256 mismatch" in combined_output
    assert "Project-local uv is already present" not in combined_output
    assert hashlib.sha256(source_uv.read_bytes()).hexdigest() == original_digest


def test_existing_uv_digest_check_precedes_version_execution():
    source_script = Path(__file__).parents[1] / "scripts" / "bootstrap_uv.ps1"
    script = source_script.read_text(encoding="utf-8")
    existing_binary_branch = script.split(
        "if ((Test-Path -LiteralPath $targetUv) -and -not $Force) {", maxsplit=1
    )[1].split("\n}", maxsplit=1)[0]
    digest_check = "Assert-UvExecutableDigest -Path $targetUv"
    version_execution = "$installedVersionOutput = (& $targetUv --version | Out-String).Trim()"

    assert existing_binary_branch.index(digest_check) < existing_binary_branch.index(
        version_execution
    )
