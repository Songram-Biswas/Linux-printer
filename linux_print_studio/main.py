#!/usr/bin/env python3
"""
Linux Print Studio - Entry Point
"""

import os
import sys

# Ensure package directory is in sys.path
package_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if package_root not in sys.path:
    sys.path.insert(0, package_root)

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from linux_print_studio.gui.main_window import MainWindow
from linux_print_studio.gui.styles import MODERN_STYLE


def main():
    # Enable High-DPI support
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Linux Print Studio")
    app.setOrganizationName("LinuxPrintStudio")
    app.setStyleSheet(MODERN_STYLE)

    # Check for CLI argument (e.g. file passed via 'Open With')
    initial_file = None
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        candidate = os.path.abspath(sys.argv[1])
        if os.path.exists(candidate):
            initial_file = candidate

    window = MainWindow(initial_file=initial_file)
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
