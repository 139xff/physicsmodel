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
            page_errors: list[str] = []
            console_errors: list[str] = []
            page.on("pageerror", lambda error: page_errors.append(str(error)))
            page.on(
                "console",
                lambda message: (
                    console_errors.append(message.text) if message.type == "error" else None
                ),
            )
            page.goto(live_server_url, wait_until="networkidle")
            yield page
            assert page_errors == []
            assert console_errors == []
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
    assert -1000 <= value <= 1000


def _assert_inside_svg_viewbox(page: Page, test_id: str, x: float, y: float) -> None:
    value = page.get_by_test_id(test_id).locator("svg").get_attribute("viewBox")
    assert value is not None
    min_x, min_y, width, height = [float(part) for part in value.split()]
    assert min_x <= x <= min_x + width
    assert min_y <= y <= min_y + height


def _svg_viewbox(page: Page) -> tuple[float, float, float, float]:
    value = page.get_by_test_id("view-2d").locator("svg").get_attribute("viewBox")
    assert value is not None
    return tuple(float(part) for part in value.split())


def test_browser_interaction_slice_keeps_state_across_2d_3d_toggle(page: Page) -> None:
    expect(page.get_by_role("heading", name="电磁工作台")).to_be_visible()
    expect(page.get_by_test_id("runtime-status")).to_contain_text("Three.js")

    page.locator("#add-point").click()
    page.locator("#add-ring").click()

    expect(page.get_by_test_id("source-card-point-1")).to_contain_text("点电荷 1")
    expect(page.get_by_test_id("source-card-ring-1")).to_contain_text("带电圆环 1")
    expect(page.get_by_test_id("view-2d")).to_contain_text("点电荷 1")
    expect(page.get_by_test_id("view-2d")).to_contain_text("带电圆环 1")

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

    page.locator("#probe-x").fill("0.22")
    page.locator("#probe-y").fill("0.03")
    page.locator("#probe-z").fill("0.08")
    page.locator("#probe-z").press("Tab")

    expect(page.get_by_test_id("solver-status")).to_contain_text("已完成")
    expect(page.get_by_test_id("potential-value")).not_to_contain_text("暂无")
    expect(page.get_by_test_id("field-magnitude-value")).not_to_contain_text("暂无")
    expect(page.get_by_test_id("contribution-list")).to_contain_text("point-1")
    expect(page.get_by_test_id("contribution-list")).to_contain_text("ring-1")
    expect(page.get_by_test_id("quality-value")).to_contain_text("preview")
    expect(page.get_by_test_id("warning-list")).to_contain_text("finite-segment approximation")

    page.get_by_role("button", name="3D").click()
    expect(page.get_by_test_id("view-3d")).to_be_visible()
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-ring-normal-three", "0,1,0")
    expect(page.get_by_test_id("mode-label")).to_contain_text("3D")
    expect(page.get_by_test_id("source-count")).to_contain_text("2 个源")
    expect(page.get_by_test_id("probe-position")).to_contain_text("0.220")
    expect(page.get_by_test_id("potential-value")).not_to_contain_text("暂无")

    page.get_by_role("button", name="2D").click()
    expect(page.get_by_test_id("view-2d")).to_be_visible()
    expect(page.get_by_test_id("source-count")).to_contain_text("2 个源")
    expect(page.get_by_test_id("probe-position")).to_contain_text("0.220")
    expect(page.get_by_test_id("source-card-ring-1")).to_contain_text("带电圆环 1")


def test_browser_views_use_fixed_ten_meter_centimeter_grid(page: Page) -> None:
    page.locator("#add-point").click()

    page.locator('[data-source-id="point-1"][data-field="position.x"]').fill("9.5")
    page.locator('[data-source-id="point-1"][data-field="position.y"]').fill("-9")
    page.locator('[data-source-id="point-1"][data-field="position.z"]').fill("0")
    page.locator('[data-source-id="point-1"][data-field="position.z"]').press("Tab")

    page.locator("#probe-x").fill("-9.5")
    page.locator("#probe-y").fill("8.5")
    page.locator("#probe-z").fill("0")
    page.locator("#probe-z").press("Tab")

    view_box = page.get_by_test_id("view-2d").locator("svg").get_attribute("viewBox")
    assert view_box == "-1000 -1000 2000 2000"

    grid = page.locator("#grid")
    expect(grid).to_have_attribute("width", "1")
    expect(grid).to_have_attribute("height", "1")

    point_x = _number_attr(page, "source-point-2d-point-1", "cx")
    point_y = _number_attr(page, "source-point-2d-point-1", "cy")
    point_radius = _number_attr(page, "source-point-2d-point-1", "r")
    assert point_x == 950
    assert point_y == 900
    assert point_radius == 1.5
    _assert_inside_svg_viewbox(page, "view-2d", point_x - point_radius, point_y)
    _assert_inside_svg_viewbox(page, "view-2d", point_x + point_radius, point_y)
    _assert_inside_svg_viewbox(page, "view-2d", point_x, point_y - point_radius)
    _assert_inside_svg_viewbox(page, "view-2d", point_x, point_y + point_radius)

    probe_x = _number_attr(page, "probe-marker-2d", "data-view-x")
    probe_y = _number_attr(page, "probe-marker-2d", "data-view-y")
    assert probe_x == -950
    assert probe_y == -850
    _assert_inside_svg_viewbox(page, "view-2d", probe_x - 4, probe_y)
    _assert_inside_svg_viewbox(page, "view-2d", probe_x + 4, probe_y)
    _assert_inside_svg_viewbox(page, "view-2d", probe_x, probe_y - 4)
    _assert_inside_svg_viewbox(page, "view-2d", probe_x, probe_y + 4)

    page.get_by_role("button", name="3D").click()
    expect(page.get_by_test_id("view-3d")).to_be_visible()
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-grid-size-meters", "20")
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-grid-cell-size-meters", "0.01")
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-grid-divisions", "2000")


