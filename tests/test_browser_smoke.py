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


def _view2d_surface_aspect(page: Page) -> float:
    box = page.get_by_test_id("view-2d").bounding_box()
    assert box is not None
    return box["width"] / box["height"]


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
    axis_label_size = float(
        page.get_by_test_id("axis-layer-2d").get_attribute("data-label-font-px") or "0"
    )
    source_label_height = page.get_by_test_id("source-label-2d-point-1").evaluate(
        "element => element.getBoundingClientRect().height"
    )
    axis_text_height = _axis_tick_text_height(page)
    assert source_label_height == pytest.approx(axis_text_height, abs=1.5)
    assert point_radius == pytest.approx(0.5)
    expect(page.get_by_test_id("source-point-2d-point-1")).to_have_attribute(
        "data-visual-radius-cm",
        "0.5",
    )
    expect(page.get_by_test_id("source-point-2d-point-1")).to_have_attribute(
        "data-physics-model",
        "ideal-point",
    )
    expect(page.get_by_test_id("source-point-2d-point-1")).to_have_attribute(
        "data-physics-center",
        "position",
    )
    expect(page.get_by_test_id("source-point-2d-point-1")).to_have_attribute(
        "data-charge-sign",
        "positive",
    )
    expect(page.get_by_test_id("source-point-2d-point-1")).to_have_attribute(
        "data-charge-color",
        "#d92d20",
    )
    point_fill = page.get_by_test_id("source-point-2d-point-1").evaluate(
        "element => getComputedStyle(element).fill"
    )
    assert "gradient" in point_fill
    _assert_inside_viewbox(point_x - point_radius)
    _assert_inside_viewbox(point_x + point_radius)
    _assert_inside_viewbox(point_y - point_radius)
    _assert_inside_viewbox(point_y + point_radius)

    line_x1 = _number_attr(page, "source-line-segment-2d-line-segment-1", "x1")
    line_x2 = _number_attr(page, "source-line-segment-2d-line-segment-1", "x2")
    line_y1 = _number_attr(page, "source-line-segment-2d-line-segment-1", "y1")
    line_y2 = _number_attr(page, "source-line-segment-2d-line-segment-1", "y2")
    line_length = ((line_x2 - line_x1) ** 2 + (line_y2 - line_y1) ** 2) ** 0.5
    assert line_x1 == pytest.approx(-8)
    assert line_y1 == pytest.approx(-8)
    assert line_x2 == pytest.approx(8)
    assert line_y2 == pytest.approx(-8)
    assert line_length == pytest.approx(16)
    expect(page.get_by_test_id("source-line-segment-2d-line-segment-1")).to_have_attribute(
        "data-starts-at-position",
        "true",
    )
    assert float(
        page.get_by_test_id("source-line-segment-2d-line-segment-1").get_attribute("data-stroke-px")
        or "0"
    ) == pytest.approx(axis_label_size, abs=0.05)
    expect(page.get_by_test_id("source-line-segment-2d-line-segment-1")).to_have_attribute(
        "data-charge-color",
        "#d92d20",
    )

    ring_x = _number_attr(page, "source-ring-2d-ring-1", "cx")
    ring_y = _number_attr(page, "source-ring-2d-ring-1", "cy")
    ring_radius = _number_attr(page, "source-ring-2d-ring-1", "r")
    assert ring_radius == 0.2
    assert float(
        page.get_by_test_id("source-ring-2d-ring-1").get_attribute("data-stroke-px") or "0"
    ) == pytest.approx(axis_label_size, abs=0.05)
    expect(page.get_by_test_id("source-ring-2d-ring-1")).to_have_attribute(
        "data-charge-color",
        "#d92d20",
    )
    _assert_inside_viewbox(ring_x - ring_radius)
    _assert_inside_viewbox(ring_x + ring_radius)
    _assert_inside_viewbox(ring_y - ring_radius)
    _assert_inside_viewbox(ring_y + ring_radius)

    expect(page.get_by_test_id("probe-marker-2d")).to_have_count(0)

    page.locator('[data-source-id="line-segment-1"][data-field="charge_c"]').fill("-1.5e-9")
    page.locator('[data-source-id="line-segment-1"][data-field="charge_c"]').press("Tab")
    expect(page.get_by_test_id("source-line-segment-2d-line-segment-1")).to_have_attribute(
        "data-charge-sign",
        "negative",
    )
    expect(page.get_by_test_id("source-line-segment-2d-line-segment-1")).to_have_attribute(
        "data-charge-color",
        "#175cd3",
    )

    page.locator("#probe-x").fill("22")
    page.locator("#probe-y").fill("3")
    page.locator("#probe-submit").click()

    expect(page.get_by_test_id("solver-status")).to_contain_text("已完成")
    expect(page.get_by_test_id("field-magnitude-value")).not_to_contain_text("暂无")
    expect(page.get_by_test_id("contribution-list")).to_contain_text("point-1")
    expect(page.get_by_test_id("contribution-list")).to_contain_text("ring-1")
    expect(page.get_by_test_id("quality-value")).to_contain_text("preview")
    expect(page.get_by_test_id("warning-list")).to_contain_text("finite-segment approximation")

    page.get_by_role("button", name="3D").click()
    expect(page.get_by_test_id("view-3d")).to_be_visible()
    expect(page.get_by_test_id("mode-label")).to_contain_text("3D")
    expect(page.get_by_test_id("source-count")).to_contain_text("0 个源")
    expect(page.get_by_test_id("probe-position")).to_contain_text("20")

    page.get_by_role("button", name="2D").click()
    expect(page.get_by_test_id("view-2d")).to_be_visible()
    expect(page.get_by_test_id("source-count")).to_contain_text("3 个源")
    expect(page.get_by_test_id("probe-position")).to_contain_text("22")
    expect(page.get_by_test_id("source-card-ring-1")).to_contain_text("带电圆环 1")


