import json
import subprocess
import sys
from pathlib import Path


def test_cli_renders_accessible_html_and_escapes_content(tmp_path):
    script_path = Path(__file__).parents[1] / "scripts" / "render_task_report.py"
    input_path = tmp_path / "task-report.json"
    output_path = tmp_path / "task-report.html"
    report = {
        "title": "Task <01>: uv foundation",
        "completed_at": "2026-05-27T14:30:00+08:00",
        "status": "DONE",
        "scope_delivered": ["Pinned Python 3.12 & lockfile workflow."],
        "scope_deferred": ["Application shell."],
        "stack": [{"concern": "Runtime", "choice": "Python 3.12 + uv"}],
        "changed_files": [{"path": "pyproject.toml", "purpose": "Dependencies"}],
        "commands": [
            {
                "command": r".\.tools\uv\uv.exe lock",
                "outcome": "PASS",
                "evidence": "Resolved packages.",
            }
        ],
        "verification": [
            {
                "check": "Unit tests",
                "outcome": "PASS",
                "evidence": "1 passed",
            }
        ],
        "limitations": ["No browser UI in this task."],
        "next_task": "Build the FastAPI shell.",
    }

    input_path.write_text(json.dumps(report), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--input",
            str(input_path),
            "--output",
            str(output_path),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    html = output_path.read_text(encoding="utf-8")
    assert '<html lang="en">' in html
    assert "<main>" in html
    assert "<h1>Task &lt;01&gt;: uv foundation</h1>" in html
    assert '<time datetime="2026-05-27T14:30:00+08:00">' in html
    assert "Python 3.12 &amp; lockfile workflow." in html
    assert "<caption>Commands executed</caption>" in html
    assert '<th scope="col">Command</th>' in html
    assert r".\.tools\uv\uv.exe lock" in html
