from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, expect, sync_playwright

from em_workbench.app import app
from em_workbench.desktop import _bridge_bootstrap_script


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


def _set_source_number(page: Page, source_id: str, field: str, value: str) -> None:
    control = page.locator(f'[data-source-id="{source_id}"][data-field="{field}"]')
    control.fill(value)
    control.press("Tab")


def _add_point_charge(
    page: Page,
    *,
    x_cm: str = "-16",
    y_cm: str = "0",
    z_cm: str = "0",
    charge_c: str = "1e-9",
) -> None:
    page.locator("#point-source-x").fill(x_cm)
    page.locator("#point-source-y").fill(y_cm)
    if page.locator("#point-source-z").is_visible():
        page.locator("#point-source-z").fill(z_cm)
    page.locator("#point-source-charge").fill(charge_c)
    page.locator("#add-point").click()


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


def test_desktop_bridge_bootstrap_waits_for_document_root(page: Page) -> None:
    browser = page.context.browser
    assert browser is not None
    probe_context = browser.new_context()
    probe_page = probe_context.new_page()
    page_errors: list[str] = []
    probe_page.on("pageerror", lambda error: page_errors.append(str(error)))
    probe_page.add_init_script(_bridge_bootstrap_script())

    probe_page.goto("data:text/html,<html><body>probe</body></html>", wait_until="load")
    probe_page.wait_for_timeout(100)
    probe_context.close()

    assert page_errors == []


def test_browser_interaction_slice_keeps_state_across_2d_3d_toggle(page: Page) -> None:
    expect(page.get_by_role("heading", name="电磁工作台")).to_be_visible()
    expect(page.get_by_test_id("runtime-status")).to_contain_text("Three.js")
    expect(page.get_by_test_id("compute-backend")).to_contain_text("CPU")
    expect(page.get_by_test_id("compute-warmup")).to_contain_text("预热状态")
    expect(page.locator("#point-source-z-field")).to_be_hidden()

    _add_point_charge(page)
    page.locator("#add-line-segment").click()
    page.locator("#add-ring").click()

    expect(page.get_by_test_id("source-card-point-1")).to_contain_text("点电荷 1")
    expect(page.get_by_test_id("source-card-point-1")).to_have_attribute(
        "data-source-readonly",
        "true",
    )
    expect(page.locator('[data-source-id="point-1"][data-field="position.x"]')).to_have_count(0)
    expect(page.get_by_test_id("source-readout-point-1-position-x")).to_contain_text("-16")
    expect(page.get_by_test_id("source-readout-point-1-charge-c")).to_contain_text("1.00")
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
        """
        element => ({
            fill: getComputedStyle(element).fill,
            filter: getComputedStyle(element).filter,
            material: element.getAttribute("data-material"),
            finish: element.getAttribute("data-material-finish"),
        })
        """
    )
    assert "source-point-positive-gradient" in point_fill["fill"]
    assert point_fill["filter"] == "none"
    assert point_fill["material"] == "charge-orb"
    assert point_fill["finish"] == "internal-radial-glow"
    point_symbol = page.get_by_test_id("source-point-symbol-2d-point-1").evaluate(
        """
        node => ({
            symbol: node.getAttribute("data-charge-symbol"),
            centerX: Number(node.getAttribute("data-symbol-center-x")),
            centerY: Number(node.getAttribute("data-symbol-center-y")),
            halfLength: Number(node.getAttribute("data-symbol-half-length")),
            lineCount: node.querySelectorAll("line").length,
        })
        """
    )
    assert point_symbol["symbol"] == "+"
    assert point_symbol["centerX"] == pytest.approx(point_x)
    assert point_symbol["centerY"] == pytest.approx(point_y)
    assert point_symbol["halfLength"] == pytest.approx(point_radius * 0.32)
    assert point_symbol["halfLength"] < point_radius
    assert point_symbol["lineCount"] == 2
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
    assert ring_radius == 8
    expect(page.get_by_test_id("source-ring-2d-ring-1")).to_have_attribute(
        "data-display-diameter-cm",
        "16",
    )
    expect(page.get_by_test_id("source-ring-2d-ring-1")).to_have_attribute(
        "data-physical-radius-cm",
        "8",
    )
    expect(page.get_by_test_id("source-ring-2d-ring-1")).to_have_attribute(
        "data-visual-model",
        "hollow-ring",
    )
    ring_style = page.get_by_test_id("source-ring-2d-ring-1").evaluate(
        """
        element => ({
          fill: getComputedStyle(element).fill,
          fillOpacity: getComputedStyle(element).fillOpacity,
          stroke: getComputedStyle(element).stroke,
        })
        """
    )
    assert ring_style["fill"] == "none"
    assert ring_style["fillOpacity"] == "0"
    assert "source-fruit-positive-gradient" in ring_style["stroke"]
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
    expect(page.locator("#point-source-z-field")).to_be_visible()
    expect(page.get_by_test_id("source-count")).to_contain_text("0 个源")
    expect(page.get_by_test_id("probe-position")).to_contain_text("20")

    page.get_by_role("button", name="2D").click()
    expect(page.get_by_test_id("view-2d")).to_be_visible()
    expect(page.locator("#point-source-z-field")).to_be_hidden()
    expect(page.get_by_test_id("source-count")).to_contain_text("3 个源")
    expect(page.get_by_test_id("probe-position")).to_contain_text("22")
    expect(page.get_by_test_id("source-card-ring-1")).to_contain_text("带电圆环 1")