def test_browser_views_use_fixed_ten_meter_centimeter_grid(page: Page) -> None:
    page.locator("#add-point").click()

    page.locator('[data-source-id="point-1"][data-field="position.x"]').fill("0.08")
    page.locator('[data-source-id="point-1"][data-field="position.y"]').fill("-0.08")
    page.locator('[data-source-id="point-1"][data-field="position.y"]').press("Tab")

    page.locator("#probe-x").fill("-5")
    page.locator("#probe-y").fill("4.5")
    page.locator("#probe-submit").click()

    min_x, min_y, width, height = _svg_viewbox(page)
    assert min_x == pytest.approx(-width / 2)
    assert min_y == pytest.approx(-height / 2)
    assert width == pytest.approx(20)
    assert width / height == pytest.approx(_view2d_surface_aspect(page), rel=0.02)

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
    assert 0 < x_tick_count <= 36
    assert 0 < y_tick_count <= 36
    assert axis_layer.get_attribute("data-axis-unit") == "cm"
    assert axis_layer.get_attribute("data-tick-length-px") == "7"
    label_font_px = float(axis_layer.get_attribute("data-label-font-px") or "0")
    assert 8.75 <= label_font_px <= 20
    assert x_tick_count <= int(axis_layer.get_attribute("data-x-tick-limit") or "0")
    assert y_tick_count <= int(axis_layer.get_attribute("data-y-tick-limit") or "0")
    visible_zero_labels = page.locator(".axis-tick text").evaluate_all(
        "nodes => nodes.filter((node) => node.textContent.trim() === '0').length"
    )
    assert visible_zero_labels == 1
    visible_x_label_count = int(axis_layer.get_attribute("data-visible-x-label-count") or "0")
    visible_y_label_count = int(axis_layer.get_attribute("data-visible-y-label-count") or "0")
    viewport_ratio = float(axis_layer.get_attribute("data-viewport-ratio") or "0")
    label_ratio = visible_x_label_count / visible_y_label_count
    assert label_ratio == pytest.approx(viewport_ratio, rel=0.35)
    assert visible_x_label_count + visible_y_label_count >= 20
    origin_tick_lines = page.locator(".axis-tick").evaluate_all(
        """
        nodes => nodes.filter((node) => {
          const text = node.querySelector('text')?.textContent.trim();
          return text === '0' || text === '';
        }).reduce((count, node) => count + node.querySelectorAll('line').length, 0)
        """
    )
    assert origin_tick_lines == 0
    tick_colors = page.locator(".axis-layer").evaluate(
        """
        (node) => ({
          x: node.querySelector('.axis-tick-x line')?.getAttribute('stroke'),
          y: node.querySelector('.axis-tick-y line')?.getAttribute('stroke'),
        })
        """
    )
    assert tick_colors == {"x": "#d92d20", "y": "#175cd3"}
    x_tick_labels = page.locator(".axis-tick-x text").evaluate_all(
        "nodes => nodes.map((node) => node.textContent.trim()).filter(Boolean)"
    )
    y_tick_labels = page.locator(".axis-tick-y text").evaluate_all(
        "nodes => nodes.map((node) => node.textContent.trim()).filter(Boolean)"
    )
    assert len(x_tick_labels) == len(set(x_tick_labels))
    assert len(y_tick_labels) == len(set(y_tick_labels))

    point_x = _number_attr(page, "source-point-2d-point-1", "cx")
    point_y = _number_attr(page, "source-point-2d-point-1", "cy")
    point_radius = _number_attr(page, "source-point-2d-point-1", "r")
    assert point_x == 8
    assert point_y == 8
    assert point_radius == pytest.approx(0.5)
    expect(page.get_by_test_id("source-point-2d-point-1")).to_have_attribute(
        "data-physics-model",
        "ideal-point",
    )
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
    assert initial_min_x == pytest.approx(-initial_width / 2)
    assert initial_min_y == pytest.approx(-initial_height / 2)
    assert initial_width == pytest.approx(20)
    assert initial_width / initial_height == pytest.approx(_view2d_surface_aspect(page), rel=0.05)
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
    assert int(zoomed_axis_layer.get_attribute("data-x-tick-count") or "0") <= 36
    assert int(zoomed_axis_layer.get_attribute("data-y-tick-count") or "0") <= 36
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
    assert larger_label_size <= 20
    assert larger_text_height > initial_text_height


