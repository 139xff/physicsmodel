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


def _axis_tick_text_height(page: Page) -> float:
    height = page.locator("[data-testid='axis-tick-2d-x'] text").first.evaluate(
        "element => element.getBoundingClientRect().height"
    )
    return float(height)


def test_browser_interaction_slice_keeps_state_across_2d_3d_toggle(page: Page) -> None:
    expect(page.get_by_role("heading", name="电磁工作台")).to_be_visible()
    expect(page.get_by_test_id("runtime-status")).to_contain_text("Three.js")

    page.locator("#add-point").click()
    page.locator("#add-line-segment").click()
    page.locator("#add-ring").click()

    expect(page.get_by_test_id("source-card-point-1")).to_contain_text("点电荷 1")
    expect(page.get_by_test_id("source-card-ring-1")).to_contain_text("带电圆环 1")
    expect(page.get_by_test_id("view-2d")).to_contain_text("点电荷 1")
    expect(page.get_by_test_id("view-2d")).to_contain_text("带电圆环 1")

    point_x = _number_attr(page, "source-point-2d-point-1", "cx")
    point_y = _number_attr(page, "source-point-2d-point-1", "cy")
    point_radius = _number_attr(page, "source-point-2d-point-1", "r")
    assert point_radius == 0.2
    _assert_inside_viewbox(point_x - point_radius)
    _assert_inside_viewbox(point_x + point_radius)
    _assert_inside_viewbox(point_y - point_radius)
    _assert_inside_viewbox(point_y + point_radius)

    line_x1 = _number_attr(page, "source-line-segment-2d-line-segment-1", "x1")
    line_x2 = _number_attr(page, "source-line-segment-2d-line-segment-1", "x2")
    line_y1 = _number_attr(page, "source-line-segment-2d-line-segment-1", "y1")
    line_y2 = _number_attr(page, "source-line-segment-2d-line-segment-1", "y2")
    line_length = ((line_x2 - line_x1) ** 2 + (line_y2 - line_y1) ** 2) ** 0.5
    assert line_length == pytest.approx(0.4)

    ring_x = _number_attr(page, "source-ring-2d-ring-1", "cx")
    ring_y = _number_attr(page, "source-ring-2d-ring-1", "cy")
    ring_radius = _number_attr(page, "source-ring-2d-ring-1", "r")
    assert ring_radius == 0.2
    _assert_inside_viewbox(ring_x - ring_radius)
    _assert_inside_viewbox(ring_x + ring_radius)
    _assert_inside_viewbox(ring_y - ring_radius)
    _assert_inside_viewbox(ring_y + ring_radius)

    expect(page.get_by_test_id("probe-marker-2d")).to_have_count(0)

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
    expect(page.get_by_test_id("source-count")).to_contain_text("3 个源")
    expect(page.get_by_test_id("probe-position")).to_contain_text("0.220")
    expect(page.get_by_test_id("potential-value")).not_to_contain_text("暂无")

    page.get_by_role("button", name="2D").click()
    expect(page.get_by_test_id("view-2d")).to_be_visible()
    expect(page.get_by_test_id("source-count")).to_contain_text("3 个源")
    expect(page.get_by_test_id("probe-position")).to_contain_text("0.220")
    expect(page.get_by_test_id("source-card-ring-1")).to_contain_text("带电圆环 1")