def test_browser_sources_use_fruit_glass_material(page: Page) -> None:
    for button_selector in ["#add-point", "#add-line-segment", "#add-ring", "#add-disk"]:
        page.locator(button_selector).click()

    material_metadata = page.evaluate(
        """
        () => ({
            filter: Boolean(document.querySelector("#source-fruit-glass-filter")),
            positiveGradient: Boolean(document.querySelector("#source-fruit-positive-gradient")),
            negativeGradient: Boolean(document.querySelector("#source-fruit-negative-gradient")),
            pointPositiveGradient: Boolean(
                document.querySelector("#source-point-positive-gradient")
            ),
            pointNegativeGradient: Boolean(
                document.querySelector("#source-point-negative-gradient")
            ),
            point: document.querySelector('[data-testid="source-point-2d-point-1"]')?.dataset,
            line: document.querySelector(
                '[data-testid="source-line-segment-2d-line-segment-1"]'
            )?.dataset,
            ring: document.querySelector('[data-testid="source-ring-2d-ring-1"]')?.dataset,
            disk: document.querySelector('[data-testid="source-disk-2d-disk-1"]')?.dataset,
            highlightCount: document.querySelectorAll(
                '[data-testid^="source-fruit-highlight-2d-"]'
            ).length,
            causticCount: document.querySelectorAll(
                '[data-testid^="source-fruit-caustic-2d-"]'
            ).length,
            rimCount: document.querySelectorAll(
                '[data-testid^="source-fruit-rim-2d-"]'
            ).length,
            refractCount: document.querySelectorAll(
                '[data-testid^="source-fruit-refract-2d-"]'
            ).length,
        })
        """
    )

    assert material_metadata["filter"]
    assert material_metadata["positiveGradient"]
    assert material_metadata["negativeGradient"]
    assert material_metadata["pointPositiveGradient"]
    assert material_metadata["pointNegativeGradient"]
    assert material_metadata["point"]["material"] == "charge-orb"
    assert material_metadata["point"]["materialFinish"] == "internal-radial-glow"
    for key in ["line", "ring", "disk"]:
        assert material_metadata[key]["material"] == "fruit-glass"
        assert material_metadata[key]["materialFinish"] == "translucent-caustic"
        assert material_metadata[key]["materialDepth"] == "layered-rind-lens"
    assert material_metadata["highlightCount"] >= 3
    assert material_metadata["causticCount"] >= 3
    assert material_metadata["rimCount"] >= 3
    assert material_metadata["refractCount"] >= 2


def test_browser_source_library_modules_are_collapsible_parameter_forms(page: Page) -> None:
    for test_id in [
        "source-module-point",
        "source-module-line-segment",
        "source-module-ring",
        "source-module-disk",
    ]:
        module = page.get_by_test_id(test_id)
        assert module.evaluate("node => node.tagName.toLowerCase()") == "details"

    module_contract = page.evaluate(
        """
        () => [
            ['source-module-point', 'point-source-form', 'add-point'],
            ['source-module-line-segment', 'line-segment-source-form', 'add-line-segment'],
            ['source-module-ring', 'ring-source-form', 'add-ring'],
            ['source-module-disk', 'disk-source-form', 'add-disk'],
        ].map(([testId, formId, buttonId]) => {
            const module = document.querySelector(`[data-testid="${testId}"]`);
            const form = document.querySelector(`#${formId}`);
            const button = document.querySelector(`#${buttonId}`);
            return {
                testId,
                open: module?.hasAttribute('open') ?? false,
                formInsideModule: Boolean(form && module?.contains(form)),
                headingInsideForm: Boolean(form?.querySelector('.source-form-heading')),
                miniGridInsideForm: Boolean(form?.querySelector('.mini-grid')),
                buttonInsideForm: Boolean(button && form?.contains(button)),
            };
        })
        """
    )
    assert module_contract == [
        {
            "testId": "source-module-point",
            "open": True,
            "formInsideModule": True,
            "headingInsideForm": True,
            "miniGridInsideForm": True,
            "buttonInsideForm": True,
        },
        {
            "testId": "source-module-line-segment",
            "open": True,
            "formInsideModule": True,
            "headingInsideForm": True,
            "miniGridInsideForm": True,
            "buttonInsideForm": True,
        },
        {
            "testId": "source-module-ring",
            "open": True,
            "formInsideModule": True,
            "headingInsideForm": True,
            "miniGridInsideForm": True,
            "buttonInsideForm": True,
        },
        {
            "testId": "source-module-disk",
            "open": True,
            "formInsideModule": True,
            "headingInsideForm": True,
            "miniGridInsideForm": True,
            "buttonInsideForm": True,
        },
    ]

    page.locator("#source-module-line-segment summary").click()
    expect(page.get_by_test_id("source-module-line-segment")).not_to_have_attribute("open", "")
    page.locator("#source-module-line-segment summary").click()
    expect(page.get_by_test_id("source-module-line-segment")).to_have_attribute("open", "")
    page.locator("#line-segment-source-x").fill("3")
    page.locator("#line-segment-source-y").fill("5")
    page.locator("#line-segment-source-orientation-x").fill("0")
    page.locator("#line-segment-source-orientation-y").fill("1")
    page.locator("#line-segment-source-length").fill("12")
    page.locator("#line-segment-source-charge").fill("-2.5e-9")
    page.locator("#add-line-segment").click()

    expect(page.get_by_test_id("source-card-line-segment-1")).to_be_visible()
    expect(page.locator('[data-source-id="line-segment-1"][data-field="position.x"]')).to_have_value("0.03")
    expect(page.locator('[data-source-id="line-segment-1"][data-field="position.y"]')).to_have_value("0.05")
    expect(page.locator('[data-source-id="line-segment-1"][data-field="orientation.x"]')).to_have_value("0")
    expect(page.locator('[data-source-id="line-segment-1"][data-field="orientation.y"]')).to_have_value("1")
    expect(page.locator('[data-source-id="line-segment-1"][data-field="length_m"]')).to_have_value("0.12")
    expect(page.locator('[data-source-id="line-segment-1"][data-field="charge_c"]')).to_have_value("-2.5e-9")

    expect(page.get_by_test_id("source-module-ring")).to_have_attribute("open", "")
    page.locator("#ring-source-x").fill("-2")
    page.locator("#ring-source-y").fill("4")
    page.locator("#ring-source-radius").fill("7")
    page.locator("#ring-source-charge").fill("3e-9")
    page.locator("#add-ring").click()

    expect(page.get_by_test_id("source-card-ring-1")).to_be_visible()
    expect(page.locator('[data-source-id="ring-1"][data-field="position.x"]')).to_have_value("-0.02")
    expect(page.locator('[data-source-id="ring-1"][data-field="position.y"]')).to_have_value("0.04")
    expect(page.locator('[data-source-id="ring-1"][data-field="normal.x"]')).to_have_value("0")
    expect(page.locator('[data-source-id="ring-1"][data-field="normal.y"]')).to_have_value("0")
    expect(page.locator('[data-source-id="ring-1"][data-field="radius_m"]')).to_have_value("0.07")
    expect(page.locator('[data-source-id="ring-1"][data-field="charge_c"]')).to_have_value("3e-9")

    expect(page.get_by_test_id("source-module-disk")).to_have_attribute("open", "")
    page.locator("#disk-source-y").fill("-6")
    page.locator("#disk-source-radius").fill("9")
    page.locator("#disk-source-charge").fill("-4e-9")
    page.locator("#add-disk").click()

    expect(page.get_by_test_id("source-card-disk-1")).to_be_visible()
    expect(page.locator('[data-source-id="disk-1"][data-field="position.y"]')).to_have_value("-0.06")
    expect(page.locator('[data-source-id="disk-1"][data-field="normal.x"]')).to_have_value("0")
    expect(page.locator('[data-source-id="disk-1"][data-field="normal.y"]')).to_have_value("0")
    expect(page.locator('[data-source-id="disk-1"][data-field="radius_m"]')).to_have_value("0.09")
    expect(page.locator('[data-source-id="disk-1"][data-field="charge_c"]')).to_have_value("-4e-9")


