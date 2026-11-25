"""
Modern CSS / QSS Stylesheet for Linux Print Studio.
Provides clean, accessible, modern UI styling compatible with dark and light desktop environments.
"""

MODERN_STYLE = """
QMainWindow {
    background-color: #1e1e24;
    color: #f0f0f5;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
}

QWidget {
    color: #e0e0ea;
}

QMenuBar {
    background-color: #18181c;
    color: #e0e0ea;
    border-bottom: 1px solid #2d2d38;
}

QMenuBar::item:selected {
    background-color: #2e5aac;
    border-radius: 4px;
}

QMenu {
    background-color: #22222a;
    color: #e0e0ea;
    border: 1px solid #3d3d4e;
    border-radius: 6px;
    padding: 4px;
}

QMenu::item:selected {
    background-color: #3b73cf;
    border-radius: 4px;
}

QToolBar {
    background-color: #23232b;
    border-bottom: 1px solid #32323f;
    spacing: 6px;
    padding: 6px;
}

QGroupBox {
    font-weight: bold;
    border: 1px solid #363645;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 18px;
    padding-bottom: 12px;
    padding-left: 12px;
    padding-right: 12px;
    background-color: #24242d;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    padding: 0 6px;
    color: #64b5f6;
    background-color: #24242d;
    border-radius: 4px;
}

QPushButton {
    background-color: #333342;
    color: #f5f5fa;
    border: 1px solid #48485c;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #424256;
    border-color: #5c5c76;
}

QPushButton:pressed {
    background-color: #282834;
}

QPushButton:disabled {
    background-color: #1e1e26;
    color: #666677;
    border-color: #2a2a36;
}

/* Primary Action Buttons */
QPushButton#primaryButton {
    background-color: #1e88e5;
    color: #ffffff;
    border: 1px solid #1976d2;
    font-size: 14px;
    font-weight: bold;
    padding: 10px 18px;
    border-radius: 8px;
}

QPushButton#primaryButton:hover {
    background-color: #2196f3;
}

QPushButton#primaryButton:pressed {
    background-color: #1565c0;
}

QPushButton#secondaryButton {
    background-color: #2e7d32;
    color: #ffffff;
    border: 1px solid #1b5e20;
    font-weight: bold;
    border-radius: 6px;
    padding: 8px 14px;
}

QPushButton#secondaryButton:hover {
    background-color: #388e3c;
}

QRadioButton, QCheckBox {
    spacing: 8px;
    font-size: 13px;
}

QRadioButton::indicator, QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 2px solid #5a5a72;
    background-color: #1c1c24;
}

QRadioButton::indicator {
    border-radius: 9px;
}

QRadioButton::indicator:checked, QCheckBox::indicator:checked {
    background-color: #1e88e5;
    border-color: #64b5f6;
}

QComboBox, QSpinBox, QLineEdit {
    background-color: #1a1a22;
    border: 1px solid #424254;
    border-radius: 6px;
    padding: 6px 10px;
    color: #f0f0f5;
    selection-background-color: #1e88e5;
}

QComboBox:focus, QSpinBox:focus, QLineEdit:focus {
    border: 1px solid #64b5f6;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QScrollArea {
    border: 1px solid #2d2d3a;
    background-color: #16161c;
    border-radius: 6px;
}

QScrollBar:vertical {
    border: none;
    background: #1a1a22;
    width: 12px;
    margin: 0px;
    border-radius: 6px;
}

QScrollBar::handle:vertical {
    background: #424256;
    min-height: 20px;
    border-radius: 6px;
}

QScrollBar::handle:vertical:hover {
    background: #5c5c76;
}

QScrollBar:horizontal {
    border: none;
    background: #1a1a22;
    height: 12px;
    margin: 0px;
    border-radius: 6px;
}

QScrollBar::handle:horizontal {
    background: #424256;
    min-width: 20px;
    border-radius: 6px;
}

QScrollBar::add-line, QScrollBar::sub-line {
    border: none;
    background: none;
}

QStatusBar {
    background-color: #16161c;
    color: #a0a0b2;
    border-top: 1px solid #282834;
}

QLabel#titleLabel {
    font-size: 16px;
    font-weight: bold;
    color: #ffffff;
}

QLabel#badgeLabel {
    background-color: #3949ab;
    color: #ffffff;
    padding: 3px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: bold;
}

QLabel#highlightLabel {
    color: #ffb74d;
    font-weight: bold;
}
"""