def test_browser_views_use_fixed_ten_meter_centimeter_grid(page: Page) -> None:
    page.locator("#add-point").click()

    page.locator('[data-source-id="point-1"][data-field="position.x"]').fill("0.08")
    page.locator('[data-source-id="point-1"][data-field="position.y"]').fill("-0.08")
    page.locator('[data-source-id="point-1"][data-field="position.z"]').fill("0")
    page.locator('[data-source-id="point-1"][data-field="position.z"]').press("Tab")

    page.locator("#probe-x").fill("-0.05")
    page.locator("#probe-y").fill("0.045")
    page.locator("#probe-z").fill("0")
    page.locator("#probe-z").press("Tab")

    view_box = page.get_by_test_id("view-2d").locator("svg").get_attribute("viewBox")
    assert view_box == "-10 -10 20 20"

    grid = page.locator("#grid")
    expect(grid).to_have_attribute("width", "1")
    expect(grid).to_have_attribute("height", "1")
    expect(page.get_by_test_id("axis-label-2d-x")).to_have_count(0)
    expect(page.get_by_test_id("axis-label-2d-y")).to_have_count(0)
    expect(page.get_by_test_id("axis-label-2d-z")).to_have_count(0)
    expect(page.get_by_test_id("axis-line-2d-x")).to_have_class("axis-line axis-line-x")
    expect(page.get_by_test_id("axis-line-2d-y")).to_have_class("axis-line axis-line-y")
    expect(page.get_by_test_id("axis-arrow-2d-x")).to_be_visible()
    expect(page.get_by_test_id("axis-arrow-2d-y")).to_be_visible()

    axis_layer = page.get_by_test_id("axis-layer-2d")
    x_tick_count = int(axis_layer.get_attribute("data-x-tick-count") or "0")
    y_tick_count = int(axis_layer.get_attribute("data-y-tick-count") or "0")
    assert 0 < x_tick_count <= 20
    assert 0 < y_tick_count <= 20
    assert axis_layer.get_attribute("data-axis-unit") == "cm"
    assert axis_layer.get_attribute("data-tick-length-px") == "7"
    label_font_px = float(axis_layer.get_attribute("data-label-font-px") or "0")
    assert 50 <= label_font_px <= 80

    point_x = _number_attr(page, "source-point-2d-point-1", "cx")
    point_y = _number_attr(page, "source-point-2d-point-1", "cy")
    point_radius = _number_attr(page, "source-point-2d-point-1", "r")
    assert point_x == 8
    assert point_y == 8
    assert point_radius == 0.2
    _assert_inside_svg_viewbox(page, "view-2d", point_x - point_radius, point_y)
    _assert_inside_svg_viewbox(page, "view-2d", point_x + point_radius, point_y)
    _assert_inside_svg_viewbox(page, "view-2d", point_x, point_y - point_radius)
    _assert_inside_svg_viewbox(page, "view-2d", point_x, point_y + point_radius)

    expect(page.get_by_test_id("probe-marker-2d")).to_have_count(0)

    page.get_by_role("button", name="3D").click()
    expect(page.get_by_test_id("view-3d")).to_be_visible()
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-grid-size-meters", "20")
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-grid-cell-size-meters", "0.01")
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-grid-divisions", "2000")
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-axis-min-meters", "-10")
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-axis-max-meters", "10")
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-axis-labels", "+X,+Y,+Z")
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-camera-zoom", "100")
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-camera-far-meters", "10000")
    expect(page.get_by_test_id("view-3d")).to_have_attribute(
        "data-point-marker-radius-meters",
        "0.005",
    )
    expect(page.get_by_test_id("view-3d")).to_have_attribute(
        "data-probe-marker-radius-meters",
        "0.005",
    )
    expect(page.get_by_test_id("view-3d")).to_have_attribute(
        "data-controls-max-distance-meters",
        "5000",
    )


def test_browser_2d_view_zooms_with_origin_fixed_at_center(page: Page) -> None:
    initial_min_x, initial_min_y, initial_width, initial_height = _svg_viewbox(page)
    assert (initial_min_x, initial_min_y, initial_width, initial_height) == (
        -10,
        -10,
        20,
        20,
    )
    initial_zoom = page.get_by_test_id("view-2d").locator("svg").get_attribute("data-zoom")
    assert initial_zoom == "100"
    initial_axis_layer = page.get_by_test_id("axis-layer-2d")
    initial_tick_length = initial_axis_layer.get_attribute("data-tick-length-px")
    initial_label_size = initial_axis_layer.get_attribute("data-label-font-px")

    surface = page.get_by_test_id("view-2d")
    box = surface.bounding_box()
    assert box is not None
    center_x = box["x"] + box["width"] / 2
    center_y = box["y"] + box["height"] / 2

    page.mouse.move(center_x, center_y)
    page.mouse.wheel(0, -700)
    zoomed_min_x, zoomed_min_y, zoomed_width, zoomed_height = _svg_viewbox(page)
    zoom_attr = surface.locator("svg").get_attribute("data-zoom")
    zoomed_axis_layer = page.get_by_test_id("axis-layer-2d")
    assert zoom_attr is not None
    assert float(zoom_attr) > 1
    assert zoomed_axis_layer.get_attribute("data-tick-length-px") == initial_tick_length
    assert zoomed_axis_layer.get_attribute("data-label-font-px") == initial_label_size
    assert int(zoomed_axis_layer.get_attribute("data-x-tick-count") or "0") <= 20
    assert int(zoomed_axis_layer.get_attribute("data-y-tick-count") or "0") <= 20
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

    for _ in range(8):
        page.mouse.wheel(0, -700)
    deep_zoom_min_x, deep_zoom_min_y, deep_zoom_width, deep_zoom_height = _svg_viewbox(page)
    deep_zoom_attr = surface.locator("svg").get_attribute("data-zoom")
    assert deep_zoom_attr is not None
    assert float(deep_zoom_attr) > 80
    assert deep_zoom_width < second_width
    assert deep_zoom_height < second_height
    assert deep_zoom_min_x == -deep_zoom_width / 2
    assert deep_zoom_min_y == -deep_zoom_height / 2


