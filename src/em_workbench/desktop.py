"""Standalone desktop entry point for EM Workbench."""

from __future__ import annotations

import sys
from pathlib import Path

from em_workbench.app import WEB_ROOT
from em_workbench.desktop_bridge import WorkbenchDesktopBridge


def _retain_desktop_objects(view: object, channel: object, bridge: object) -> None:
    """Keep Qt bridge objects alive for the lifetime of the desktop view."""
    view._em_workbench_channel = channel
    view._em_workbench_bridge = bridge


def main(argv: list[str] | None = None) -> int:
    """Launch the desktop workbench window."""
    args = list(sys.argv if argv is None else argv)
    try:
        from PySide6.QtCore import QObject, QUrl, Slot
        from PySide6.QtWebChannel import QWebChannel
        from PySide6.QtWebEngineCore import QWebEngineScript
        from PySide6.QtWebEngineWidgets import QWebEngineView
        from PySide6.QtWidgets import QApplication
    except ImportError as error:
        raise SystemExit(
            "Desktop dependencies are not installed. Run "
            "'.\\.tools\\uv\\uv.exe sync --extra desktop' before launching the desktop app."
        ) from error

    if "--check" in args:
        print("desktop runtime ok")
        return 0

    class QtWorkbenchBridge(QObject):
        def __init__(self) -> None:
            super().__init__()
            self._bridge = WorkbenchDesktopBridge()

        @Slot(str, result=str)
        def config(self, payload: str = "") -> str:
            return self._bridge.config(payload)

        @Slot(str, result=str)
        def listPresets(self, payload: str = "") -> str:
            return self._bridge.list_presets(payload)

        @Slot(str, result=str)
        def getPreset(self, payload: str) -> str:
            return self._bridge.get_preset(payload)

        @Slot(str, result=str)
        def evaluateField(self, payload: str) -> str:
            return self._bridge.evaluate_field(payload)

        @Slot(str, result=str)
        def evaluateTrajectory(self, payload: str) -> str:
            return self._bridge.evaluate_trajectory(payload)

    app = QApplication(args)
    view = QWebEngineView()
    view.setWindowTitle("EM Workbench - 电磁工作台")
    view.resize(1440, 920)

    channel = QWebChannel(view.page())
    bridge = QtWorkbenchBridge()
    channel.registerObject("emWorkbenchBridge", bridge)
    view.page().setWebChannel(channel)
    _retain_desktop_objects(view, channel, bridge)

    bootstrap = QWebEngineScript()
    bootstrap.setName("em-workbench-bridge-bootstrap")
    bootstrap.setInjectionPoint(QWebEngineScript.InjectionPoint.DocumentCreation)
    bootstrap.setWorldId(QWebEngineScript.ScriptWorldId.MainWorld)
    bootstrap.setRunsOnSubFrames(False)
    bootstrap.setSourceCode(_bridge_bootstrap_script())
    view.page().scripts().insert(bootstrap)

    view.load(QUrl.fromLocalFile(str(Path(WEB_ROOT, "index.html"))))
    view.show()
    return app.exec()


def _bridge_bootstrap_script() -> str:
    return """
window.emWorkbenchBridgeReady = new Promise((resolve) => {
  const retryDelayMs = 16;
  function attachBridge() {
    if (!window.QWebChannel || !window.qt || !window.qt.webChannelTransport) {
      window.setTimeout(attachBridge, retryDelayMs);
      return;
    }
    new QWebChannel(window.qt.webChannelTransport, (channel) => {
      window.emWorkbenchBridge = channel.objects.emWorkbenchBridge;
      resolve(window.emWorkbenchBridge);
    });
  }
  function appendBridgeScript() {
    if (!document.documentElement) {
      window.setTimeout(appendBridgeScript, retryDelayMs);
      return;
    }
    const script = document.createElement("script");
    script.src = "qrc:///qtwebchannel/qwebchannel.js";
    script.onload = attachBridge;
    document.documentElement.appendChild(script);
  }
  appendBridgeScript();
});
"""


if __name__ == "__main__":
    raise SystemExit(main())
