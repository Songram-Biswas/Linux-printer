"""
Main Application Window for Linux Print Studio.
Responsive, non-congested dropdown-based layout with:
- True software B&W / Grayscale / Monochrome enforcement
- N-up Printing (1-in-1 / 2-in-1 / 4-in-1) with live sheet preview
- 1-Click Manual Duplex Wizard (Odd -> Flip Prompt -> Reverse Even)
- Full Drag & Drop support with visual drop-zone feedback
"""

import os
import tempfile
from typing import List, Optional

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QSplitter, QGroupBox, QCheckBox, QLineEdit, QComboBox, QSpinBox,
    QLabel, QPushButton, QFileDialog, QMessageBox, QStatusBar,
    QProgressBar, QDialog, QScrollArea, QFrame
)
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

from linux_print_studio.core.pdf_processor import (
    DocumentModel, PageSelectionMode, ColorMode, NUpMode,
    get_target_pages, group_pages_into_sheets, split_manual_duplex_sheets,
    is_supported_file
)
from linux_print_studio.core.cups_manager import CupsManager
from linux_print_studio.gui.preview_widget import PreviewWidget
from linux_print_studio.gui.manual_duplex_dialog import ManualDuplexDialog


class MainWindow(QMainWindow):
    def __init__(self, initial_file: Optional[str] = None):
        super().__init__()

        self.setWindowTitle("Linux Print Studio - Professional PDF & Image Printing")
        self.resize(1180, 760)
        self.setMinimumSize(800, 520)
        self.setAcceptDrops(True)

        self.doc_model: Optional[DocumentModel] = None
        self.cups_manager = CupsManager()

        self._init_ui()
        self._load_printers()
        self._update_color_hint()
        self._update_print_queue_summary()

        if initial_file and os.path.exists(initial_file):
            self.load_file(initial_file)

    def _init_ui(self):
        # Central Splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        main_splitter.setChildrenCollapsible(False)
        self.setCentralWidget(main_splitter)

        # --- Left: Interactive Preview Area ---
        preview_container = QWidget(self)
        preview_container.setMinimumWidth(430)
        preview_vbox = QVBoxLayout(preview_container)
        preview_vbox.setContentsMargins(10, 10, 6, 10)
        preview_vbox.setSpacing(0)

        self.preview_widget = PreviewWidget(self)
        self.preview_widget.openFileRequested.connect(self.action_open_file)
        preview_vbox.addWidget(self.preview_widget)
        main_splitter.addWidget(preview_container)

        # --- Right: Scrollable Settings + Pinned Action Footer ---
        sidebar_root = QWidget(self)
        sidebar_root.setMinimumWidth(340)
        sidebar_root.setMaximumWidth(440)
        sidebar_outer = QVBoxLayout(sidebar_root)
        sidebar_outer.setContentsMargins(6, 10, 10, 10)
        sidebar_outer.setSpacing(8)

        # Scrollable Settings Area (Guarantees ZERO congestion at ANY window height!)
        self.settings_scroll = QScrollArea(sidebar_root)
        self.settings_scroll.setObjectName("settingsScroll")
        self.settings_scroll.setWidgetResizable(True)
        self.settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.settings_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.settings_scroll.setFrameShape(QFrame.Shape.NoFrame)

        settings_content = QWidget()
        settings_content.setObjectName("settingsScrollContent")
        settings_vbox = QVBoxLayout(settings_content)
        settings_vbox.setContentsMargins(2, 0, 12, 4)
        settings_vbox.setSpacing(10)

        # --- 1. Document Card ---
        grp_file = QGroupBox("📄 Document", settings_content)
        file_layout = QVBoxLayout(grp_file)
        file_layout.setSpacing(6)

        self.btn_open_file = QPushButton("📂 Open PDF / Image...", grp_file)
        self.btn_open_file.clicked.connect(self.action_open_file)
        file_layout.addWidget(self.btn_open_file)

        self.lbl_file_name = QLabel("No file selected (or drag & drop)", grp_file)
        self.lbl_file_name.setWordWrap(True)
        self.lbl_file_name.setStyleSheet("color: #90caf9; font-weight: bold; font-size: 12.5px;")
        self.lbl_file_details = QLabel("Pages: 0", grp_file)
        self.lbl_file_details.setStyleSheet("color: #a6b2c2; font-size: 11px;")
        file_layout.addWidget(self.lbl_file_name)
        file_layout.addWidget(self.lbl_file_details)
        settings_vbox.addWidget(grp_file)

        # --- 2. Color & N-up Layout Card (Clean Dropdowns!) ---
        grp_mode = QGroupBox("🎨 Color && Layout (N-up)", settings_content)
        mode_layout = QVBoxLayout(grp_mode)
        mode_layout.setSpacing(8)

        mode_form = QFormLayout()
        mode_form.setContentsMargins(0, 0, 0, 0)
        mode_form.setHorizontalSpacing(10)
        mode_form.setVerticalSpacing(8)
        mode_form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        self.combo_color = QComboBox(grp_mode)
        self.combo_color.addItem("🔘 Black & White (Grayscale)", ColorMode.GRAYSCALE)
        self.combo_color.addItem("⬛ Pure Monochrome (High-Contrast)", ColorMode.MONOCHROME)
        self.combo_color.addItem("🌈 Original / Full Color", ColorMode.COLOR)
        self.combo_color.setCurrentIndex(0)  # Default: Grayscale B&W
        self.combo_color.currentIndexChanged.connect(self._on_color_mode_changed)
        mode_form.addRow("Color:", self.combo_color)

        self.combo_nup = QComboBox(grp_mode)
        self.combo_nup.addItem("1 Page / Sheet (Normal)", NUpMode.ONE_UP)
        self.combo_nup.addItem("2-in-1 (2 Pages / Sheet)", NUpMode.TWO_UP)
        self.combo_nup.addItem("4-in-1 (4 Pages / Sheet)", NUpMode.FOUR_UP)
        self.combo_nup.setCurrentIndex(0)
        self.combo_nup.currentIndexChanged.connect(self._on_nup_changed)
        mode_form.addRow("N-up:", self.combo_nup)

        mode_layout.addLayout(mode_form)

        self.chk_nup_borders = QCheckBox("Draw page borders", grp_mode)
        self.chk_nup_borders.setChecked(True)
        self.chk_nup_borders.setVisible(False)
        self.chk_nup_borders.toggled.connect(self._on_layout_option_changed)
        mode_layout.addWidget(self.chk_nup_borders)

        self.lbl_color_hint = QLabel("", grp_mode)
        self.lbl_color_hint.setObjectName("hintLabel")
        self.lbl_color_hint.setWordWrap(True)
        mode_layout.addWidget(self.lbl_color_hint)

        settings_vbox.addWidget(grp_mode)

        # --- 3. Page Range & Ordering Card (Clean Dropdown!) ---
        grp_pages = QGroupBox("📑 Page Range && Ordering", settings_content)
        pages_layout = QVBoxLayout(grp_pages)
        pages_layout.setSpacing(8)

        pages_form = QFormLayout()
        pages_form.setContentsMargins(0, 0, 0, 0)
        pages_form.setHorizontalSpacing(10)
        pages_form.setVerticalSpacing(8)

        self.combo_pages = QComboBox(grp_pages)
        self.combo_pages.addItem("All Pages", PageSelectionMode.ALL)
        self.combo_pages.addItem("Odd Pages Only (1, 3, 5...)", PageSelectionMode.ODD)
        self.combo_pages.addItem("Even Pages Only (2, 4, 6...)", PageSelectionMode.EVEN)
        self.combo_pages.addItem("Custom Range...", PageSelectionMode.CUSTOM)
        self.combo_pages.currentIndexChanged.connect(self._on_page_selection_changed)
        pages_form.addRow("Pages:", self.combo_pages)
        pages_layout.addLayout(pages_form)

        # Custom range row (shown only when "Custom Range..." is selected)
        self.custom_range_container = QWidget(grp_pages)
        custom_row = QHBoxLayout(self.custom_range_container)
        custom_row.setContentsMargins(0, 0, 0, 0)
        custom_row.setSpacing(6)
        lbl_range = QLabel("Range:", self.custom_range_container)
        self.txt_custom_range = QLineEdit(self.custom_range_container)
        self.txt_custom_range.setAcceptDrops(False)
        self.txt_custom_range.setPlaceholderText("e.g. 1-3, 5, 8-10")
        self.txt_custom_range.textChanged.connect(self._on_custom_range_edited)
        custom_row.addWidget(lbl_range)
        custom_row.addWidget(self.txt_custom_range, 1)
        self.custom_range_container.setVisible(False)
        pages_layout.addWidget(self.custom_range_container)

        self.chk_reverse_order = QCheckBox("🔄 Reverse Order (Print Back to Front)", grp_pages)
        self.chk_reverse_order.setToolTip(
            "Prints from the last page to the first page. Ideal for face-up printer trays!"
        )
        self.chk_reverse_order.setStyleSheet("font-weight: 600; color: #ffb74d;")
        self.chk_reverse_order.toggled.connect(self._on_reverse_order_toggled)
        pages_layout.addWidget(self.chk_reverse_order)

        self.lbl_page_summary = QLabel("Print Queue: 0 pages", grp_pages)
        self.lbl_page_summary.setObjectName("summaryBadge")
        self.lbl_page_summary.setWordWrap(True)
        pages_layout.addWidget(self.lbl_page_summary)

        settings_vbox.addWidget(grp_pages)

        # --- 4. Printer & Paper Setup Card ---
        grp_printer = QGroupBox("🖨️ Printer && Paper Setup", settings_content)
        printer_layout = QVBoxLayout(grp_printer)
        printer_layout.setSpacing(8)

        printer_sel_row = QHBoxLayout()
        printer_sel_row.setSpacing(6)
        self.combo_printers = QComboBox(grp_printer)
        self.combo_printers.currentIndexChanged.connect(self._on_printer_changed)
        self.btn_refresh_printers = QPushButton("🔄", grp_printer)
        self.btn_refresh_printers.setObjectName("toolBtn")
        self.btn_refresh_printers.setToolTip("Refresh Printer List")
        self.btn_refresh_printers.clicked.connect(self._load_printers)
        printer_sel_row.addWidget(self.combo_printers, 1)
        printer_sel_row.addWidget(self.btn_refresh_printers)
        printer_layout.addLayout(printer_sel_row)

        paper_form = QFormLayout()
        paper_form.setContentsMargins(0, 0, 0, 0)
        paper_form.setHorizontalSpacing(10)
        paper_form.setVerticalSpacing(8)

        self.combo_paper = QComboBox(grp_printer)
        self.combo_paper.addItems(["A4", "Letter", "Legal", "A3", "A5", "Executive"])
        self.combo_paper.currentIndexChanged.connect(self._on_layout_option_changed)
        paper_form.addRow("Paper:", self.combo_paper)

        self.combo_duplex = QComboBox(grp_printer)
        self.combo_duplex.addItem("Off (One-sided)", "simplex")
        self.combo_duplex.addItem("Auto Long-edge (Book)", "long-edge")
        self.combo_duplex.addItem("Auto Short-edge (Notepad)", "short-edge")
        paper_form.addRow("Duplex:", self.combo_duplex)

        copies_widget = QWidget(grp_printer)
        copies_row = QHBoxLayout(copies_widget)
        copies_row.setContentsMargins(0, 0, 0, 0)
        copies_row.setSpacing(10)
        self.spin_copies = QSpinBox(copies_widget)
        self.spin_copies.setRange(1, 999)
        self.spin_copies.setValue(1)
        self.spin_copies.setMinimumWidth(68)
        self.chk_collate = QCheckBox("Collate", copies_widget)
        self.chk_collate.setChecked(True)
        copies_row.addWidget(self.spin_copies)
        copies_row.addWidget(self.chk_collate)
        copies_row.addStretch()
        paper_form.addRow("Copies:", copies_widget)

        printer_layout.addLayout(paper_form)

        self.chk_fit_page = QCheckBox("Fit to Printable Area", grp_printer)
        self.chk_fit_page.setChecked(True)
        printer_layout.addWidget(self.chk_fit_page)

        settings_vbox.addWidget(grp_printer)
        settings_vbox.addStretch(1)

        # Ensure dropdowns shrink smoothly with sidebar width instead of overflowing horizontally
        for combo in (
            self.combo_color, self.combo_nup, self.combo_pages,
            self.combo_printers, self.combo_paper, self.combo_duplex
        ):
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(8)

        self.settings_scroll.setWidget(settings_content)
        sidebar_outer.addWidget(self.settings_scroll, 1)

        # --- 5. Pinned Bottom Action Footer (Always Visible!) ---
        footer = QFrame(sidebar_root)
        footer.setObjectName("actionFooter")
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(8, 8, 8, 8)
        footer_layout.setSpacing(7)

        self.btn_print_now = QPushButton("🖨️ Print Now", footer)
        self.btn_print_now.setObjectName("primaryButton")
        self.btn_print_now.clicked.connect(self.action_print_now)

        self.btn_manual_duplex = QPushButton("🔄 1-Click Manual Duplex", footer)
        self.btn_manual_duplex.setObjectName("duplexButton")
        self.btn_manual_duplex.setToolTip(
            "Prints Odd pages first, prompts you to flip & reinsert paper, then prints Even pages in reverse!"
        )
        self.btn_manual_duplex.clicked.connect(self.action_manual_duplex)

        secondary_row = QHBoxLayout()
        secondary_row.setSpacing(6)

        self.btn_export_pdf = QPushButton("💾 Export PDF", footer)
        self.btn_export_pdf.setObjectName("secondaryButton")
        self.btn_export_pdf.clicked.connect(self.action_export_pdf)

        self.btn_system_dialog = QPushButton("⚙️ System Dialog", footer)
        self.btn_system_dialog.clicked.connect(self.action_system_dialog)

        secondary_row.addWidget(self.btn_export_pdf, 1)
        secondary_row.addWidget(self.btn_system_dialog, 1)

        footer_layout.addWidget(self.btn_print_now)
        footer_layout.addWidget(self.btn_manual_duplex)
        footer_layout.addLayout(secondary_row)

        sidebar_outer.addWidget(footer, 0)

        main_splitter.addWidget(sidebar_root)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(180)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.status_bar.showMessage("Ready. Drag & drop a PDF or image anywhere, or click Open.")

    # ------------------------------------------------------------------
    # Printer Discovery & File Loading
    # ------------------------------------------------------------------

    def _load_printers(self):
        self.combo_printers.clear()
        printers = self.cups_manager.get_printers()
        default_index = 0
        for i, p in enumerate(printers):
            self.combo_printers.addItem(p.description, p.name)
            if p.is_default:
                default_index = i
        if printers:
            self.combo_printers.setCurrentIndex(default_index)
            self._on_printer_changed(default_index)

    def _on_printer_changed(self, _index: int):
        printer_name = self.combo_printers.currentData()
        if not printer_name or printer_name == "Print_to_PDF":
            return

        caps = self.cups_manager.get_printer_capabilities(printer_name)
        model = self.combo_duplex.model()
        for row in (1, 2):
            item = model.item(row) if hasattr(model, "item") else None
            if item is not None:
                item.setEnabled(caps.supports_duplex)

        if not caps.supports_duplex:
            self.combo_duplex.setCurrentIndex(0)
            self.combo_duplex.setToolTip(
                f"'{printer_name}' does not support hardware auto-duplex.\n"
                "Use the '1-Click Manual Duplex' button below for double-sided printing!"
            )
        else:
            self.combo_duplex.setToolTip("Automatic hardware duplex mode")

    def action_open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF or Image",
            "",
            "Supported Files (*.pdf *.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff);;"
            "PDF Files (*.pdf);;"
            "Images (*.png *.jpg *.jpeg *.bmp *.webp *.tif *.tiff);;"
            "All Files (*)"
        )
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: str):
        if not is_supported_file(file_path):
            QMessageBox.warning(
                self,
                "Unsupported File",
                f"Cannot open '{os.path.basename(file_path)}'.\n\n"
                "Supported formats: PDF, PNG, JPG, JPEG, WebP, BMP, TIFF."
            )
            return

        try:
            if self.doc_model:
                self.doc_model.close()

            self.doc_model = DocumentModel(file_path)
            self.lbl_file_name.setText(os.path.basename(file_path))
            self.lbl_file_details.setText(
                f"{'Image' if self.doc_model.is_image else 'PDF Document'}  •  "
                f"{self.doc_model.total_pages} page(s)"
            )

            self.preview_widget.color_mode = self._get_selected_color_mode()
            self.preview_widget.set_document(self.doc_model)

            self._update_print_queue_summary()
            self.status_bar.showMessage(f"Loaded: {os.path.basename(file_path)}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Error Opening File", f"Failed to open {file_path}:\n{str(e)}")

    # ------------------------------------------------------------------
    # Settings Accessors & Live Preview Updates
    # ------------------------------------------------------------------

    def _get_selected_color_mode(self) -> ColorMode:
        mode = self.combo_color.currentData()
        return mode if isinstance(mode, ColorMode) else ColorMode.GRAYSCALE

    def _get_selected_nup_mode(self) -> NUpMode:
        mode = self.combo_nup.currentData()
        return mode if isinstance(mode, NUpMode) else NUpMode.ONE_UP

    def _get_selected_page_mode(self) -> PageSelectionMode:
        mode = self.combo_pages.currentData()
        return mode if isinstance(mode, PageSelectionMode) else PageSelectionMode.ALL

    def _get_target_pages_list(self) -> List[int]:
        if not self.doc_model or self.doc_model.total_pages == 0:
            return []
        mode = self._get_selected_page_mode()
        custom = self.txt_custom_range.text()
        rev = self.chk_reverse_order.isChecked()
        return get_target_pages(self.doc_model.total_pages, mode, custom, rev)

    def _update_color_hint(self):
        mode = self._get_selected_color_mode()
        if mode == ColorMode.GRAYSCALE:
            self.lbl_color_hint.setText("💡 True Grayscale B&W — guarantees zero color ink usage.")
            self.lbl_color_hint.setStyleSheet("color: #8bc399; font-size: 11px;")
        elif mode == ColorMode.MONOCHROME:
            self.lbl_color_hint.setText("💡 Pure 1-bit B&W — crisp high-contrast text, max toner saving.")
            self.lbl_color_hint.setStyleSheet("color: #8bc399; font-size: 11px;")
        else:
            self.lbl_color_hint.setText("🎨 Full original document colors preserved.")
            self.lbl_color_hint.setStyleSheet("color: #90caf9; font-size: 11px;")

    def _on_color_mode_changed(self, _index: int):
        mode = self._get_selected_color_mode()
        self._update_color_hint()
        self.preview_widget.set_color_mode(mode)
        self._update_print_queue_summary()

    def _on_nup_changed(self, _index: int):
        n_up = self._get_selected_nup_mode()
        self.chk_nup_borders.setVisible(n_up != NUpMode.ONE_UP)
        self._update_print_queue_summary()

    def _on_layout_option_changed(self, *_args):
        self._update_print_queue_summary()

    def _on_page_selection_changed(self, _index: int):
        is_custom = (self._get_selected_page_mode() == PageSelectionMode.CUSTOM)
        self.custom_range_container.setVisible(is_custom)
        if is_custom:
            self.txt_custom_range.setFocus()
        self._update_print_queue_summary()

    def _on_custom_range_edited(self, _text: str):
        self._update_print_queue_summary()

    def _on_reverse_order_toggled(self, _checked: bool):
        self._update_print_queue_summary()

    def _update_print_queue_summary(self):
        pages = self._get_target_pages_list()
        n_up = self._get_selected_nup_mode()
        paper_size = self.combo_paper.currentText() if hasattr(self, "combo_paper") else "A4"
        draw_borders = self.chk_nup_borders.isChecked() if hasattr(self, "chk_nup_borders") else True

        self.preview_widget.set_print_layout(
            ordered_pages=pages,
            n_up=n_up,
            paper_size=paper_size,
            draw_borders=draw_borders
        )

        if not pages:
            self.lbl_page_summary.setText("Print Queue: 0 pages selected")
            return

        sheets = group_pages_into_sheets(pages, n_up.value)
        if len(pages) <= 8:
            order_str = f"[{', '.join(str(p) for p in pages)}]"
        else:
            order_str = f"[{pages[0]}, {pages[1]}, {pages[2]} ... {pages[-1]}]"

        rev_tag = " • Reversed" if self.chk_reverse_order.isChecked() else ""
        if n_up == NUpMode.ONE_UP:
            self.lbl_page_summary.setText(
                f"Queue: {len(pages)} page(s){rev_tag}\nOrder: {order_str}"
            )
        else:
            self.lbl_page_summary.setText(
                f"Queue: {len(pages)} page(s) → {len(sheets)} sheet(s) ({n_up.value}-in-1){rev_tag}\n"
                f"Order: {order_str}"
            )

    def _set_busy(self, busy: bool, message: str = ""):
        self.progress_bar.setVisible(busy)
        if busy:
            self.progress_bar.setRange(0, 0)
        if message:
            self.status_bar.showMessage(message)
        QApplication.processEvents()

    # ------------------------------------------------------------------
    # Print, 1-Click Manual Duplex, Export, System Print Dialog
    # ------------------------------------------------------------------

    def action_print_now(self):
        if not self.doc_model or self.doc_model.total_pages == 0:
            QMessageBox.warning(self, "No Document", "Please open a PDF or image file first.")
            return

        pages = self._get_target_pages_list()
        if not pages:
            QMessageBox.warning(self, "No Pages", "No pages are selected to print.")
            return

        printer_name = self.combo_printers.currentData()
        if not printer_name:
            QMessageBox.warning(self, "No Printer", "No printer is selected or CUPS is unavailable.")
            return

        if printer_name == "Print_to_PDF":
            self.action_export_pdf()
            return

        temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        temp_pdf.close()

        color_mode = self._get_selected_color_mode()
        n_up = self._get_selected_nup_mode()
        paper_size = self.combo_paper.currentText()
        draw_borders = self.chk_nup_borders.isChecked()
        sheets = group_pages_into_sheets(pages, n_up.value)

        self._set_busy(True, "Processing print job...")

        try:
            success = self.doc_model.export_processed_pdf(
                output_path=temp_pdf.name,
                selection_mode=self._get_selected_page_mode(),
                custom_range=self.txt_custom_range.text(),
                reverse=self.chk_reverse_order.isChecked(),
                color_mode=color_mode,
                render_dpi=300,
                n_up=n_up,
                paper_size=paper_size,
                draw_borders=draw_borders
            )

            if not success:
                QMessageBox.critical(self, "Error", "Failed to generate print job document.")
                return

            copies = self.spin_copies.value()
            duplex = self.combo_duplex.currentData()
            fit_page = self.chk_fit_page.isChecked()
            force_gray = (color_mode != ColorMode.COLOR)

            print_success, msg = self.cups_manager.print_file(
                file_path=temp_pdf.name,
                printer_name=printer_name,
                copies=copies,
                page_size=paper_size,
                orientation="auto",
                duplex=duplex,
                force_grayscale=force_gray,
                fit_to_page=fit_page,
                job_title=f"PrintStudio - {os.path.basename(self.doc_model.original_path)}"
            )

            if print_success:
                nup_info = f" ({n_up.value}-in-1, {len(sheets)} sheets)" if n_up != NUpMode.ONE_UP else ""
                QMessageBox.information(
                    self,
                    "Print Sent Successfully",
                    f"Job submitted to '{printer_name}'!\n\n"
                    f"Pages: {len(pages)}{nup_info} {'(Reversed)' if self.chk_reverse_order.isChecked() else ''}\n"
                    f"Color Mode: {color_mode.value.capitalize()}\n"
                    f"Copies: {copies}\n\n{msg}"
                )
                self.status_bar.showMessage("Print job sent successfully.", 5000)
            else:
                QMessageBox.critical(self, "Printing Failed", f"Could not print:\n{msg}")
                self.status_bar.showMessage("Print job failed.", 5000)
        finally:
            self._set_busy(False)
            if os.path.exists(temp_pdf.name):
                try:
                    os.remove(temp_pdf.name)
                except Exception:
                    pass

    def action_manual_duplex(self):
        """
        1-Click Manual Duplex Workflow:
        Step 1: Automatically prints Odd sheets (1, 3, 5...).
        Step 2: Prompts the user to flip & reinsert the stack into the tray.
        Step 3: On Continue, automatically prints Even sheets in reverse order (..., 6, 4, 2).
        Works seamlessly with Custom Ranges, Color/B&W mode, and N-up (2-in-1 / 4-in-1)!
        """
        if not self.doc_model or self.doc_model.total_pages == 0:
            QMessageBox.warning(self, "No Document", "Please open a PDF or image file first.")
            return

        printer_name = self.combo_printers.currentData()
        if not printer_name:
            QMessageBox.warning(self, "No Printer", "No printer is selected or CUPS is unavailable.")
            return

        # Determine source pages: honor Custom Range if selected, otherwise full document in logical order
        page_mode = self._get_selected_page_mode()
        if page_mode == PageSelectionMode.CUSTOM:
            logical_pages = get_target_pages(
                self.doc_model.total_pages,
                PageSelectionMode.CUSTOM,
                custom_range=self.txt_custom_range.text(),
                reverse=False
            )
        else:
            logical_pages = get_target_pages(
                self.doc_model.total_pages,
                PageSelectionMode.ALL,
                reverse=False
            )

        n_up = self._get_selected_nup_mode()
        paper_size = self.combo_paper.currentText()
        draw_borders = self.chk_nup_borders.isChecked()
        color_mode = self._get_selected_color_mode()
        copies = self.spin_copies.value()
        fit_page = self.chk_fit_page.isChecked()
        force_gray = (color_mode != ColorMode.COLOR)

        sheets = group_pages_into_sheets(logical_pages, n_up.value)
        if len(sheets) <= 1:
            QMessageBox.information(
                self,
                "Single Sheet Document",
                "Only 1 sheet is needed for this document, so Manual Duplex is not required.\n"
                "Please use 'Print Now' instead."
            )
            return

        pass1_sheets, pass2_normal_sheets, has_trailing_odd = split_manual_duplex_sheets(
            sheets, reverse_even=False
        )

        # Handle Print_to_PDF fallback cleanly (export Pass 1 & Pass 2 PDFs)
        if printer_name == "Print_to_PDF":
            self._manual_duplex_export_pdfs(
                pass1_sheets, pass2_normal_sheets, has_trailing_odd,
                n_up, paper_size, draw_borders, color_mode
            )
            return

        # --- PASS 1: Print Odd Sheets ---
        temp_p1 = tempfile.NamedTemporaryFile(suffix="_odd.pdf", delete=False)
        temp_p1.close()
        self._set_busy(True, "Manual Duplex Step 1/2: Printing Odd pages...")

        try:
            ok1 = self.doc_model.export_processed_pdf(
                output_path=temp_p1.name,
                color_mode=color_mode,
                render_dpi=300,
                n_up=n_up,
                paper_size=paper_size,
                draw_borders=draw_borders,
                explicit_sheets=pass1_sheets
            )
            if not ok1:
                QMessageBox.critical(self, "Error", "Failed to prepare Pass 1 (Odd pages) PDF.")
                return

            sent1, msg1 = self.cups_manager.print_file(
                file_path=temp_p1.name,
                printer_name=printer_name,
                copies=copies,
                page_size=paper_size,
                orientation="auto",
                duplex="simplex",
                force_grayscale=force_gray,
                fit_to_page=fit_page,
                job_title=f"PrintStudio Duplex P1 (Odd) - {os.path.basename(self.doc_model.original_path)}"
            )
        finally:
            self._set_busy(False)
            if os.path.exists(temp_p1.name):
                try:
                    os.remove(temp_p1.name)
                except Exception:
                    pass

        if not sent1:
            QMessageBox.critical(self, "Manual Duplex Failed (Step 1)", f"Could not print Odd pages:\n{msg1}")
            self.status_bar.showMessage("Manual Duplex Pass 1 failed.", 5000)
            return

        self.status_bar.showMessage("Pass 1 (Odd) sent! Flip paper and click Continue for Even pages.")

        # --- Interactive Prompt: Flip & Reinsert Paper ---
        dialog = ManualDuplexDialog(
            pass1_sheets=pass1_sheets,
            even_sheets_normal=pass2_normal_sheets,
            has_trailing_odd=has_trailing_odd,
            n_up=n_up.value,
            printer_name=printer_name,
            parent=self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            self.status_bar.showMessage("Manual Duplex cancelled after Pass 1 (Odd pages already sent).", 5000)
            return

        # --- PASS 2: Print Even Sheets (Reversed by Default) ---
        pass2_sheets = dialog.get_pass2_sheets()
        temp_p2 = tempfile.NamedTemporaryFile(suffix="_even.pdf", delete=False)
        temp_p2.close()
        self._set_busy(True, "Manual Duplex Step 2/2: Printing Even pages...")

        try:
            ok2 = self.doc_model.export_processed_pdf(
                output_path=temp_p2.name,
                color_mode=color_mode,
                render_dpi=300,
                n_up=n_up,
                paper_size=paper_size,
                draw_borders=draw_borders,
                explicit_sheets=pass2_sheets
            )
            if not ok2:
                QMessageBox.critical(self, "Error", "Failed to prepare Pass 2 (Even pages) PDF.")
                return

            sent2, msg2 = self.cups_manager.print_file(
                file_path=temp_p2.name,
                printer_name=printer_name,
                copies=copies,
                page_size=paper_size,
                orientation="auto",
                duplex="simplex",
                force_grayscale=force_gray,
                fit_to_page=fit_page,
                job_title=f"PrintStudio Duplex P2 (Even) - {os.path.basename(self.doc_model.original_path)}"
            )

            if sent2:
                QMessageBox.information(
                    self,
                    "Manual Duplex Complete",
                    f"Both sides submitted to '{printer_name}'!\n\n"
                    f"Pass 1 (Odd): {len(pass1_sheets)} sheet(s)\n"
                    f"Pass 2 (Even): {len(pass2_sheets)} sheet(s)\n\n{msg2}"
                )
                self.status_bar.showMessage("Manual Duplex print complete!", 5000)
            else:
                QMessageBox.critical(self, "Manual Duplex Failed (Step 2)", f"Could not print Even pages:\n{msg2}")
                self.status_bar.showMessage("Manual Duplex Pass 2 failed.", 5000)
        finally:
            self._set_busy(False)
            if os.path.exists(temp_p2.name):
                try:
                    os.remove(temp_p2.name)
                except Exception:
                    pass

    def _manual_duplex_export_pdfs(
        self,
        pass1_sheets: List[List[int]],
        pass2_normal_sheets: List[List[int]],
        has_trailing_odd: bool,
        n_up: NUpMode,
        paper_size: str,
        draw_borders: bool,
        color_mode: ColorMode
    ):
        """Fallback when Print_to_PDF is selected: exports separate Pass 1 & Pass 2 PDFs."""
        out_dir = QFileDialog.getExistingDirectory(
            self,
            "Select Folder to Save Manual Duplex PDFs (Odd & Even)"
        )
        if not out_dir:
            return

        base_name = os.path.splitext(os.path.basename(self.doc_model.original_path))[0]
        p1_path = os.path.join(out_dir, f"{base_name}_duplex_pass1_odd.pdf")
        p2_path = os.path.join(out_dir, f"{base_name}_duplex_pass2_even_reversed.pdf")

        self._set_busy(True, "Exporting Manual Duplex Pass 1 & Pass 2 PDFs...")
        try:
            ok1 = self.doc_model.export_processed_pdf(
                output_path=p1_path,
                color_mode=color_mode,
                render_dpi=300,
                n_up=n_up,
                paper_size=paper_size,
                draw_borders=draw_borders,
                explicit_sheets=pass1_sheets
            )
            ok2 = self.doc_model.export_processed_pdf(
                output_path=p2_path,
                color_mode=color_mode,
                render_dpi=300,
                n_up=n_up,
                paper_size=paper_size,
                draw_borders=draw_borders,
                explicit_sheets=list(reversed(pass2_normal_sheets))
            )
            if ok1 and ok2:
                extra = "\n⚠️ Note: Odd sheet count — set aside the last sheet of Pass 1 before flipping." if has_trailing_odd else ""
                QMessageBox.information(
                    self,
                    "Manual Duplex PDFs Exported",
                    f"Saved two print-ready PDFs:\n\n"
                    f"1. {os.path.basename(p1_path)} ({len(pass1_sheets)} sheets)\n"
                    f"2. {os.path.basename(p2_path)} ({len(pass2_normal_sheets)} sheets){extra}"
                )
        finally:
            self._set_busy(False)

    def action_export_pdf(self):
        if not self.doc_model or self.doc_model.total_pages == 0:
            QMessageBox.warning(self, "No Document", "Please open a PDF or image file first.")
            return

        pages = self._get_target_pages_list()
        if not pages:
            QMessageBox.warning(self, "No Pages", "No pages are selected to export.")
            return

        n_up = self._get_selected_nup_mode()
        paper_size = self.combo_paper.currentText()
        draw_borders = self.chk_nup_borders.isChecked()
        sheets = group_pages_into_sheets(pages, n_up.value)

        base_name = os.path.splitext(os.path.basename(self.doc_model.original_path))[0]
        color_tag = "bw" if self._get_selected_color_mode() != ColorMode.COLOR else "color"
        nup_tag = f"_{n_up.value}up" if n_up != NUpMode.ONE_UP else ""
        rev_tag = "_reversed" if self.chk_reverse_order.isChecked() else ""
        suggested_name = f"{base_name}_{color_tag}{nup_tag}{rev_tag}.pdf"

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Processed PDF",
            suggested_name,
            "PDF Files (*.pdf)"
        )
        if not out_path:
            return

        self._set_busy(True, "Exporting PDF...")

        try:
            success = self.doc_model.export_processed_pdf(
                output_path=out_path,
                selection_mode=self._get_selected_page_mode(),
                custom_range=self.txt_custom_range.text(),
                reverse=self.chk_reverse_order.isChecked(),
                color_mode=self._get_selected_color_mode(),
                render_dpi=300,
                n_up=n_up,
                paper_size=paper_size,
                draw_borders=draw_borders
            )
            if success:
                QMessageBox.information(
                    self,
                    "Export Succeeded",
                    f"Successfully exported {len(pages)} page(s) into {len(sheets)} sheet(s) to:\n{out_path}"
                )
                self.status_bar.showMessage(f"Exported to {os.path.basename(out_path)}", 4000)
            else:
                QMessageBox.critical(self, "Export Failed", "Could not generate exported PDF.")
        finally:
            self._set_busy(False)

    def action_system_dialog(self):
        """
        Opens the system print dialog using the processed PDF so that all page ordering,
        N-up composition, reverse order, and grayscale options are strictly preserved.
        """
        if not self.doc_model or self.doc_model.total_pages == 0:
            QMessageBox.warning(self, "No Document", "Please open a PDF or image file first.")
            return

        temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        temp_pdf.close()
        self._set_busy(True, "Preparing document for System Print Dialog...")

        try:
            success = self.doc_model.export_processed_pdf(
                output_path=temp_pdf.name,
                selection_mode=self._get_selected_page_mode(),
                custom_range=self.txt_custom_range.text(),
                reverse=self.chk_reverse_order.isChecked(),
                color_mode=self._get_selected_color_mode(),
                render_dpi=300,
                n_up=self._get_selected_nup_mode(),
                paper_size=self.combo_paper.currentText(),
                draw_borders=self.chk_nup_borders.isChecked()
            )
            self._set_busy(False)
            if not success:
                return

            printer = QPrinter(QPrinter.PrinterMode.HighResolution)
            dialog = QPrintDialog(printer, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                printer_name = printer.printerName()
                self.cups_manager.print_file(
                    file_path=temp_pdf.name,
                    printer_name=printer_name,
                    copies=printer.copyCount(),
                    orientation="auto",
                    force_grayscale=(self._get_selected_color_mode() != ColorMode.COLOR),
                    job_title="PrintStudio Job"
                )
        finally:
            self._set_busy(False)
            if os.path.exists(temp_pdf.name):
                try:
                    os.remove(temp_pdf.name)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Enhanced Drag & Drop Support with Visual Feedback
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_local_file(event) -> Optional[str]:
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile():
                    path = url.toLocalFile()
                    if path and os.path.isfile(path):
                        return path
        return None

    def dragEnterEvent(self, event: QDragEnterEvent):
        path = self._extract_local_file(event)
        if path:
            event.acceptProposedAction()
            self.preview_widget.set_drag_active(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event: QDragMoveEvent):
        if self._extract_local_file(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent):
        self.preview_widget.set_drag_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent):
        self.preview_widget.set_drag_active(False)
        path = self._extract_local_file(event)
        if path:
            event.acceptProposedAction()
            self.load_file(path)
        else:
            event.ignore()