def test_browser_2d_axis_decimal_labels_do_not_collapse_after_ten(page: Page) -> None:
    surface = page.get_by_test_id("view-2d")
    box = surface.bounding_box()
    assert box is not None
    center_x = box["x"] + box["width"] / 2
    center_y = box["y"] + box["height"] / 2

    page.mouse.move(center_x, center_y)
    for _ in range(3):
        page.mouse.wheel(0, -700)

    pan_tool = page.get_by_test_id("pan-tool")
    pan_tool.click()
    for _ in range(8):
        page.mouse.move(center_x, center_y)
        page.mouse.down()
        page.mouse.move(center_x - 600, center_y)
        page.mouse.up()

    x_tick_labels = page.locator(".axis-tick-x text").evaluate_all(
        "nodes => nodes.map((node) => node.textContent.trim()).filter(Boolean)"
    )
    x_tick_values = [float(label) for label in x_tick_labels]

    assert len(x_tick_labels) == len(set(x_tick_labels))
    assert any(value > 10 and not value.is_integer() for value in x_tick_values)


def test_browser_2d_axis_ticks_reduce_for_small_viewport(page: Page) -> None:
    page.set_viewport_size({"width": 900, "height": 620})
    page.wait_for_timeout(300)

    axis_layer = page.get_by_test_id("axis-layer-2d")
    label_size = float(axis_layer.get_attribute("data-label-font-px") or "0")
    x_tick_count = int(axis_layer.get_attribute("data-x-tick-count") or "0")
    y_tick_count = int(axis_layer.get_attribute("data-y-tick-count") or "0")
    x_tick_limit = int(axis_layer.get_attribute("data-x-tick-limit") or "0")
    y_tick_limit = int(axis_layer.get_attribute("data-y-tick-limit") or "0")

    assert label_size >= 8.75
    assert 0 < x_tick_count <= x_tick_limit <= 36
    assert 0 < y_tick_count <= y_tick_limit <= 36