def test_browser_2d_axis_label_size_follows_viewport_not_zoom(page: Page) -> None:
    initial_axis_layer = page.get_by_test_id("axis-layer-2d")
    initial_label_size = float(initial_axis_layer.get_attribute("data-label-font-px") or "0")
    initial_text_height = _axis_tick_text_height(page)

    surface = page.get_by_test_id("view-2d")
    box = surface.bounding_box()
    assert box is not None
    page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    page.mouse.wheel(0, -700)

    zoomed_label_size = float(
        page.get_by_test_id("axis-layer-2d").get_attribute("data-label-font-px") or "0"
    )
    zoomed_text_height = _axis_tick_text_height(page)
    assert zoomed_label_size == initial_label_size
    assert zoomed_text_height == pytest.approx(initial_text_height, abs=1.5)

    page.set_viewport_size({"width": 1920, "height": 1100})
    page.wait_for_timeout(300)
    larger_label_size = float(
        page.get_by_test_id("axis-layer-2d").get_attribute("data-label-font-px") or "0"
    )
    larger_text_height = _axis_tick_text_height(page)
    assert larger_label_size > initial_label_size
    assert larger_label_size <= 80
    assert larger_text_height > initial_text_height


def test_browser_pan_tool_moves_view_without_moving_axes(page: Page) -> None:
    pan_tool = page.get_by_test_id("pan-tool")
    expect(pan_tool).to_be_visible()
    expect(pan_tool).to_have_attribute("aria-pressed", "false")

    initial_min_x, initial_min_y, initial_width, initial_height = _svg_viewbox(page)
    pan_tool.click()
    expect(pan_tool).to_have_attribute("aria-pressed", "true")

    surface = page.get_by_test_id("view-2d")
    box = surface.bounding_box()
    assert box is not None
    center_x = box["x"] + box["width"] / 2
    center_y = box["y"] + box["height"] / 2

    page.mouse.move(center_x, center_y)
    page.mouse.down()
    page.mouse.move(center_x - 140, center_y - 90)
    page.mouse.up()

    panned_min_x, panned_min_y, panned_width, panned_height = _svg_viewbox(page)
    assert panned_width == initial_width
    assert panned_height == initial_height
    assert panned_min_x > initial_min_x
    assert panned_min_y > initial_min_y

    panned_view_box = _svg_viewbox(page)
    pan_tool.click()
    expect(pan_tool).to_have_attribute("aria-pressed", "false")
    assert _svg_viewbox(page) == panned_view_box
    pan_tool.click()
    expect(pan_tool).to_have_attribute("aria-pressed", "true")
    assert _svg_viewbox(page) == panned_view_box

    grid = page.locator("#grid")
    expect(grid).to_have_attribute("width", "1")
    expect(grid).to_have_attribute("height", "1")

    page.get_by_role("button", name="3D").click()
    expect(page.get_by_test_id("view-3d")).to_be_visible()
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-pan-mode", "true")
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-pan-speed", "0.04")

    pan_tool.click()
    expect(pan_tool).to_have_attribute("aria-pressed", "false")
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-pan-mode", "false")
    expect(page.get_by_test_id("view-3d")).to_have_attribute("data-pan-speed", "1")


def test_browser_static_source_editing_overlays_and_presets(page: Page) -> None:
    expect(page.locator("#add-infinite-plane")).to_be_hidden()
    for button_selector, test_id in [
        ("#add-point", "source-card-point-1"),
        ("#add-line-segment", "source-card-line-segment-1"),
        ("#add-ring", "source-card-ring-1"),
        ("#add-disk", "source-card-disk-1"),
        ("#add-spherical-shell", "source-card-spherical-shell-1"),
    ]:
        page.locator(button_selector).click()
        expect(page.get_by_test_id(test_id)).to_be_visible()

    expect(page.get_by_test_id("source-count")).to_contain_text("5 个源")
    page.get_by_role("button", name="3D").click()
    expect(page.locator("#add-infinite-plane")).to_be_visible()
    page.locator("#add-infinite-plane").click()
    expect(page.get_by_test_id("source-card-infinite-plane-1")).to_be_visible()

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