def test_browser_views_use_fixed_ten_meter_centimeter_grid(page: Page) -> None:
    _add_point_charge(page, x_cm="8", y_cm="-8")

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


def test_browser_field_lines_use_global_display_cap_for_same_sign_charges(page: Page) -> None:
    _add_point_charge(page, x_cm="-11", y_cm="0", charge_c="1e-9")
    _add_point_charge(page, x_cm="11", y_cm="0", charge_c="1e-9")

    page.locator("#toggle-field-lines").click()
    field_line_layer = page.get_by_test_id("field-line-layer")
    expect(field_line_layer).to_have_attribute(
        "data-display-strategy",
        "uniform-charge-angle-field-tangent",
    )
    expect(field_line_layer).to_have_attribute("data-candidates-per-point-charge", "48")
    expect(field_line_layer).to_have_attribute("data-target-total-charge-rays", "96")
    expect(field_line_layer).to_have_attribute("data-display-max-line-count", "120")
    expect(field_line_layer).to_have_attribute("data-target-line-count", "120")
    expect(field_line_layer).to_have_attribute("data-conflict-filter", "display-spatial")
    candidate_count = int(field_line_layer.get_attribute("data-candidate-line-count") or "0")
    raw_count = int(field_line_layer.get_attribute("data-raw-line-count") or "0")
    display_count = int(field_line_layer.get_attribute("data-field-line-count") or "0")
    assert candidate_count == 96
    assert 0 < raw_count <= candidate_count
    assert 48 <= display_count <= 96
    expect(page.get_by_test_id("field-line-arrow-2d")).to_have_count(display_count)
    source_counts = page.get_by_test_id("field-line-2d").evaluate_all(
        """
        nodes => nodes.reduce((counts, node) => {
            const sourceId = node.getAttribute("data-field-start-id") === "infinity"
                ? node.getAttribute("data-field-end-id")
                : node.getAttribute("data-field-start-id");
            counts[sourceId] = (counts[sourceId] || 0) + 1;
            return counts;
        }, {})
        """
    )
    assert set(source_counts) == {"point-1", "point-2"}
    assert sum(source_counts.values()) == display_count
    assert all(count > 0 for count in source_counts.values())


