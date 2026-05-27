"""Render a standalone engineering task report from structured JSON input."""

from __future__ import annotations

import argparse
import json
import sys
from html import escape
from pathlib import Path
from typing import Any


def _required_text(report: dict[str, Any], key: str) -> str:
    value = report.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Field '{key}' must be a non-empty string.")
    return value


def _text_items(report: dict[str, Any], key: str) -> list[str]:
    value = report.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"Field '{key}' must be a non-empty list of strings.")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"Field '{key}' must contain only non-empty strings.")
    return value


def _table_rows(report: dict[str, Any], key: str, columns: list[str]) -> list[list[str]]:
    value = report.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"Field '{key}' must be a non-empty list of objects.")

    rows: list[list[str]] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"Field '{key}' must contain only objects.")
        row: list[str] = []
        for column in columns:
            cell = item.get(column)
            if not isinstance(cell, str) or not cell.strip():
                raise ValueError(
                    f"Every '{key}' entry must provide non-empty text field '{column}'."
                )
            row.append(cell)
        rows.append(row)
    return rows


def _render_items(heading: str, items: list[str]) -> str:
    rendered_items = "\n".join(f"        <li>{escape(item)}</li>" for item in items)
    return (
        f"    <section>\n"
        f"      <h2>{escape(heading)}</h2>\n"
        f"      <ul>\n{rendered_items}\n      </ul>\n"
        f"    </section>\n"
    )


def _render_table(
    heading: str,
    caption: str,
    column_headings: list[str],
    rows: list[list[str]],
    *,
    code_first_column: bool = False,
) -> str:
    headings = "".join(f'<th scope="col">{escape(item)}</th>' for item in column_headings)
    rendered_rows: list[str] = []
    for row in rows:
        cells: list[str] = []
        for index, cell in enumerate(row):
            content = escape(cell)
            if code_first_column and index == 0:
                content = f"<code>{content}</code>"
            cells.append(f"<td>{content}</td>")
        rendered_rows.append(f"        <tr>{''.join(cells)}</tr>")

    return (
        "    <section>\n"
        f"      <h2>{escape(heading)}</h2>\n"
        "      <div class=\"table-scroll\">\n"
        "        <table>\n"
        f"          <caption>{escape(caption)}</caption>\n"
        f"          <thead><tr>{headings}</tr></thead>\n"
        "          <tbody>\n"
        f"{'\n'.join(rendered_rows)}\n"
        "          </tbody>\n"
        "        </table>\n"
        "      </div>\n"
        "    </section>\n"
    )


def render_report(report: dict[str, Any]) -> str:
    """Return accessible, standalone HTML for a validated task-report mapping."""
    title = _required_text(report, "title")
    completed_at = _required_text(report, "completed_at")
    status = _required_text(report, "status")
    next_task = _required_text(report, "next_task")
    delivered = _text_items(report, "scope_delivered")
    deferred = _text_items(report, "scope_deferred")
    limitations = _text_items(report, "limitations")
    stack = _table_rows(report, "stack", ["concern", "choice"])
    changed_files = _table_rows(report, "changed_files", ["path", "purpose"])
    commands = _table_rows(report, "commands", ["command", "outcome", "evidence"])
    verification = _table_rows(report, "verification", ["check", "outcome", "evidence"])

    sections = [
        _render_items("Scope Delivered", delivered),
        _render_items("Scope Deferred", deferred),
        _render_table("Technical Stack", "Technology choices", ["Concern", "Choice"], stack),
        _render_table(
            "Changed Files",
            "Files changed in this task",
            ["Path", "Purpose"],
            changed_files,
            code_first_column=True,
        ),
        _render_table(
            "Commands",
            "Commands executed",
            ["Command", "Outcome", "Evidence"],
            commands,
            code_first_column=True,
        ),
        _render_table(
            "Verification",
            "Verification evidence",
            ["Check", "Outcome", "Evidence"],
            verification,
        ),
        _render_items("Known Risks And Limitations", limitations),
    ]

    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8">\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"  <title>{escape(title)} - Engineering Task Report</title>\n"
        "  <style>\n"
        "    :root { color-scheme: light; --ink: #19202b; --muted: #566576; "
        "--line: #d3dce6; --panel: #f5f7fa; --accent: #0d5e63; }\n"
        "    * { box-sizing: border-box; }\n"
        "    body { margin: 0; color: var(--ink); background: #fff; "
        "font: 16px/1.55 system-ui, -apple-system, \"Segoe UI\", sans-serif; }\n"
        "    main { max-width: 70rem; margin: 0 auto; padding: 2.5rem 1.25rem 4rem; }\n"
        "    header { border-bottom: 3px solid var(--accent); margin-bottom: 2rem; "
        "padding-bottom: 1.25rem; }\n"
        "    h1 { font-size: clamp(1.6rem, 3vw, 2.3rem); margin: 0 0 0.75rem; }\n"
        "    h2 { font-size: 1.2rem; margin: 2rem 0 0.75rem; }\n"
        "    .meta { display: flex; flex-wrap: wrap; gap: 0.75rem 1.5rem; color: var(--muted); }\n"
        "    .status { background: #e7f4f1; border-radius: 999px; color: var(--accent); "
        "font-weight: 700; padding: 0.15rem 0.65rem; }\n"
        "    ul { margin-top: 0.5rem; padding-left: 1.4rem; }\n"
        "    .table-scroll { overflow-x: auto; }\n"
        "    table { border-collapse: collapse; min-width: 36rem; width: 100%; }\n"
        "    caption { color: var(--muted); font-size: 0.95rem; text-align: left; "
        "padding: 0 0 0.5rem; }\n"
        "    th, td { border: 1px solid var(--line); padding: 0.6rem 0.7rem; "
        "text-align: left; vertical-align: top; }\n"
        "    th { background: var(--panel); }\n"
        "    code { font: 0.92em ui-monospace, \"Cascadia Code\", Consolas, monospace; "
        "white-space: pre-wrap; }\n"
        "    .next { border-left: 4px solid var(--accent); background: var(--panel); "
        "padding: 0.85rem 1rem; }\n"
        "  </style>\n"
        "</head>\n"
        "<body>\n"
        "  <main>\n"
        "    <header>\n"
        f"      <h1>{escape(title)}</h1>\n"
        "      <div class=\"meta\">\n"
        f"        <span class=\"status\">{escape(status)}</span>\n"
        f"        <span>Completed: <time datetime=\"{escape(completed_at)}\">"
        f"{escape(completed_at)}</time></span>\n"
        "      </div>\n"
        "    </header>\n"
        f"{''.join(sections)}"
        "    <section>\n"
        "      <h2>Next Scheduled Task</h2>\n"
        f"      <p class=\"next\">{escape(next_task)}</p>\n"
        "    </section>\n"
        "  </main>\n"
        "</body>\n"
        "</html>\n"
    )


def write_report(report: dict[str, Any], output_path: Path) -> None:
    """Write one rendered task report to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report(report), encoding="utf-8")


def _load_report(input_source: str) -> dict[str, Any]:
    if input_source == "-":
        data = json.load(sys.stdin)
    else:
        with Path(input_source).open(encoding="utf-8") as input_file:
            data = json.load(input_file)
    if not isinstance(data, dict):
        raise ValueError("Report input must be a JSON object.")
    return data


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to report JSON, or '-' for stdin.")
    parser.add_argument("--output", required=True, type=Path, help="Destination HTML report path.")
    args = parser.parse_args(argv)

    try:
        report = _load_report(args.input)
        write_report(report, args.output)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
