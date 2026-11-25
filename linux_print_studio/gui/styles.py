"""
Modern CSS / QSS Stylesheet for Linux Print Studio.
Provides clean, accessible, non-congested modern UI styling across all window sizes.
"""

import os

_ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
_CHEVRON_ICON = os.path.join(_ASSETS_DIR, "chevron_down.svg").replace("\\", "/")
_CHECK_ICON = os.path.join(_ASSETS_DIR, "check.svg").replace("\\", "/")

MODERN_STYLE = """
QMainWindow, QDialog {
    background-color: #18181f;
    color: #f0f0f5;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #e4e4ee;
}

QSplitter::handle {
    background-color: #2a2a36;
    width: 2px;
}

QSplitter::handle:hover {
    background-color: #4a7fd4;
}

/* Settings Cards (GroupBox) */
QGroupBox {
    font-weight: 600;
    font-size: 12px;
    border: 1px solid #323244;
    border-radius: 10px;
    margin-top: 12px;
    padding-top: 16px;
    padding-bottom: 10px;
    padding-left: 12px;
    padding-right: 12px;
    background-color: #22222c;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    padding: 0 6px;
    color: #7cc0ff;
    background-color: #22222c;
    border-radius: 4px;
}

/* Standard Buttons */
QPushButton {
    background-color: #2f2f3f;
    color: #f5f5fa;
    border: 1px solid #44445a;
    border-radius: 6px;
    padding: 6px 12px;
    font-weight: 500;
    min-height: 20px;
}

QPushButton:hover {
    background-color: #3d3d52;
    border-color: #5b5b78;
}

QPushButton:pressed {
    background-color: #252532;
}

QPushButton:disabled {
    background-color: #1d1d26;
    color: #606074;
    border-color: #292936;
}

/* Compact Preview Toolbar Buttons */
QPushButton#toolBtn {
    background-color: #2c2c3a;
    border: 1px solid #3f3f52;
    border-radius: 6px;
    padding: 3px 4px;
    min-height: 22px;
    min-width: 0px;
    font-weight: 600;
}

QPushButton#toolBtn:hover {
    background-color: #3a3a4e;
    border-color: #64b5f6;
}

/* Primary Print Button */
QPushButton#primaryButton {
    background-color: #1e88e5;
    color: #ffffff;
    border: 1px solid #1976d2;
    font-size: 14px;
    font-weight: bold;
    padding: 9px 16px;
    border-radius: 8px;
    min-height: 24px;
}

QPushButton#primaryButton:hover {
    background-color: #2196f3;
}

QPushButton#primaryButton:pressed {
    background-color: #1565c0;
}

/* 1-Click Manual Duplex Button */
QPushButton#duplexButton {
    background-color: #5e35b1;
    color: #ffffff;
    border: 1px solid #7e57c2;
    font-size: 13px;
    font-weight: bold;
    padding: 8px 14px;
    border-radius: 8px;
    min-height: 22px;
}

QPushButton#duplexButton:hover {
    background-color: #6f42c1;
    border-color: #9575cd;
}

QPushButton#duplexButton:pressed {
    background-color: #4527a0;
}

/* Secondary Export Button */
QPushButton#secondaryButton {
    background-color: #2e7d32;
    color: #ffffff;
    border: 1px solid #388e3c;
    font-weight: 600;
    border-radius: 6px;
    padding: 6px 10px;
    min-height: 20px;
}

QPushButton#secondaryButton:hover {
    background-color: #388e3c;
}

/* Checkboxes */
QCheckBox {
    spacing: 7px;
    font-size: 12.5px;
    padding: 2px 0;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border-radius: 4px;
    border: 2px solid #5a5a74;
    background-color: #1a1a22;
}

QCheckBox::indicator:hover {
    border-color: #7cc0ff;
}

QCheckBox::indicator:checked {
    background-color: #1e88e5;
    border-color: #64b5f6;
    image: url("__CHECK_ICON__");
}

/* Dropdowns, SpinBoxes, LineEdits */
QComboBox, QSpinBox, QLineEdit {
    background-color: #171720;
    border: 1px solid #3e3e52;
    border-radius: 6px;
    padding: 5px 10px;
    color: #f0f0f8;
    min-height: 22px;
    selection-background-color: #1e88e5;
}

QComboBox:hover, QSpinBox:hover, QLineEdit:hover {
    border-color: #5a5a76;
}

QComboBox:focus, QSpinBox:focus, QLineEdit:focus {
    border: 1px solid #64b5f6;
}

QComboBox::drop-down {
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 24px;
    border-left: 1px solid #323244;
    border-top-right-radius: 6px;
    border-bottom-right-radius: 6px;
    background-color: #252534;
}

QComboBox::down-arrow {
    image: url("__CHEVRON_ICON__");
    width: 12px;
    height: 12px;
}

QComboBox QAbstractItemView {
    background-color: #20202b;
    color: #f0f0f8;
    border: 1px solid #4a4a64;
    border-radius: 6px;
    selection-background-color: #1e88e5;
    selection-color: #ffffff;
    padding: 4px;
    outline: 0px;
}

/* Preview Scroll Area & Drag-Drop Highlight */
QScrollArea#previewScroll {
    border: 2px solid #2a2a38;
    background-color: #121218;
    border-radius: 8px;
}

QScrollArea#previewScroll[dragActive="true"] {
    border: 2px dashed #42a5f5;
    background-color: #132033;
}

/* Borderless Scrollable Sidebar */
QScrollArea#settingsScroll {
    border: none;
    background-color: transparent;
}

QWidget#settingsScrollContent {
    background-color: transparent;
}

/* Action Footer pinned at bottom of sidebar */
QFrame#actionFooter {
    background-color: #1e1e27;
    border-top: 1px solid #323244;
    border-radius: 8px;
}

/* Preview Toolbar & Info Strip */
QFrame#previewToolbar {
    background-color: #22222c;
    border: 1px solid #303042;
    border-radius: 8px;
}

QFrame#previewInfoBar {
    background-color: #1d1d26;
    border: 1px solid #2b2b3a;
    border-radius: 6px;
}

/* Scrollbars */
QScrollBar:vertical {
    border: none;
    background: #17171f;
    width: 9px;
    margin: 2px 0;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background: #3d3d52;
    min-height: 24px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #585876;
}

QScrollBar:horizontal {
    border: none;
    background: #17171f;
    height: 9px;
    margin: 0 2px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background: #3d3d52;
    min-width: 24px;
    border-radius: 4px;
}

QScrollBar::add-line, QScrollBar::sub-line {
    border: none;
    background: none;
    width: 0px;
    height: 0px;
}

/* Status Bar */
QStatusBar {
    background-color: #14141a;
    color: #9ea0b4;
    border-top: 1px solid #262634;
    font-size: 12px;
}

/* Labels & Badges */
QLabel#badgeLabel {
    background-color: #2c3e75;
    color: #e8f1ff;
    padding: 3px 10px;
    border-radius: 10px;
    font-size: 11.5px;
    font-weight: 600;
}

QLabel#excludedBadge {
    background-color: #5c3228;
    color: #ffccbc;
    padding: 3px 10px;
    border-radius: 10px;
    font-size: 11.5px;
    font-weight: 600;
}

QLabel#summaryBadge {
    background-color: #262238;
    color: #d1b3ff;
    border: 1px solid #3f345e;
    border-radius: 6px;
    padding: 6px 8px;
    font-size: 11.5px;
    font-weight: 600;
}

QLabel#hintLabel {
    color: #8bc399;
    font-size: 11px;
}

QFrame#dropCard {
    background-color: #1c1c25;
    border: 2px dashed #3e4866;
    border-radius: 14px;
}

QFrame#dropCard[dragActive="true"] {
    background-color: #16263c;
    border: 2px dashed #42a5f5;
}

/* Manual Duplex Dialog Cards */
QFrame#stepCard {
    background-color: #22222d;
    border: 1px solid #38384c;
    border-radius: 10px;
}

QFrame#warningCard {
    background-color: #332518;
    border: 1px solid #b57428;
    border-radius: 8px;
}
""".replace("__CHEVRON_ICON__", _CHEVRON_ICON).replace("__CHECK_ICON__", _CHECK_ICON)