def test_browser_2d_view_zooms_with_origin_fixed_at_center(page: Page) -> None:
    initial_min_x, initial_min_y, initial_width, initial_height = _svg_viewbox(page)
    assert (initial_min_x, initial_min_y, initial_width, initial_height) == (
        -1000,
        -1000,
        2000,
        2000,
    )

    surface = page.get_by_test_id("view-2d")
    box = surface.bounding_box()
    assert box is not None
    center_x = box["x"] + box["width"] / 2
    center_y = box["y"] + box["height"] / 2

    page.mouse.move(center_x, center_y)
    page.mouse.wheel(0, -700)
    zoomed_min_x, zoomed_min_y, zoomed_width, zoomed_height = _svg_viewbox(page)
    zoom_attr = surface.locator("svg").get_attribute("data-zoom")
    assert zoom_attr is not None
    assert float(zoom_attr) > 1
    assert zoomed_width < initial_width
    assert zoomed_height < initial_height
    assert zoomed_min_x > initial_min_x
    assert zoomed_min_y > initial_min_y
    assert zoomed_min_x == -zoomed_width / 2
    assert zoomed_min_y == -zoomed_height / 2

    page.mouse.move(center_x + 180, center_y + 120)
    page.mouse.wheel(0, -500)
    second_min_x, second_min_y, second_width, second_height = _svg_viewbox(page)
    assert second_width < zoomed_width
    assert second_height < zoomed_height
    assert second_min_x == -second_width / 2
    assert second_min_y == -second_height / 2


def test_browser_static_source_editing_overlays_and_presets(page: Page) -> None:
    for button_selector, test_id in [
        ("#add-point", "source-card-point-1"),
        ("#add-line-segment", "source-card-line-segment-1"),
        ("#add-ring", "source-card-ring-1"),
        ("#add-disk", "source-card-disk-1"),
        ("#add-infinite-plane", "source-card-infinite-plane-1"),
        ("#add-spherical-shell", "source-card-spherical-shell-1"),
    ]:
        page.locator(button_selector).click()
        expect(page.get_by_test_id(test_id)).to_be_visible()

    expect(page.get_by_test_id("source-count")).to_contain_text("6 个源")
    expect(page.get_by_test_id("source-card-line-segment-1")).to_contain_text("方向")
    expect(page.get_by_test_id("source-card-disk-1")).to_contain_text("法向")
    expect(page.get_by_test_id("source-card-infinite-plane-1")).to_contain_text("面电荷密度")
    expect(page.get_by_test_id("source-card-spherical-shell-1")).to_contain_text("半径 m")

    page.locator('[data-source-id="line-segment-1"][data-field="orientation.x"]').fill("0")
    page.locator('[data-source-id="line-segment-1"][data-field="orientation.y"]').fill("1")
    page.locator('[data-source-id="line-segment-1"][data-field="length_m"]').fill("0.18")
    page.locator('[data-source-id="disk-1"][data-field="normal.z"]').fill("1")
    page.locator(
        '[data-source-id="infinite-plane-1"][data-field="surface_charge_density_c_per_m2"]'
    ).fill("2e-9")
    page.locator('[data-source-id="spherical-shell-1"][data-field="radius_m"]').fill("0.14")
    page.locator('[data-source-id="spherical-shell-1"][data-field="radius_m"]').press("Tab")

    page.locator("#quality-select").select_option("refined")
    expect(page.get_by_test_id("quality-value")).to_contain_text("refined")
    expect(page.get_by_test_id("solver-status")).to_contain_text("已完成")

    expect(page.get_by_test_id("overlay-status")).to_contain_text("已完成")
    expect(page.get_by_test_id("overlay-vector-layer")).to_have_attribute("data-vector-count", "25")
    expect(page.get_by_test_id("overlay-summary")).to_contain_text("采样 |E|")

    page.get_by_role("button", name="3D").click()
    expect(page.get_by_test_id("view-3d")).to_be_visible()
    expect(page.get_by_test_id("source-count")).to_contain_text("6 个源")
    expect(page.get_by_test_id("mode-label")).to_contain_text("3D")

    page.get_by_role("button", name="2D").click()
    expect(page.get_by_test_id("view-2d")).to_be_visible()
    expect(page.get_by_test_id("source-card-disk-1")).to_contain_text("带电圆盘 1")

    page.locator("#preset-select").select_option("electric-dipole")
    page.locator("#preset-form button").click()
    expect(page.get_by_test_id("preset-status")).to_contain_text("已加载：Electric dipole")
    expect(page.get_by_test_id("source-count")).to_contain_text("2 个源")
    expect(page.get_by_test_id("source-card-dipole-positive")).to_contain_text("Positive pole")
    expect(page.get_by_test_id("quality-value")).to_contain_text("refined")
    expect(page.get_by_test_id("overlay-vector-layer")).to_have_attribute("data-vector-count", "25")