def test_browser_field_lines_geogebra_like_dedupes_opposite_charge_pairs(page: Page) -> None:
    _add_point_charge(page, x_cm="-11", y_cm="0", charge_c="1e-9")
    _add_point_charge(page, x_cm="11", y_cm="0", charge_c="-2e-9")

    page.locator("#toggle-field-lines").click()
    field_line_layer = page.get_by_test_id("field-line-layer")
    expect(field_line_layer).to_have_attribute(
        "data-display-strategy",
        "uniform-charge-angle-field-tangent",
    )
    expect(field_line_layer).to_have_attribute("data-candidates-per-point-charge", "48")
    expect(field_line_layer).to_have_attribute("data-target-total-charge-rays", "96")
    expect(field_line_layer).to_have_attribute("data-boundary-candidate-count", "0")
    expect(field_line_layer).to_have_attribute("data-display-max-line-count", "120")
    expect(field_line_layer).to_have_attribute("data-target-line-count", "120")
    expect(field_line_layer).to_have_attribute("data-conflict-filter", "display-spatial")

    candidate_count = int(field_line_layer.get_attribute("data-candidate-line-count") or "0")
    display_count = int(field_line_layer.get_attribute("data-field-line-count") or "0")
    raw_count = int(field_line_layer.get_attribute("data-raw-line-count") or "0")
    paired_count = int(field_line_layer.get_attribute("data-paired-line-count") or "0")
    display_rejected = int(
        field_line_layer.get_attribute("data-display-conflict-rejected-line-count") or "0"
    )
    display_deduped = int(field_line_layer.get_attribute("data-display-deduped-line-count") or "0")
    assert candidate_count == 96
    assert 0 < raw_count <= candidate_count
    assert 40 <= display_count <= 96
    assert 0 < paired_count <= 72
    assert display_rejected + display_deduped > 0
    expect(page.get_by_test_id("field-line-arrow-2d")).to_have_count(display_count)

    topology_counts = page.get_by_test_id("field-line-2d").evaluate_all(
        """
        nodes => nodes.reduce((counts, node) => {
            const topology = node.getAttribute("data-field-topology");
            const startId = node.getAttribute("data-field-start-id");
            const endId = node.getAttribute("data-field-end-id");
            const key = `${topology}:${startId}->${endId}`;
            counts[key] = (counts[key] || 0) + 1;
            return counts;
        }, {})
        """
    )
    assert 0 < topology_counts["charge-to-charge:point-1->point-2"] <= 72
    assert topology_counts["infinity-to-charge:infinity->point-2"] > 0
    assert "charge-to-charge:point-2->point-1" not in topology_counts

    rendered_metadata = page.get_by_test_id("field-line-2d").evaluate_all(
        """
        nodes => nodes.map((node) => ({
            method: node.getAttribute("data-trace-method"),
            pathModel: node.getAttribute("data-path-model"),
            endpointClass: node.getAttribute("data-endpoint-class"),
            stopReason: node.getAttribute("data-stop-reason"),
            path: node.getAttribute("d"),
        }))
        """
    )
    assert all(item["method"] == "adaptive-rk4" for item in rendered_metadata)
    assert all(
        item["pathModel"] == "verified-rk4-bounded-catmull-rom"
        for item in rendered_metadata
    )
    assert all(
        item["endpointClass"] in {"opposite-charge", "infinity"}
        for item in rendered_metadata
    )
    assert all(
        item["stopReason"] in {"opposite-charge", "view-boundary"}
        for item in rendered_metadata
    )
    assert all(" C " in item["path"] for item in rendered_metadata)


def test_browser_field_lines_are_loaded_from_backend(page: Page) -> None:
    requests: list[str] = []
    page.on("request", lambda request: requests.append(request.url))

    _add_point_charge(page)
    page.locator("#toggle-field-lines").click()
    expect(page.get_by_test_id("field-line-layer")).to_have_attribute(
        "data-compute-source",
        "backend",
    )
    expect(page.get_by_test_id("field-line-layer")).to_have_attribute(
        "data-request-current",
        "true",
    )

    assert any(url.endswith("/api/field/lines") for url in requests)


@pytest.mark.parametrize(
    ("button_selector", "source_id"),
    [
        ("#add-line-segment", "line-segment-1"),
        ("#add-ring", "ring-1"),
        ("#add-disk", "disk-1"),
    ],
)
def test_browser_field_lines_render_for_integrated_sources(
    page: Page,
    button_selector: str,
    source_id: str,
) -> None:
    page.locator(button_selector).click()

    page.locator("#toggle-field-lines").click()
    page.wait_for_function(
        """
        () => {
            const layer = document.querySelector('[data-testid="field-line-layer"]');
            return layer?.dataset.requestCurrent === "true" &&
                Number(layer.dataset.fieldLineCount || 0) > 0;
        }
        """
    )

    field_line_layer = page.get_by_test_id("field-line-layer")
    expect(field_line_layer).to_have_attribute("data-compute-source", "backend")
    display_count = int(field_line_layer.get_attribute("data-field-line-count") or "0")
    candidate_count = int(field_line_layer.get_attribute("data-candidate-line-count") or "0")
    raw_count = int(field_line_layer.get_attribute("data-raw-line-count") or "0")
    assert 0 < display_count <= 120
    assert candidate_count > 0
    assert raw_count > 0

    source_ids = page.get_by_test_id("field-line-2d").evaluate_all(
        """
        nodes => [...new Set(nodes.map((node) => {
            return node.getAttribute("data-field-start-id") === "infinity"
                ? node.getAttribute("data-field-end-id")
                : node.getAttribute("data-field-start-id");
        }))]
        """
    )
    assert source_ids == [source_id]
    expect(page.get_by_test_id("field-line-arrow-2d")).to_have_count(display_count)