def test_browser_pan_tool_moves_view_without_moving_axes(page: Page) -> None:
    pan_tool = page.get_by_test_id("pan-tool")
    expect(pan_tool).to_be_visible()
    expect(pan_tool).to_have_attribute("aria-pressed", "false")

    initial_min_x, initial_min_y, initial_width, initial_height = _svg_viewbox(page)
    pan_tool.click()
    expect(pan_tool).to_have_attribute("aria-pressed", "true")
    initial_min_x, initial_min_y, initial_width, initial_height = _svg_viewbox(page)

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
    assert panned_width == pytest.approx(initial_width, rel=0.005)
    assert panned_height == pytest.approx(initial_height, rel=0.005)
    assert panned_min_x > initial_min_x
    assert panned_min_y > initial_min_y

    panned_view_box = _svg_viewbox(page)
    pan_tool.click()
    expect(pan_tool).to_have_attribute("aria-pressed", "false")
    assert _svg_viewbox(page) == pytest.approx(panned_view_box, rel=0.005)
    pan_tool.click()
    expect(pan_tool).to_have_attribute("aria-pressed", "true")
    assert _svg_viewbox(page) == pytest.approx(panned_view_box, rel=0.005)

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
    expect(page.locator("#add-spherical-shell")).to_be_hidden()
    for button_selector, test_id in [
        ("#add-point", "source-card-point-1"),
        ("#add-line-segment", "source-card-line-segment-1"),
        ("#add-ring", "source-card-ring-1"),
        ("#add-disk", "source-card-disk-1"),
    ]:
        page.locator(button_selector).click()
        expect(page.get_by_test_id(test_id)).to_be_visible()

    expect(page.get_by_test_id("source-count")).to_contain_text("4 个源")
    expect(page.get_by_test_id("source-card-spherical-shell-1")).to_have_count(0)
    expect(page.get_by_test_id("overlay-vector-layer")).to_have_attribute("data-vector-count", "0")
    expect(page.get_by_test_id("field-line-layer")).to_have_attribute("data-field-line-count", "0")
    page.locator("#toggle-field-lines").click()
    expect(page.get_by_test_id("field-line-layer")).to_have_attribute("data-enabled", "true")
    field_line_layer = page.get_by_test_id("field-line-layer")
    field_line_count = int(field_line_layer.get_attribute("data-field-line-count") or "0")
    assert field_line_count == 36
    expect(field_line_layer).to_have_attribute("data-target-line-count", "36")
    expect(field_line_layer).to_have_attribute("data-arrow-distance-cm", "5")
    expect(page.get_by_test_id("field-line-arrow-2d")).to_have_count(36)
    expect(page.get_by_test_id("overlay-summary")).to_contain_text("电场线")
    page.locator("#toggle-field-lines").click()
    page.get_by_role("button", name="3D").click()
    expect(page.locator("#add-infinite-plane")).to_be_visible()
    expect(page.locator("#add-spherical-shell")).to_be_visible()
    for button_selector, test_id in [
        ("#add-point", "source-card-point-1"),
        ("#add-line-segment", "source-card-line-segment-1"),
        ("#add-ring", "source-card-ring-1"),
        ("#add-disk", "source-card-disk-1"),
        ("#add-spherical-shell", "source-card-spherical-shell-1"),
    ]:
        page.locator(button_selector).click()
        expect(page.get_by_test_id(test_id)).to_be_visible()
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
    expect(page.get_by_test_id("overlay-vector-layer")).to_have_attribute("data-vector-count", "0")
    expect(page.get_by_test_id("overlay-summary")).to_contain_text("|E|")

    page.get_by_role("button", name="3D").click()
    expect(page.get_by_test_id("view-3d")).to_be_visible()
    expect(page.get_by_test_id("source-count")).to_contain_text("6 个源")
    expect(page.get_by_test_id("mode-label")).to_contain_text("3D")

    page.get_by_role("button", name="2D").click()
    expect(page.get_by_test_id("view-2d")).to_be_visible()
    expect(page.get_by_test_id("source-card-disk-1")).to_contain_text("带电圆盘 1")
    expect(page.get_by_test_id("source-card-spherical-shell-1")).to_have_count(0)
    expect(page.get_by_test_id("source-spherical-shell-2d-spherical-shell-1")).to_have_count(0)

    disk_style = page.get_by_test_id("source-disk-2d-disk-1").evaluate(
        """
        element => ({
          fill: getComputedStyle(element).fill,
          fillOpacity: getComputedStyle(element).fillOpacity,
          stroke: getComputedStyle(element).stroke,
        })
        """
    )
    assert disk_style["fill"] == "rgb(217, 45, 32)"
    assert disk_style["fillOpacity"] == "1"
    assert disk_style["stroke"] == "rgb(217, 45, 32)"

    page.locator("#preset-select").select_option("electric-dipole")
    page.locator("#preset-form button").click()
    expect(page.get_by_test_id("preset-status")).to_contain_text("已加载：Electric dipole")
    expect(page.get_by_test_id("source-count")).to_contain_text("2 个源")
    expect(page.get_by_test_id("source-card-dipole-positive")).to_contain_text("Positive pole")
    expect(page.get_by_test_id("quality-value")).to_contain_text("refined")
    expect(page.get_by_test_id("overlay-vector-layer")).to_have_attribute("data-vector-count", "0")
