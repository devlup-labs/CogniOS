"""Native desktop shell for the existing Streamlit dashboard."""

from __future__ import annotations

import sys

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView


def run_dashboard(url: str = "http://127.0.0.1:8501") -> int:
    app = QApplication(sys.argv)
    window = QMainWindow()
    window.setWindowTitle("CogniOS - System Observability")
    window.resize(1440, 900)

    view = QWebEngineView()
    view.setUrl(QUrl(url))
    window.setCentralWidget(view)
    window.show()

    return app.exec()