def test_browser_field_lines_remain_balanced_for_mixed_finite_sources(page: Page) -> None:
    for button_selector in ["#add-point", "#add-line-segment", "#add-ring", "#add-disk"]:
        page.locator(button_selector).click()

    page.locator("#toggle-field-lines").click()
    page.wait_for_function(
        """
        () => {
            const layer = document.querySelector('[data-testid="field-line-layer"]');
            return layer?.dataset.requestCurrent === "true" &&
                Number(layer.dataset.fieldLineCount || 0) >= 12;
        }
        """
    )

    source_counts = page.get_by_test_id("field-line-2d").evaluate_all(
        """
        nodes => nodes.reduce((counts, node) => {
            const sourceId = node.getAttribute("data-field-start-id") === "infinity"
                ? node.getAttribute("data-field-end-id")
                : node.getAttribute("data-field-start-id");
            counts[sourceId] = (counts[sourceId] || 0) + 1;
            return counts;
        }, {})
        """
    )
    expected_source_ids = {"point-1", "line-segment-1", "ring-1", "disk-1"}
    assert set(source_counts) == expected_source_ids
    counts = list(source_counts.values())
    assert min(counts) >= 4
    assert max(counts) / min(counts) <= 2

    path_geometry = page.evaluate(
        """
        () => {
            const samplePath = (path) => {
                const totalLength = path.getTotalLength();
                const sampleCount = Math.max(8, Math.ceil(totalLength / 2));
                return Array.from({ length: sampleCount + 1 }, (_, index) => {
                    const point = path.getPointAtLength((totalLength * index) / sampleCount);
                    return { x: point.x, y: point.y };
                });
            };
            const cross = (a, b) => a.x * b.y - a.y * b.x;
            const intersection = (a, b, c, d) => {
                const r = { x: b.x - a.x, y: b.y - a.y };
                const s = { x: d.x - c.x, y: d.y - c.y };
                const denominator = cross(r, s);
                if (Math.abs(denominator) < 1e-9) {
                    return null;
                }
                const ac = { x: c.x - a.x, y: c.y - a.y };
                const t = cross(ac, s) / denominator;
                const u = cross(ac, r) / denominator;
                if (t <= 1e-5 || t >= 1 - 1e-5 || u <= 1e-5 || u >= 1 - 1e-5) {
                    return null;
                }
                return {
                    x: a.x + (b.x - a.x) * t,
                    y: a.y + (b.y - a.y) * t,
                };
            };
            const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);
            const pathSegments = [...document.querySelectorAll('[data-testid="field-line-2d"]')]
                .map((path, pathIndex) => {
                    const points = samplePath(path);
                    return points.slice(1).map((point, index) => ({
                        pathIndex,
                        start: points[index],
                        end: point,
                    }));
                });
            const intersections = [];
            for (let lineA = 0; lineA < pathSegments.length; lineA += 1) {
                for (let lineB = lineA + 1; lineB < pathSegments.length; lineB += 1) {
                    for (const segmentA of pathSegments[lineA]) {
                        for (const segmentB of pathSegments[lineB]) {
                            const point = intersection(
                                segmentA.start,
                                segmentA.end,
                                segmentB.start,
                                segmentB.end,
                            );
                            if (!point) {
                                continue;
                            }
                            const endpointDistance = Math.min(
                                distance(point, segmentA.start),
                                distance(point, segmentA.end),
                                distance(point, segmentB.start),
                                distance(point, segmentB.end),
                            );
                            if (endpointDistance > 1.5) {
                                intersections.push(point);
                            }
                        }
                    }
                }
            }
            return {
                intersectionCount: intersections.length,
                sampledPathCount: pathSegments.length,
            };
        }
        """
    )
    assert path_geometry["sampledPathCount"] >= 12
    assert path_geometry["intersectionCount"] == 0


def test_browser_discards_stale_field_line_response_after_zoom(page: Page) -> None:
    page.add_init_script(
        """
        (() => {
          const originalFetch = window.fetch.bind(window);
          window.__fieldLineDelayedRequestIds = [];
          window.fetch = async (...args) => {
            const [input, init] = args;
            if (String(input).endsWith("/api/field/lines")) {
              const request = JSON.parse(init.body);
              const requestIndex = window.__fieldLineDelayedRequestIds.length;
              window.__fieldLineDelayedRequestIds.push(request.request_id);
              const response = await originalFetch(...args);
              await new Promise((resolve) => {
                window.setTimeout(resolve, requestIndex === 0 ? 500 : 10);
              });
              return response;
            }
            return originalFetch(...args);
          };
        })();
        """
    )
    page.reload(wait_until="networkidle")
    _add_point_charge(page)
    page.locator("#toggle-field-lines").click()
    page.wait_for_function("() => window.__fieldLineDelayedRequestIds.length >= 1")
    page.get_by_test_id("view-2d").hover()
    page.mouse.wheel(0, -240)
    page.wait_for_function("() => window.__fieldLineDelayedRequestIds.length >= 2")
    page.wait_for_timeout(700)

    request_ids = page.evaluate("() => window.__fieldLineDelayedRequestIds")
    field_line_layer = page.get_by_test_id("field-line-layer")
    expect(field_line_layer).to_have_attribute("data-request-current", "true")
    expect(field_line_layer).to_have_attribute("data-rendered-request-id", request_ids[1])


