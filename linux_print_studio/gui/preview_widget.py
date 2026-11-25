"""
Interactive Preview Widget for Linux Print Studio.
Provides high-fidelity page preview with zoom, pan, navigation,
and live visual feedback of color vs grayscale/monochrome conversion.
"""

from typing import Optional, List
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QImage, QPixmap, QWheelEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QSpinBox, QSizePolicy
)
from linux_print_studio.core.pdf_processor import DocumentModel, ColorMode


class PreviewWidget(QWidget):
    """
    Renders document pages and manages zoom, pan, and page navigation.
    """
    pageChanged = pyqtSignal(int)  # 1-based page index

    def __init__(self, parent=None):
        super().__init__(parent)

        self.doc_model: Optional[DocumentModel] = None
        self.current_page: int = 1
        self.zoom_factor: float = 1.0
        self.fit_mode: str = "fit_page"  # 'fit_page', 'fit_width', 'custom'
        self.color_mode: ColorMode = ColorMode.COLOR
        self.ordered_pages: List[int] = []

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 1. Navigation & Zoom Toolbar
        nav_toolbar = QWidget(self)
        nav_layout = QHBoxLayout(nav_toolbar)
        nav_layout.setContentsMargins(6, 6, 6, 6)
        nav_layout.setSpacing(8)

        self.btn_first = QPushButton("⏮", self)
        self.btn_first.setToolTip("First Page")
        self.btn_first.clicked.connect(self.go_to_first_page)

        self.btn_prev = QPushButton("◀ Prev", self)
        self.btn_prev.setToolTip("Previous Page")
        self.btn_prev.clicked.connect(self.go_to_prev_page)

        self.lbl_page_prefix = QLabel("Page", self)
        self.spin_page = QSpinBox(self)
        self.spin_page.setMinimum(1)
        self.spin_page.setMaximum(1)
        self.spin_page.valueChanged.connect(self._on_spin_page_changed)

        self.lbl_page_total = QLabel("of 0", self)

        self.btn_next = QPushButton("Next ▶", self)
        self.btn_next.setToolTip("Next Page")
        self.btn_next.clicked.connect(self.go_to_next_page)

        self.btn_last = QPushButton("⏭", self)
        self.btn_last.setToolTip("Last Page")
        self.btn_last.clicked.connect(self.go_to_last_page)

        # Zoom buttons
        self.btn_zoom_out = QPushButton("🔍 -", self)
        self.btn_zoom_out.setToolTip("Zoom Out")
        self.btn_zoom_out.clicked.connect(self.zoom_out)

        self.btn_zoom_in = QPushButton("🔍 +", self)
        self.btn_zoom_in.setToolTip("Zoom In")
        self.btn_zoom_in.clicked.connect(self.zoom_in)

        self.btn_fit_page = QPushButton("Fit Page", self)
        self.btn_fit_page.clicked.connect(self.set_fit_page)

        self.btn_fit_width = QPushButton("Fit Width", self)
        self.btn_fit_width.clicked.connect(self.set_fit_width)

        self.lbl_zoom_percent = QLabel("100%", self)

        # Page Info Badge
        self.lbl_badge = QLabel("", self)
        self.lbl_badge.setObjectName("badgeLabel")
        self.lbl_badge.setVisible(False)

        nav_layout.addWidget(self.btn_first)
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.lbl_page_prefix)
        nav_layout.addWidget(self.spin_page)
        nav_layout.addWidget(self.lbl_page_total)
        nav_layout.addWidget(self.btn_next)
        nav_layout.addWidget(self.btn_last)
        nav_layout.addSpacing(16)
        nav_layout.addWidget(self.btn_zoom_out)
        nav_layout.addWidget(self.lbl_zoom_percent)
        nav_layout.addWidget(self.btn_zoom_in)
        nav_layout.addWidget(self.btn_fit_page)
        nav_layout.addWidget(self.btn_fit_width)
        nav_layout.addStretch()
        nav_layout.addWidget(self.lbl_badge)

        main_layout.addWidget(nav_toolbar)

        # 2. Scrollable Canvas
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.container_widget = QWidget()
        container_layout = QVBoxLayout(self.container_widget)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_image = QLabel(self.container_widget)
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.lbl_image.setText("No document loaded.\nDrag and drop a PDF or Image here, or click 'Open File'.")
        self.lbl_image.setStyleSheet("color: #888899; font-size: 15px; font-weight: bold;")

        container_layout.addWidget(self.lbl_image)
        self.scroll_area.setWidget(self.container_widget)

        main_layout.addWidget(self.scroll_area)

    def set_document(self, doc_model: Optional[DocumentModel]):
        self.doc_model = doc_model
        if self.doc_model and self.doc_model.total_pages > 0:
            self.spin_page.setMaximum(self.doc_model.total_pages)
            self.lbl_page_total.setText(f"of {self.doc_model.total_pages}")
            self.current_page = 1
            self.spin_page.setValue(1)
            self.ordered_pages = list(range(1, self.doc_model.total_pages + 1))
            self.refresh_preview()
        else:
            self.spin_page.setMaximum(1)
            self.lbl_page_total.setText("of 0")
            self.lbl_image.setText("No document loaded.")
            self.lbl_badge.setVisible(False)

    def set_ordered_pages(self, pages: List[int]):
        """Updates the print-order page list to show queue position badges."""
        self.ordered_pages = pages
        self._update_badge()

    def set_color_mode(self, mode: ColorMode):
        if self.color_mode != mode:
            self.color_mode = mode
            self.refresh_preview()

    def refresh_preview(self):
        if not self.doc_model or self.doc_model.total_pages == 0:
            return

        # Calculate zoom
        zoom = self._calculate_effective_zoom()
        pix = self.doc_model.render_preview_pixmap(
            page_num_1_based=self.current_page,
            color_mode=self.color_mode,
            zoom=zoom
        )

        if pix:
            # Convert PyMuPDF Pixmap to QImage
            fmt = QImage.Format.Format_Grayscale8 if pix.colorspace.n == 1 else QImage.Format.Format_RGB888
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt)
            qpixmap = QPixmap.fromImage(qimg)
            self.lbl_image.setPixmap(qpixmap)
            self.lbl_image.setText("")
        else:
            self.lbl_image.setText("Failed to render page preview.")

        self.lbl_zoom_percent.setText(f"{int(zoom * 100)}%")
        self._update_badge()

    def _calculate_effective_zoom(self) -> float:
        if not self.doc_model or self.doc_model.total_pages == 0:
            return 1.0

        if self.fit_mode == "custom":
            return max(0.2, min(5.0, self.zoom_factor))

        w_pt, h_pt = self.doc_model.get_page_size_pt(self.current_page)
        viewport_w = max(200, self.scroll_area.viewport().width() - 40)
        viewport_h = max(200, self.scroll_area.viewport().height() - 40)

        # 72 points = 1 inch, default screen DPI approx 96-120
        # PyMuPDF matrix zoom=1.0 renders at 72 DPI
        scale_w = viewport_w / w_pt
        scale_h = viewport_h / h_pt

        if self.fit_mode == "fit_width":
            return max(0.3, scale_w)
        elif self.fit_mode == "fit_page":
            return max(0.3, min(scale_w, scale_h))

        return 1.0

    def _update_badge(self):
        if not self.doc_model or not self.ordered_pages:
            self.lbl_badge.setVisible(False)
            return

        # Check if current page is in the print queue
        if self.current_page in self.ordered_pages:
            idx = self.ordered_pages.index(self.current_page) + 1
            total_selected = len(self.ordered_pages)
            mode_text = "🌈 Color"
            if self.color_mode == ColorMode.GRAYSCALE:
                mode_text = "🔘 Grayscale B&W"
            elif self.color_mode == ColorMode.MONOCHROME:
                mode_text = "⬛ Pure B&W"

            self.lbl_badge.setText(f"Print Job: Sheet {idx} of {total_selected} | {mode_text}")
            self.lbl_badge.setVisible(True)
        else:
            self.lbl_badge.setText("⚠️ Excluded from Print")
            self.lbl_badge.setVisible(True)

    def _on_spin_page_changed(self, val: int):
        if self.current_page != val:
            self.current_page = val
            self.refresh_preview()
            self.pageChanged.emit(self.current_page)

    def go_to_first_page(self):
        self.spin_page.setValue(1)

    def go_to_last_page(self):
        if self.doc_model:
            self.spin_page.setValue(self.doc_model.total_pages)

    def go_to_prev_page(self):
        if self.current_page > 1:
            self.spin_page.setValue(self.current_page - 1)

    def go_to_next_page(self):
        if self.doc_model and self.current_page < self.doc_model.total_pages:
            self.spin_page.setValue(self.current_page + 1)

    def zoom_in(self):
        self.fit_mode = "custom"
        self.zoom_factor = min(4.0, self.zoom_factor * 1.25)
        self.refresh_preview()

    def zoom_out(self):
        self.fit_mode = "custom"
        self.zoom_factor = max(0.2, self.zoom_factor / 1.25)
        self.refresh_preview()

    def set_fit_page(self):
        self.fit_mode = "fit_page"
        self.refresh_preview()

    def set_fit_width(self):
        self.fit_mode = "fit_width"
        self.refresh_preview()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.fit_mode in ("fit_page", "fit_width"):
            self.refresh_preview()

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)
