from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect, sync_playwright

from em_workbench.app import app


@pytest.fixture(scope="module")
def live_server_url() -> Iterator[str]:
    host = "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        port = sock.getsockname()[1]

    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 10
    while not server.started and time.time() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError("Timed out waiting for browser smoke test server.")

    yield f"http://{host}:{port}"

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture()
def page(live_server_url: str) -> Iterator[Page]:
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            page = browser.new_page(viewport={"width": 1440, "height": 900})
            page.goto(live_server_url, wait_until="networkidle")
            yield page
            browser.close()
    except PlaywrightError as error:
        pytest.fail(
            "Playwright Chromium is unavailable. Install it only through "
            "'.\\.tools\\uv\\uv.exe run python -m playwright install chromium'. "
            f"Original error: {error}"
        )


def _fill_number(page: Page, label: str, value: str) -> None:
    field = page.get_by_label(label)
    field.fill(value)
    field.press("Tab")


def _number_attr(page: Page, test_id: str, attribute: str) -> float:
    value = page.get_by_test_id(test_id).get_attribute(attribute)
    assert value is not None
    return float(value)


def _assert_inside_viewbox(value: float) -> None:
    assert 0 <= value <= 100


def test_browser_interaction_slice_keeps_state_across_2d_3d_toggle(page: Page) -> None:
    expect(page.get_by_role("heading", name="EM Workbench")).to_be_visible()
    expect(page.get_by_test_id("runtime-status")).to_contain_text("Three.js")

    page.get_by_role("button", name="Add point charge").click()
    page.get_by_role("button", name="Add ring").click()

    expect(page.get_by_test_id("source-card-point-1")).to_contain_text("Point 1")
    expect(page.get_by_test_id("source-card-ring-1")).to_contain_text("Ring 1")
    expect(page.get_by_test_id("view-2d")).to_contain_text("Point 1")
    expect(page.get_by_test_id("view-2d")).to_contain_text("Ring 1")

    point_x = _number_attr(page, "source-point-2d-point-1", "cx")
    point_y = _number_attr(page, "source-point-2d-point-1", "cy")
    point_radius = _number_attr(page, "source-point-2d-point-1", "r")
    _assert_inside_viewbox(point_x - point_radius)
    _assert_inside_viewbox(point_x + point_radius)
    _assert_inside_viewbox(point_y - point_radius)
    _assert_inside_viewbox(point_y + point_radius)

    ring_x = _number_attr(page, "source-ring-2d-ring-1", "cx")
    ring_y = _number_attr(page, "source-ring-2d-ring-1", "cy")
    ring_radius = _number_attr(page, "source-ring-2d-ring-1", "r")
    _assert_inside_viewbox(ring_x - ring_radius)
    _assert_inside_viewbox(ring_x + ring_radius)
    _assert_inside_viewbox(ring_y - ring_radius)
    _assert_inside_viewbox(ring_y + ring_radius)

    probe_x = _number_attr(page, "probe-marker-2d", "data-view-x")
    probe_y = _number_attr(page, "probe-marker-2d", "data-view-y")
    _assert_inside_viewbox(probe_x - 4)
    _assert_inside_viewbox(probe_x + 4)
    _assert_inside_viewbox(probe_y - 4)
    _assert_inside_viewbox(probe_y + 4)

    _fill_number(page, "Probe x", "0.22")
    _fill_number(page, "Probe y", "0.03")
    _fill_number(page, "Probe z", "0.08")

    expect(page.get_by_test_id("solver-status")).to_contain_text("Ready")
    expect(page.get_by_test_id("potential-value")).not_to_contain_text("Unavailable")
    expect(page.get_by_test_id("field-magnitude-value")).not_to_contain_text("Unavailable")
    expect(page.get_by_test_id("contribution-list")).to_contain_text("point-1")
    expect(page.get_by_test_id("contribution-list")).to_contain_text("ring-1")
    expect(page.get_by_test_id("quality-value")).to_contain_text("preview")
    expect(page.get_by_test_id("warning-list")).to_contain_text("finite-segment approximation")

    page.get_by_role("button", name="3D").click()
    expect(page.get_by_test_id("view-3d")).to_be_visible()
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-ring-normal-three", "0,1,0")
    expect(page.get_by_test_id("mode-label")).to_contain_text("3D")
    expect(page.get_by_test_id("source-count")).to_contain_text("2 sources")
    expect(page.get_by_test_id("probe-position")).to_contain_text("0.220")
    expect(page.get_by_test_id("potential-value")).not_to_contain_text("Unavailable")

    page.get_by_role("button", name="2D").click()
    expect(page.get_by_test_id("view-2d")).to_be_visible()
    expect(page.get_by_test_id("source-count")).to_contain_text("2 sources")
    expect(page.get_by_test_id("probe-position")).to_contain_text("0.220")
    expect(page.get_by_test_id("source-card-ring-1")).to_contain_text("Ring 1")