def test_browser_equipotential_lines_use_auto_delta_v_and_probe_potential(page: Page) -> None:
    _add_point_charge(page, x_cm="-11", y_cm="0", charge_c="1e-9")
    _add_point_charge(page, x_cm="11", y_cm="0", charge_c="-1e-9")

    page.locator("#toggle-equipotential-lines").click()
    equipotential_layer = page.get_by_test_id("equipotential-layer")
    expect(equipotential_layer).to_have_attribute("data-enabled", "true")
    expect(equipotential_layer).to_have_attribute("data-method", "marching-squares")
    expect(equipotential_layer).to_have_attribute("data-linking", "segment-graph")
    expect(equipotential_layer).not_to_have_attribute("data-auto-delta-v", "0")
    equipotential_count = int(equipotential_layer.get_attribute("data-equipotential-count") or "0")
    label_count = int(equipotential_layer.get_attribute("data-equipotential-label-count") or "0")
    level_count = int(equipotential_layer.get_attribute("data-level-count") or "0")
    assert 0 < equipotential_count <= 140
    assert 0 < label_count <= 48
    assert 0 < level_count <= 32
    expect(page.get_by_test_id("equipotential-line-2d")).to_have_count(equipotential_count)
    expect(page.get_by_test_id("equipotential-label-2d")).to_have_count(label_count)
    expect(page.get_by_test_id("equipotential-label-layer")).to_have_attribute(
        "data-label-style",
        "contour-inline",
    )
    path_models = page.get_by_test_id("equipotential-line-2d").evaluate_all(
        """
        nodes => nodes.map((node) => ({
            model: node.getAttribute("data-path-model"),
            path: node.getAttribute("d"),
            value: Number(node.getAttribute("data-potential-v")),
        }))
        """
    )
    assert all(item["model"] == "marching-squares-catmull-rom" for item in path_models)
    assert all(" C " in item["path"] for item in path_models)
    assert all(abs(item["value"]) >= 0 for item in path_models)
    label_metrics = page.get_by_test_id("equipotential-label-2d").evaluate_all(
        """
        nodes => {
            const boxes = nodes.map((node) => {
                const rect = node.getBoundingClientRect();
                return {
                    text: node.getAttribute("data-label-text"),
                    transform: node.getAttribute("transform"),
                    width: rect.width,
                    height: rect.height,
                    left: rect.left,
                    right: rect.right,
                    top: rect.top,
                    bottom: rect.bottom,
                };
            });
            let overlapPairs = 0;
            for (let i = 0; i < boxes.length; i += 1) {
                for (let j = i + 1; j < boxes.length; j += 1) {
                    const first = boxes[i];
                    const second = boxes[j];
                    const separated = first.right < second.left ||
                        second.right < first.left ||
                        first.bottom < second.top ||
                        second.bottom < first.top;
                    if (!separated) {
                        overlapPairs += 1;
                    }
                }
            }
            return {
                boxes,
                overlapPairs,
            };
        }
        """
    )
    assert label_metrics["overlapPairs"] == 0
    assert all("V" in item["text"] for item in label_metrics["boxes"])
    assert all("NaN" not in item["transform"] for item in label_metrics["boxes"])
    assert all(item["width"] > 0 and item["height"] > 0 for item in label_metrics["boxes"])

    page.locator("#probe-x").fill("0")
    page.locator("#probe-y").fill("3")
    page.locator("#probe-submit").click()
    expect(page.get_by_test_id("potential-value")).to_contain_text("V")


def test_browser_motion_playback_preserves_complex_field_line_layer(page: Page) -> None:
    _add_point_charge(page, x_cm="-11", y_cm="0", charge_c="1e-9")
    _add_point_charge(page, x_cm="11", y_cm="0", charge_c="-1e-9")
    page.locator("#toggle-field-lines").click()
    expect(page.get_by_test_id("field-line-2d")).not_to_have_count(0)
    page.wait_for_timeout(500)

    page.evaluate(
        """
        () => {
            window.__fieldLineReference = document.querySelector('[data-testid="field-line-2d"]');
        }
        """
    )
    page.locator("#motion-steps").fill("12")
    page.locator("#motion-dt").fill("0.001")
    page.locator("#motion-run").click()
    page.wait_for_function(
        """
        () => Number(
            document.querySelector('[data-testid="motion-layer-2d"]')?.dataset.pointCount || 0
        ) > 1
        """
    )

    assert page.evaluate(
        """
        () => window.__fieldLineReference ===
            document.querySelector('[data-testid="field-line-2d"]')
        """
    )
    expect(page.get_by_test_id("motion-particle-2d")).to_be_visible()
    motion_style = page.get_by_test_id("motion-particle-2d").evaluate(
        """
        node => {
            const trail = document.querySelector('.motion-trail');
            const group = document.querySelector('[data-testid="motion-particle-group-2d"]');
            const particleStyle = getComputedStyle(node);
            const trailStyle = getComputedStyle(trail);
            return {
                particleFill: particleStyle.fill,
                particleStroke: particleStyle.stroke,
                particleRadius: node.getAttribute('r'),
                particleVisualRadius: node.getAttribute('data-visual-radius-cm'),
                particleStrokeWidth: particleStyle.strokeWidth,
                particleFilter: particleStyle.filter,
                particleMaterial: node.getAttribute('data-material'),
                hasParticleSymbol: Boolean(
                    document.querySelector('[data-testid="motion-particle-symbol-2d"]')
                ),
                particleGroupRatio: group.getAttribute('data-radius-ratio-to-static'),
                trailStroke: trailStyle.stroke,
                trailWidth: trailStyle.strokeWidth,
            };
        }
        """
    )
    assert "source-point-negative-gradient" in motion_style["particleFill"]
    assert motion_style["particleStroke"] == "rgba(207, 248, 255, 0.9)"
    assert float(motion_style["particleRadius"]) == pytest.approx(0.1)
    assert float(motion_style["particleVisualRadius"]) == pytest.approx(0.1)
    assert motion_style["particleStrokeWidth"] == "0.012px"
    assert motion_style["particleFilter"] == "none"
    assert motion_style["particleMaterial"] == "charge-orb"
    assert motion_style["hasParticleSymbol"] is False
    assert motion_style["particleGroupRatio"] == "0.2"
    assert motion_style["trailStroke"] == "rgb(57, 255, 20)"
    assert motion_style["trailWidth"] == "0.22px"


