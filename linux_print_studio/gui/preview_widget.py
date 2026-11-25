"""
Interactive Preview Widget for Linux Print Studio.
Provides high-fidelity page & N-up sheet preview with compact non-clipping toolbar,
zoom dropdown, navigation, drag-and-drop visual feedback, and live color conversion preview.
"""

from typing import List, Optional
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QImage, QPixmap, QWheelEvent
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QScrollArea, QSpinBox, QComboBox, QSizePolicy,
    QStackedWidget
)
from linux_print_studio.core.pdf_processor import (
    DocumentModel, ColorMode, NUpMode, group_pages_into_sheets
)


class PreviewWidget(QWidget):
    """
    Renders document pages or composed N-up sheets and manages zoom, navigation,
    empty drop-zone state, and live drag-and-drop highlight feedback.
    """
    pageChanged = pyqtSignal(int)       # 1-based page or sheet index
    openFileRequested = pyqtSignal()    # Emitted when empty-state Open button is clicked

    def __init__(self, parent=None):
        super().__init__(parent)

        self.doc_model: Optional[DocumentModel] = None
        self.current_index: int = 1  # 1-based page (1-up) or sheet (N-up)
        self.zoom_factor: float = 1.0
        self.fit_mode: str = "fit_page"  # 'fit_page', 'fit_width', 'custom'
        self.color_mode: ColorMode = ColorMode.GRAYSCALE
        self.n_up: NUpMode = NUpMode.ONE_UP
        self.paper_size: str = "A4"
        self.draw_borders: bool = True

        self.ordered_pages: List[int] = []
        self.sheets: List[List[int]] = []
        self._updating_zoom_combo = False

        # Debounce resize re-renders for smooth resizing
        self._resize_timer = QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.setInterval(45)
        self._resize_timer.timeout.connect(self.refresh_preview)

        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 1. Compact Non-Clipping Navigation & Zoom Toolbar
        toolbar_frame = QFrame(self)
        toolbar_frame.setObjectName("previewToolbar")
        nav_layout = QHBoxLayout(toolbar_frame)
        nav_layout.setContentsMargins(6, 5, 6, 5)
        nav_layout.setSpacing(4)

        self.btn_first = QPushButton("⏮", self)
        self.btn_first.setObjectName("toolBtn")
        self.btn_first.setFixedWidth(28)
        self.btn_first.setToolTip("First Page / Sheet")
        self.btn_first.clicked.connect(self.go_to_first_page)

        self.btn_prev = QPushButton("◀", self)
        self.btn_prev.setObjectName("toolBtn")
        self.btn_prev.setFixedWidth(28)
        self.btn_prev.setToolTip("Previous Page / Sheet")
        self.btn_prev.clicked.connect(self.go_to_prev_page)

        self.lbl_nav_unit = QLabel("Pg", self)
        self.lbl_nav_unit.setStyleSheet("font-size: 11.5px; color: #b8bccf;")

        self.spin_page = QSpinBox(self)
        self.spin_page.setMinimum(1)
        self.spin_page.setMaximum(1)
        self.spin_page.setFixedWidth(54)
        self.spin_page.valueChanged.connect(self._on_spin_page_changed)

        self.lbl_page_total = QLabel("/ 0", self)
        self.lbl_page_total.setStyleSheet("font-size: 11.5px; color: #b8bccf;")

        self.btn_next = QPushButton("▶", self)
        self.btn_next.setObjectName("toolBtn")
        self.btn_next.setFixedWidth(28)
        self.btn_next.setToolTip("Next Page / Sheet")
        self.btn_next.clicked.connect(self.go_to_next_page)

        self.btn_last = QPushButton("⏭", self)
        self.btn_last.setObjectName("toolBtn")
        self.btn_last.setFixedWidth(28)
        self.btn_last.setToolTip("Last Page / Sheet")
        self.btn_last.clicked.connect(self.go_to_last_page)

        # Zoom Controls (Compact with Dropdown!)
        self.btn_zoom_out = QPushButton("−", self)
        self.btn_zoom_out.setObjectName("toolBtn")
        self.btn_zoom_out.setFixedWidth(28)
        self.btn_zoom_out.setToolTip("Zoom Out (Ctrl + Scroll)")
        self.btn_zoom_out.clicked.connect(self.zoom_out)

        self.combo_zoom = QComboBox(self)
        self.combo_zoom.setFixedWidth(96)
        self.combo_zoom.setToolTip("Zoom / Fit Mode")
        self.combo_zoom.addItem("Fit Page", ("fit_page", 1.0))
        self.combo_zoom.addItem("Fit Width", ("fit_width", 1.0))
        self.combo_zoom.addItem("50%", ("custom", 0.5))
        self.combo_zoom.addItem("75%", ("custom", 0.75))
        self.combo_zoom.addItem("100%", ("custom", 1.0))
        self.combo_zoom.addItem("125%", ("custom", 1.25))
        self.combo_zoom.addItem("150%", ("custom", 1.5))
        self.combo_zoom.addItem("200%", ("custom", 2.0))
        self.combo_zoom.currentIndexChanged.connect(self._on_zoom_combo_changed)

        self.btn_zoom_in = QPushButton("+", self)
        self.btn_zoom_in.setObjectName("toolBtn")
        self.btn_zoom_in.setFixedWidth(28)
        self.btn_zoom_in.setToolTip("Zoom In (Ctrl + Scroll)")
        self.btn_zoom_in.clicked.connect(self.zoom_in)

        nav_layout.addWidget(self.btn_first)
        nav_layout.addWidget(self.btn_prev)
        nav_layout.addWidget(self.lbl_nav_unit)
        nav_layout.addWidget(self.spin_page)
        nav_layout.addWidget(self.lbl_page_total)
        nav_layout.addWidget(self.btn_next)
        nav_layout.addWidget(self.btn_last)
        nav_layout.addStretch(1)
        nav_layout.addWidget(self.btn_zoom_out)
        nav_layout.addWidget(self.combo_zoom)
        nav_layout.addWidget(self.btn_zoom_in)

        main_layout.addWidget(toolbar_frame)

        # 2. Compact Info / Print Queue Badge Strip (Never collides with toolbar buttons!)
        self.info_bar = QFrame(self)
        self.info_bar.setObjectName("previewInfoBar")
        info_layout = QHBoxLayout(self.info_bar)
        info_layout.setContentsMargins(10, 4, 10, 4)
        info_layout.setSpacing(8)

        self.lbl_badge = QLabel("", self)
        self.lbl_badge.setObjectName("badgeLabel")

        self.lbl_zoom_percent = QLabel("100%", self)
        self.lbl_zoom_percent.setStyleSheet("color: #9ea4be; font-size: 11.5px; font-weight: 600;")

        info_layout.addWidget(self.lbl_badge)
        info_layout.addStretch(1)
        info_layout.addWidget(self.lbl_zoom_percent)
        self.info_bar.setVisible(False)

        main_layout.addWidget(self.info_bar)

        # 3. Drag-and-Drop Banner (Visible only while dragging a file over the app)
        self.lbl_drag_banner = QLabel("📥 Drop PDF or Image anywhere here to load preview", self)
        self.lbl_drag_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_drag_banner.setStyleSheet(
            "background-color: #1565c0; color: #ffffff; font-weight: bold; "
            "padding: 7px 12px; border-radius: 6px; font-size: 13px;"
        )
        self.lbl_drag_banner.setVisible(False)
        main_layout.addWidget(self.lbl_drag_banner)

        # 4. Stacked Preview Area (Empty Drop Card vs Scrollable Page Canvas)
        self.stack = QStackedWidget(self)

        # -- Page 0: Empty Drop-Zone Card --
        empty_page = QWidget(self)
        empty_vbox = QVBoxLayout(empty_page)
        empty_vbox.setContentsMargins(20, 20, 20, 20)
        empty_vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.drop_card = QFrame(empty_page)
        self.drop_card.setObjectName("dropCard")
        self.drop_card.setMinimumSize(280, 200)
        self.drop_card.setMaximumSize(460, 280)
        card_layout = QVBoxLayout(self.drop_card)
        card_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.setSpacing(10)
        card_layout.setContentsMargins(24, 24, 24, 24)

        lbl_icon = QLabel("📄", self.drop_card)
        lbl_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_icon.setStyleSheet("font-size: 40px;")

        lbl_empty_title = QLabel("Drag & Drop a PDF or Image Here", self.drop_card)
        lbl_empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_empty_title.setStyleSheet("font-size: 15px; font-weight: bold; color: #e6ecff;")

        lbl_empty_sub = QLabel("Supports PDF, PNG, JPG, WebP, BMP, TIFF", self.drop_card)
        lbl_empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl_empty_sub.setStyleSheet("font-size: 12px; color: #8c93ab;")

        btn_empty_open = QPushButton("📂 Browse File...", self.drop_card)
        btn_empty_open.setObjectName("primaryButton")
        btn_empty_open.setMaximumWidth(180)
        btn_empty_open.clicked.connect(self.openFileRequested.emit)

        card_layout.addWidget(lbl_icon)
        card_layout.addWidget(lbl_empty_title)
        card_layout.addWidget(lbl_empty_sub)
        card_layout.addSpacing(6)
        card_layout.addWidget(btn_empty_open, alignment=Qt.AlignmentFlag.AlignCenter)

        empty_vbox.addWidget(self.drop_card)
        self.stack.addWidget(empty_page)

        # -- Page 1: Scrollable Rendered Canvas --
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("previewScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.container_widget = QWidget()
        self.container_widget.setStyleSheet("background-color: transparent;")
        container_layout = QVBoxLayout(self.container_widget)
        container_layout.setContentsMargins(16, 16, 16, 16)
        container_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.lbl_image = QLabel(self.container_widget)
        self.lbl_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_image.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        container_layout.addWidget(self.lbl_image)
        self.scroll_area.setWidget(self.container_widget)
        self.stack.addWidget(self.scroll_area)

        self.stack.setCurrentIndex(0)
        main_layout.addWidget(self.stack, 1)

        self._set_nav_enabled(False)

    def _set_nav_enabled(self, enabled: bool):
        for w in (
            self.btn_first, self.btn_prev, self.spin_page,
            self.btn_next, self.btn_last, self.btn_zoom_out,
            self.combo_zoom, self.btn_zoom_in
        ):
            w.setEnabled(enabled)

    def set_drag_active(self, active: bool):
        """Visual highlight when user drags a supported file over the app."""
        self.lbl_drag_banner.setVisible(active)
        self.scroll_area.setProperty("dragActive", active)
        self.scroll_area.style().unpolish(self.scroll_area)
        self.scroll_area.style().polish(self.scroll_area)

        self.drop_card.setProperty("dragActive", active)
        self.drop_card.style().unpolish(self.drop_card)
        self.drop_card.style().polish(self.drop_card)

    def set_document(self, doc_model: Optional[DocumentModel]):
        self.doc_model = doc_model
        if self.doc_model and self.doc_model.total_pages > 0:
            self.ordered_pages = list(range(1, self.doc_model.total_pages + 1))
            self.sheets = group_pages_into_sheets(self.ordered_pages, self.n_up.value)
            self.current_index = 1
            self.stack.setCurrentIndex(1)
            self.info_bar.setVisible(True)
            self._set_nav_enabled(True)
            self._sync_nav_bounds(reset_to_first=True)
            self.refresh_preview()
        else:
            self.ordered_pages = []
            self.sheets = []
            self.stack.setCurrentIndex(0)
            self.info_bar.setVisible(False)
            self._set_nav_enabled(False)
            self.spin_page.setMaximum(1)
            self.lbl_page_total.setText("/ 0")

    def set_print_layout(
        self,
        ordered_pages: List[int],
        n_up: NUpMode = NUpMode.ONE_UP,
        paper_size: str = "A4",
        draw_borders: bool = True
    ):
        """Updates print queue ordering, N-up mode, paper size, and border option."""
        old_n_up = self.n_up
        self.ordered_pages = ordered_pages
        self.n_up = n_up
        self.paper_size = paper_size
        self.draw_borders = draw_borders
        self.sheets = group_pages_into_sheets(ordered_pages, n_up.value)

        if self.doc_model and self.doc_model.total_pages > 0:
            self._sync_nav_bounds(reset_to_first=(old_n_up != n_up))
            self.refresh_preview()

    def set_ordered_pages(self, pages: List[int]):
        """Backward-compatible helper to update ordered pages."""
        self.set_print_layout(pages, self.n_up, self.paper_size, self.draw_borders)

    def set_color_mode(self, mode: ColorMode):
        if self.color_mode != mode:
            self.color_mode = mode
            self.refresh_preview()

    def _get_max_nav_index(self) -> int:
        if not self.doc_model or self.doc_model.total_pages == 0:
            return 0
        if self.n_up == NUpMode.ONE_UP:
            return self.doc_model.total_pages
        return max(1, len(self.sheets))

    def _sync_nav_bounds(self, reset_to_first: bool = False):
        max_idx = self._get_max_nav_index()
        self.lbl_nav_unit.setText("Sheet" if self.n_up != NUpMode.ONE_UP else "Pg")

        self.spin_page.blockSignals(True)
        self.spin_page.setMinimum(1)
        self.spin_page.setMaximum(max(1, max_idx))
        if reset_to_first or self.current_index > max_idx or self.current_index < 1:
            self.current_index = 1
        self.spin_page.setValue(self.current_index)
        self.spin_page.blockSignals(False)

        self.lbl_page_total.setText(f"/ {max_idx}")

    def refresh_preview(self):
        if not self.doc_model or self.doc_model.total_pages == 0:
            return

        zoom = self._calculate_effective_zoom()

        if self.n_up == NUpMode.ONE_UP:
            pix = self.doc_model.render_preview_pixmap(
                page_num_1_based=self.current_index,
                color_mode=self.color_mode,
                zoom=zoom
            )
        else:
            if not self.sheets:
                self.lbl_image.setPixmap(QPixmap())
                self.lbl_image.setText("No pages match the selected page range.")
                self._update_badge()
                return
            sheet_idx = min(self.current_index - 1, len(self.sheets) - 1)
            sheet_pages = self.sheets[sheet_idx]
            pix = self.doc_model.render_sheet_preview_pixmap(
                sheet_pages=sheet_pages,
                n_up=self.n_up,
                color_mode=self.color_mode,
                zoom=zoom,
                paper_size=self.paper_size,
                draw_borders=self.draw_borders
            )

        if pix:
            fmt = QImage.Format.Format_Grayscale8 if pix.colorspace.n == 1 else QImage.Format.Format_RGB888
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, fmt).copy()
            qpixmap = QPixmap.fromImage(qimg)
            self.lbl_image.setPixmap(qpixmap)
            self.lbl_image.setText("")
        else:
            self.lbl_image.setText("Failed to render page preview.")

        self.lbl_zoom_percent.setText(f"{int(round(zoom * 100))}%")
        self._update_badge()

    def _calculate_effective_zoom(self) -> float:
        if not self.doc_model or self.doc_model.total_pages == 0:
            return 1.0

        if self.fit_mode == "custom":
            return max(0.2, min(4.0, self.zoom_factor))

        if self.n_up == NUpMode.ONE_UP:
            w_pt, h_pt = self.doc_model.get_page_size_pt(self.current_index)
        elif self.sheets:
            sheet_idx = min(self.current_index - 1, len(self.sheets) - 1)
            w_pt, h_pt = self.doc_model.get_sheet_size_pt(
                self.sheets[sheet_idx], self.n_up, self.paper_size
            )
        else:
            w_pt, h_pt = 595.28, 841.89

        viewport_w = max(180, self.scroll_area.viewport().width() - 36)
        viewport_h = max(180, self.scroll_area.viewport().height() - 36)

        scale_w = viewport_w / max(1.0, w_pt)
        scale_h = viewport_h / max(1.0, h_pt)

        if self.fit_mode == "fit_width":
            return max(0.25, min(4.0, scale_w))
        return max(0.25, min(4.0, min(scale_w, scale_h)))

    def _update_badge(self):
        if not self.doc_model:
            return

        mode_text = "🌈 Color"
        if self.color_mode == ColorMode.GRAYSCALE:
            mode_text = "🔘 Grayscale B&W"
        elif self.color_mode == ColorMode.MONOCHROME:
            mode_text = "⬛ Pure B&W"

        if self.n_up != NUpMode.ONE_UP:
            if not self.sheets:
                self.lbl_badge.setObjectName("excludedBadge")
                self.lbl_badge.setText("⚠️ No pages selected for printing")
            else:
                sheet_idx = min(self.current_index - 1, len(self.sheets) - 1)
                pgs = ", ".join(str(p) for p in self.sheets[sheet_idx])
                self.lbl_badge.setObjectName("badgeLabel")
                self.lbl_badge.setText(
                    f"Sheet {sheet_idx + 1} of {len(self.sheets)}  •  Pages [{pgs}]  •  {self.n_up.value}-in-1  •  {mode_text}"
                )
        else:
            if self.current_index in self.ordered_pages:
                idx = self.ordered_pages.index(self.current_index) + 1
                total_selected = len(self.ordered_pages)
                self.lbl_badge.setObjectName("badgeLabel")
                self.lbl_badge.setText(
                    f"Print Queue: Sheet {idx} of {total_selected}  •  {mode_text}"
                )
            else:
                self.lbl_badge.setObjectName("excludedBadge")
                self.lbl_badge.setText("⚠️ Page excluded from current print range")

        self.lbl_badge.style().unpolish(self.lbl_badge)
        self.lbl_badge.style().polish(self.lbl_badge)

    def _on_spin_page_changed(self, val: int):
        if self.current_index != val:
            self.current_index = val
            self.refresh_preview()
            self.pageChanged.emit(self.current_index)

    def _on_zoom_combo_changed(self, index: int):
        if self._updating_zoom_combo or index < 0:
            return
        data = self.combo_zoom.itemData(index)
        if not data:
            return
        mode, factor = data
        self.fit_mode = mode
        if mode == "custom":
            self.zoom_factor = factor
        self.refresh_preview()

    def _sync_zoom_combo_to_custom(self):
        self._updating_zoom_combo = True
        try:
            # Find closest preset or leave selection cleanly synced
            for i in range(self.combo_zoom.count()):
                data = self.combo_zoom.itemData(i)
                if data and data[0] == "custom" and abs(data[1] - self.zoom_factor) < 0.05:
                    self.combo_zoom.setCurrentIndex(i)
                    return
        finally:
            self._updating_zoom_combo = False

    def go_to_first_page(self):
        self.spin_page.setValue(1)

    def go_to_last_page(self):
        max_idx = self._get_max_nav_index()
        if max_idx >= 1:
            self.spin_page.setValue(max_idx)

    def go_to_prev_page(self):
        if self.current_index > 1:
            self.spin_page.setValue(self.current_index - 1)

    def go_to_next_page(self):
        if self.current_index < self._get_max_nav_index():
            self.spin_page.setValue(self.current_index + 1)

    def zoom_in(self):
        if self.fit_mode != "custom":
            self.zoom_factor = self._calculate_effective_zoom()
        self.fit_mode = "custom"
        self.zoom_factor = min(4.0, self.zoom_factor * 1.25)
        self._sync_zoom_combo_to_custom()
        self.refresh_preview()

    def zoom_out(self):
        if self.fit_mode != "custom":
            self.zoom_factor = self._calculate_effective_zoom()
        self.fit_mode = "custom"
        self.zoom_factor = max(0.25, self.zoom_factor / 1.25)
        self._sync_zoom_combo_to_custom()
        self.refresh_preview()

    def set_fit_page(self):
        self.fit_mode = "fit_page"
        self._updating_zoom_combo = True
        self.combo_zoom.setCurrentIndex(0)
        self._updating_zoom_combo = False
        self.refresh_preview()

    def set_fit_width(self):
        self.fit_mode = "fit_width"
        self._updating_zoom_combo = True
        self.combo_zoom.setCurrentIndex(1)
        self._updating_zoom_combo = False
        self.refresh_preview()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.doc_model and self.fit_mode in ("fit_page", "fit_width"):
            self._resize_timer.start()

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and self.doc_model:
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)