def test_browser_rutherford_scattering_panel_renders_tracks(page: Page) -> None:
    expect(page.get_by_role("heading", name="卢瑟福散射实验")).to_be_visible()
    expect(page.get_by_test_id("scattering-state")).to_contain_text("待命")
    expect(page.locator("#scatter-run")).to_contain_text("运行散射")
    expect(page.locator("#scatter-center-y")).to_have_value("0")

    page.locator("#scatter-particles").fill("5")
    page.locator("#scatter-half-width").fill("4")
    page.locator("#scatter-center-y").fill("2")
    page.locator("#scatter-run").click()
    page.wait_for_function(
        """
        () => {
            const layer = document.querySelector('[data-testid="scattering-layer-2d"]');
            return Number(layer?.dataset.trackCount || 0) === 5 &&
                document.querySelectorAll('[data-testid="scattering-particle-2d"]').length === 5;
        }
        """
    )

    layer = page.get_by_test_id("scattering-layer-2d")
    expect(layer).to_have_attribute("data-track-count", "5")
    expect(page.get_by_test_id("scattering-nucleus-2d")).to_be_visible()
    expect(page.locator(".scattering-nucleus-label")).to_have_count(0)
    expect(page.get_by_test_id("scattering-particle-2d")).to_have_count(5)
    expect(page.get_by_test_id("scattering-track-2d")).to_have_count(0)
    particle_frame_index = int(
        page.get_by_test_id("scattering-particle-layer-2d").get_attribute(
            "data-frame-index"
        )
        or "-1"
    )
    assert particle_frame_index >= 0
    page.wait_for_function(
        """
        () => document.querySelectorAll('[data-testid="scattering-track-2d"]').length === 5
        """
    )
    expect(page.get_by_test_id("scattering-track-2d").nth(0)).to_have_attribute(
        "data-impact-cm",
        "-2.000",
    )
    expect(page.get_by_test_id("scattering-track-2d").nth(4)).to_have_attribute(
        "data-impact-cm",
        "6.000",
    )
    particle_fill = page.get_by_test_id("scattering-particle-2d").first.evaluate(
        "element => getComputedStyle(element).fill"
    )
    assert particle_fill == "rgb(22, 163, 74)"
    assert float(layer.get_attribute("data-max-angle-deg") or "0") > 90
    assert int(layer.get_attribute("data-backscatter-count") or "0") >= 1
    expect(page.get_by_test_id("scattering-readout")).to_contain_text("个粒子")

    initial_path = page.get_by_test_id("scattering-track-2d").first.get_attribute("d")
    page.wait_for_function(
        """
        (initialPath) => document.querySelector('[data-testid="scattering-track-2d"]')
            ?.getAttribute('d') !== initialPath
        """,
        arg=initial_path,
    )


def test_browser_scattering_uses_current_scene_sources(page: Page) -> None:
    page.locator("#add-ring").click()
    page.locator("#scatter-particles").fill("3")
    page.locator("#scatter-half-width").fill("3")
    page.locator("#scatter-center-y").fill("0")
    page.locator("#scatter-max-steps").fill("800")

    with page.expect_request(
        lambda request: request.url.endswith("/api/scattering/evaluate")
    ) as request_info:
        page.locator("#scatter-run").click()
    payload = json.loads(request_info.value.post_data or "{}")

    assert "scene" in payload
    assert "nucleus" not in payload
    assert payload["scene"]["sources"][0]["kind"] == "ring"
    assert payload["quality"] == "preview"

    page.wait_for_function(
        """
        () => document.querySelector('[data-testid="scattering-layer-2d"]')
            ?.dataset.fieldModel === "scene-sources"
        """
    )
    layer = page.get_by_test_id("scattering-layer-2d")
    expect(layer).to_have_attribute("data-field-model", "scene-sources")
    expect(layer).to_have_attribute("data-target-source-count", "1")
    expect(page.get_by_test_id("scattering-nucleus-2d")).to_have_count(0)


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
    expect(field_line_layer).to_have_attribute("data-request-current", "true")
    field_line_count = int(field_line_layer.get_attribute("data-field-line-count") or "0")
    assert 0 < field_line_count <= 120
    expect(field_line_layer).to_have_attribute(
        "data-display-strategy",
        "uniform-charge-angle-field-tangent",
    )
    expect(field_line_layer).to_have_attribute("data-candidates-per-point-charge", "26")
    expect(field_line_layer).to_have_attribute("data-candidates-per-charged-source", "26")
    expect(field_line_layer).to_have_attribute("data-target-total-charge-rays", "96")
    expect(field_line_layer).to_have_attribute("data-display-max-line-count", "120")
    expect(field_line_layer).to_have_attribute("data-target-line-count", "120")
    candidate_field_line_count = int(
        field_line_layer.get_attribute("data-candidate-line-count") or "0"
    )
    assert candidate_field_line_count == 104
    raw_field_line_count = int(field_line_layer.get_attribute("data-raw-line-count") or "0")
    assert 0 < raw_field_line_count <= candidate_field_line_count
    expect(field_line_layer).to_have_attribute("data-arrow-placement", "arc-fraction")
    expect(field_line_layer).to_have_attribute("data-arrow-fraction-base", "0.42")
    expect(page.get_by_test_id("field-line-arrow-2d")).to_have_count(field_line_count)
    line_trace_metadata = page.get_by_test_id("field-line-2d").evaluate_all(
        """
        nodes => nodes.map((node) => ({
            method: node.getAttribute("data-trace-method"),
            pathModel: node.getAttribute("data-path-model"),
            endpointClass: node.getAttribute("data-endpoint-class"),
            stopReason: node.getAttribute("data-stop-reason"),
            path: node.getAttribute("d"),
            markerEnd: node.getAttribute("marker-end"),
            finitePath: [...(node.getAttribute("d").matchAll(/-?\\d+(?:\\.\\d+)?/g))]
                .every((match) => Number.isFinite(Number(match[0]))),
        }))
        """
    )
    assert all(item["method"] == "adaptive-rk4" for item in line_trace_metadata)
    assert all(
        item["pathModel"] == "verified-rk4-bounded-catmull-rom"
        for item in line_trace_metadata
    )
    assert all(item["endpointClass"] != "numerical-artifact" for item in line_trace_metadata)
    assert all(
        item["stopReason"] not in {"direction-reversal", "self-approach"}
        for item in line_trace_metadata
    )
    assert all(item["finitePath"] for item in line_trace_metadata)
    assert all(" C " in item["path"] for item in line_trace_metadata)
    assert all(item["markerEnd"] is None for item in line_trace_metadata)
    arrow_metadata = page.get_by_test_id("field-line-arrow-2d").evaluate_all(
        """
        nodes => nodes.map((node) => ({
            tagName: node.tagName.toLowerCase(),
            onLine: node.getAttribute("data-arrow-on-line"),
            sizePx: node.getAttribute("data-arrow-size-px"),
            direction: node.getAttribute("data-arrow-direction"),
            placement: node.getAttribute("data-arrow-placement"),
            fraction: Number(node.getAttribute("data-arrow-fraction")),
        }))
        """
    )
    assert all(item["tagName"] == "path" for item in arrow_metadata)
    assert all(item["onLine"] == "true" for item in arrow_metadata)
    assert all(item["sizePx"] == "9" for item in arrow_metadata)
    assert all(item["direction"] == "field" for item in arrow_metadata)
    assert all(item["placement"] == "arc-fraction" for item in arrow_metadata)
    assert all(0.22 <= item["fraction"] <= 0.72 for item in arrow_metadata)
    arrow_geometry = page.evaluate(
        """
        () => {
            const parsePoints = (path) => {
                const numbers = [...path.matchAll(/-?\\d+(?:\\.\\d+)?/g)]
                    .map((match) => Number(match[0]));
                const points = [];
                for (let index = 0; index < numbers.length; index += 2) {
                    points.push({ x: numbers[index], y: numbers[index + 1] });
                }
                return points;
            };
            const distanceToPath = (point, path) => {
                const totalLength = path.getTotalLength();
                const samples = Math.max(240, Math.ceil(totalLength * 100));
                let nearest = Infinity;
                for (let index = 0; index <= samples; index += 1) {
                    const sample = path.getPointAtLength((totalLength * index) / samples);
                    nearest = Math.min(nearest, Math.hypot(point.x - sample.x, point.y - sample.y));
                }
                return nearest;
            };
            const toScreen = (svg, point) => {
                const svgPoint = svg.createSVGPoint();
                svgPoint.x = point.x;
                svgPoint.y = point.y;
                const screenPoint = svgPoint.matrixTransform(svg.getScreenCTM());
                return { x: screenPoint.x, y: screenPoint.y };
            };
            const lines = [...document.querySelectorAll('[data-testid="field-line-2d"]')];
            const arrows = [...document.querySelectorAll('[data-testid="field-line-arrow-2d"]')];
                const metrics = arrows.map((arrow, index) => {
                    const arrowPoints = parsePoints(arrow.getAttribute("d"));
                    const tipDistance = distanceToPath(arrowPoints[0], lines[index]);
                    const svg = arrow.ownerSVGElement;
                const tip = toScreen(svg, arrowPoints[0]);
                const left = toScreen(svg, arrowPoints[1]);
                const right = toScreen(svg, arrowPoints[2]);
                const base = { x: (left.x + right.x) / 2, y: (left.y + right.y) / 2 };
                return {
                    tipDistance,
                    lengthPx: Math.hypot(tip.x - base.x, tip.y - base.y),
                    widthPx: Math.hypot(left.x - right.x, left.y - right.y),
                };
            });
            return {
                maxTipDistance: Math.max(...metrics.map((metric) => metric.tipDistance)),
                minLengthPx: Math.min(...metrics.map((metric) => metric.lengthPx)),
                maxLengthPx: Math.max(...metrics.map((metric) => metric.lengthPx)),
                minWidthPx: Math.min(...metrics.map((metric) => metric.widthPx)),
                maxWidthPx: Math.max(...metrics.map((metric) => metric.widthPx)),
            };
        }
        """
    )
    assert arrow_geometry["maxTipDistance"] < 0.01
    assert 8 <= arrow_geometry["minLengthPx"] <= arrow_geometry["maxLengthPx"] <= 10
    assert 6 <= arrow_geometry["minWidthPx"] <= arrow_geometry["maxWidthPx"] <= 8
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
    assert "source-fruit-positive-gradient" in disk_style["fill"]
    assert disk_style["fillOpacity"] == "0.82"
    assert disk_style["stroke"] == "rgb(217, 45, 32)"

    page.locator("#preset-select").select_option("electric-dipole")
    page.locator("#preset-form button").click()
    expect(page.get_by_test_id("preset-status")).to_contain_text("已加载：Electric dipole")
    expect(page.get_by_test_id("source-count")).to_contain_text("2 个源")
    expect(page.get_by_test_id("source-card-dipole-positive")).to_contain_text("Positive pole")
    expect(page.get_by_test_id("quality-value")).to_contain_text("refined")
    expect(page.get_by_test_id("overlay-vector-layer")).to_have_attribute("data-vector-count", "0")
