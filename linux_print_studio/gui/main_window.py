"""
Main Application Window for Linux Print Studio.
"""

import os
import sys
import tempfile
from typing import Optional, List

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QAction, QIcon, QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QGroupBox, QRadioButton, QButtonGroup, QCheckBox, QLineEdit,
    QComboBox, QSpinBox, QLabel, QPushButton, QFileDialog,
    QMessageBox, QStatusBar, QProgressBar, QDialog
)
from PyQt6.QtPrintSupport import QPrinter, QPrintDialog

from linux_print_studio.core.pdf_processor import (
    DocumentModel, PageSelectionMode, ColorMode, get_target_pages
)
from linux_print_studio.core.cups_manager import CupsManager
from linux_print_studio.gui.preview_widget import PreviewWidget


class MainWindow(QMainWindow):
    def __init__(self, initial_file: Optional[str] = None):
        super().__init__()

        self.setWindowTitle("Linux Print Studio - Professional PDF & Image Printing")
        self.resize(1150, 750)
        self.setMinimumSize(850, 550)
        self.setAcceptDrops(True)

        self.doc_model: Optional[DocumentModel] = None
        self.cups_manager = CupsManager()

        self._init_ui()
        self._load_printers()

        if initial_file and os.path.exists(initial_file):
            self.load_file(initial_file)

    def _init_ui(self):
        # Central Splitter
        main_splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.setCentralWidget(main_splitter)

        # Left: Interactive Preview Area
        preview_container = QWidget(self)
        preview_vbox = QVBoxLayout(preview_container)
        preview_vbox.setContentsMargins(10, 10, 10, 10)

        self.preview_widget = PreviewWidget(self)
        preview_vbox.addWidget(self.preview_widget)
        main_splitter.addWidget(preview_container)

        # Right: Settings & Actions Panel
        settings_panel = QWidget(self)
        settings_panel.setMaximumWidth(450)
        settings_panel.setMinimumWidth(340)
        settings_vbox = QVBoxLayout(settings_panel)
        settings_vbox.setContentsMargins(10, 10, 10, 10)
        settings_vbox.setSpacing(12)

        # --- 1. File & Document Info Group ---
        grp_file = QGroupBox("📄 Document", self)
        file_layout = QVBoxLayout(grp_file)

        file_btn_row = QHBoxLayout()
        self.btn_open_file = QPushButton("📂 Open PDF / Image...", self)
        self.btn_open_file.clicked.connect(self.action_open_file)
        file_btn_row.addWidget(self.btn_open_file)
        file_layout.addLayout(file_btn_row)

        self.lbl_file_name = QLabel("No file selected", self)
        self.lbl_file_name.setWordWrap(True)
        self.lbl_file_name.setStyleSheet("color: #90caf9; font-weight: bold;")
        self.lbl_file_details = QLabel("Total pages: 0", self)
        self.lbl_file_details.setStyleSheet("color: #b0bec5; font-size: 11px;")
        file_layout.addWidget(self.lbl_file_name)
        file_layout.addWidget(self.lbl_file_details)
        settings_vbox.addWidget(grp_file)

        # --- 2. Color & Toner Mode (User's Critical Request) ---
        grp_color = QGroupBox("🎨 Color & Toner Mode (Force B&W)", self)
        color_layout = QVBoxLayout(grp_color)

        self.color_group = QButtonGroup(self)
        self.rb_color_original = QRadioButton("🌈 Original / Full Color", self)
        self.rb_color_gray = QRadioButton("🔘 Black & White (Grayscale)", self)
        self.rb_color_mono = QRadioButton("⬛ Pure Monochrome (High-Contrast B&W)", self)

        # Default to Grayscale as requested by user
        self.rb_color_gray.setChecked(True)

        self.color_group.addButton(self.rb_color_original, 0)
        self.color_group.addButton(self.rb_color_gray, 1)
        self.color_group.addButton(self.rb_color_mono, 2)
        self.color_group.idClicked.connect(self._on_color_mode_changed)

        lbl_color_hint = QLabel(
            "💡 Dedicated B&W Mode: Document is converted to true grayscale "
            "before printing. Printer will NOT use color ink/toner even if "
            "system default is set to color!", self
        )
        lbl_color_hint.setWordWrap(True)
        lbl_color_hint.setStyleSheet("color: #81c784; font-size: 11px; margin-top: 4px;")

        color_layout.addWidget(self.rb_color_original)
        color_layout.addWidget(self.rb_color_gray)
        color_layout.addWidget(self.rb_color_mono)
        color_layout.addWidget(lbl_color_hint)
        settings_vbox.addWidget(grp_color)

        # --- 3. Page Selection & Reverse Order ---
        grp_pages = QGroupBox("📑 Page Range & Ordering", self)
        pages_layout = QVBoxLayout(grp_pages)

        self.pages_group = QButtonGroup(self)
        self.rb_pages_all = QRadioButton("All Pages", self)
        self.rb_pages_all.setChecked(True)
        self.rb_pages_odd = QRadioButton("Odd Pages Only (1, 3, 5, ...)", self)
        self.rb_pages_even = QRadioButton("Even Pages Only (2, 4, 6, ...)", self)
        self.rb_pages_custom = QRadioButton("Custom Range:", self)

        self.pages_group.addButton(self.rb_pages_all, 0)
        self.pages_group.addButton(self.rb_pages_odd, 1)
        self.pages_group.addButton(self.rb_pages_even, 2)
        self.pages_group.addButton(self.rb_pages_custom, 3)
        self.pages_group.idClicked.connect(self._on_page_selection_changed)

        custom_row = QHBoxLayout()
        self.txt_custom_range = QLineEdit(self)
        self.txt_custom_range.setPlaceholderText("e.g. 1-3, 5, 8-10")
        self.txt_custom_range.setEnabled(False)
        self.txt_custom_range.textChanged.connect(self._on_custom_range_edited)
        custom_row.addWidget(self.rb_pages_custom)
        custom_row.addWidget(self.txt_custom_range)

        # Dedicated Reverse Order Checkbox (Requested by user)
        self.chk_reverse_order = QCheckBox("🔄 Reverse Order (Print Back to Front)", self)
        self.chk_reverse_order.setToolTip("Prints from the last page to the first page. Ideal for face-up printer trays!")
        self.chk_reverse_order.setStyleSheet("font-weight: bold; color: #ffb74d;")
        self.chk_reverse_order.toggled.connect(self._on_reverse_order_toggled)

        self.lbl_page_summary = QLabel("Print Queue: 0 pages", self)
        self.lbl_page_summary.setStyleSheet("color: #ce93d8; font-weight: bold; font-size: 11px;")

        pages_layout.addWidget(self.rb_pages_all)
        pages_layout.addWidget(self.rb_pages_odd)
        pages_layout.addWidget(self.rb_pages_even)
        pages_layout.addLayout(custom_row)
        pages_layout.addSpacing(6)
        pages_layout.addWidget(self.chk_reverse_order)
        pages_layout.addWidget(self.lbl_page_summary)
        settings_vbox.addWidget(grp_pages)

        # --- 4. Printer & Paper Settings ---
        grp_printer = QGroupBox("🖨️ Printer & Paper Setup", self)
        printer_layout = QVBoxLayout(grp_printer)

        printer_sel_row = QHBoxLayout()
        self.combo_printers = QComboBox(self)
        self.btn_refresh_printers = QPushButton("🔄", self)
        self.btn_refresh_printers.setToolTip("Refresh Printer List")
        self.btn_refresh_printers.clicked.connect(self._load_printers)
        printer_sel_row.addWidget(self.combo_printers, 1)
        printer_sel_row.addWidget(self.btn_refresh_printers)
        printer_layout.addLayout(printer_sel_row)

        copies_row = QHBoxLayout()
        lbl_copies = QLabel("Copies:", self)
        self.spin_copies = QSpinBox(self)
        self.spin_copies.setRange(1, 999)
        self.spin_copies.setValue(1)
        self.chk_collate = QCheckBox("Collate", self)
        self.chk_collate.setChecked(True)
        copies_row.addWidget(lbl_copies)
        copies_row.addWidget(self.spin_copies)
        copies_row.addWidget(self.chk_collate)
        copies_row.addStretch()
        printer_layout.addLayout(copies_row)

        paper_row = QHBoxLayout()
        lbl_paper = QLabel("Paper Size:", self)
        self.combo_paper = QComboBox(self)
        self.combo_paper.addItems(["A4", "Letter", "Legal", "A3", "A5", "Executive"])
        paper_row.addWidget(lbl_paper)
        paper_row.addWidget(self.combo_paper)
        printer_layout.addLayout(paper_row)

        duplex_row = QHBoxLayout()
        lbl_duplex = QLabel("Two-sided:", self)
        self.combo_duplex = QComboBox(self)
        self.combo_duplex.addItem("Off (One-sided)", "simplex")
        self.combo_duplex.addItem("Long-edge (Book)", "long-edge")
        self.combo_duplex.addItem("Short-edge (Notepad)", "short-edge")
        duplex_row.addWidget(lbl_duplex)
        duplex_row.addWidget(self.combo_duplex)
        printer_layout.addLayout(duplex_row)

        self.chk_fit_page = QCheckBox("Fit to Printable Area", self)
        self.chk_fit_page.setChecked(True)
        printer_layout.addWidget(self.chk_fit_page)

        settings_vbox.addWidget(grp_printer)

        # --- 5. Action Buttons ---
        settings_vbox.addStretch()

        self.btn_print_now = QPushButton("🖨️ Print Now", self)
        self.btn_print_now.setObjectName("primaryButton")
        self.btn_print_now.clicked.connect(self.action_print_now)

        self.btn_export_pdf = QPushButton("💾 Export Processed PDF...", self)
        self.btn_export_pdf.setObjectName("secondaryButton")
        self.btn_export_pdf.clicked.connect(self.action_export_pdf)

        self.btn_system_dialog = QPushButton("⚙️ System Print Dialog...", self)
        self.btn_system_dialog.clicked.connect(self.action_system_dialog)

        settings_vbox.addWidget(self.btn_print_now)
        settings_vbox.addWidget(self.btn_export_pdf)
        settings_vbox.addWidget(self.btn_system_dialog)

        main_splitter.addWidget(settings_panel)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)

        # Status Bar
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        self.status_bar.addPermanentWidget(self.progress_bar)
        self.status_bar.showMessage("Ready. Open a PDF or image file to begin.")

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

    def action_open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF or Image",
            "",
            "Supported Files (*.pdf *.png *.jpg *.jpeg *.bmp *.webp *.tiff);;PDF Files (*.pdf);;Images (*.png *.jpg *.jpeg *.bmp *.webp *.tiff);;All Files (*)"
        )
        if file_path:
            self.load_file(file_path)

    def load_file(self, file_path: str):
        try:
            if self.doc_model:
                self.doc_model.close()

            self.doc_model = DocumentModel(file_path)
            self.lbl_file_name.setText(os.path.basename(file_path))
            self.lbl_file_details.setText(
                f"Type: {'Image' if self.doc_model.is_image else 'PDF Document'} | "
                f"Pages: {self.doc_model.total_pages}"
            )

            # Update preview color mode
            current_color_mode = self._get_selected_color_mode()
            self.preview_widget.color_mode = current_color_mode
            self.preview_widget.set_document(self.doc_model)

            self._update_print_queue_summary()
            self.status_bar.showMessage(f"Loaded: {os.path.basename(file_path)}", 4000)
        except Exception as e:
            QMessageBox.critical(self, "Error Opening File", f"Failed to open {file_path}:\n{str(e)}")

    def _get_selected_color_mode(self) -> ColorMode:
        cid = self.color_group.checkedId()
        if cid == 0:
            return ColorMode.COLOR
        elif cid == 1:
            return ColorMode.GRAYSCALE
        elif cid == 2:
            return ColorMode.MONOCHROME
        return ColorMode.GRAYSCALE

    def _get_selected_page_mode(self) -> PageSelectionMode:
        pid = self.pages_group.checkedId()
        if pid == 0:
            return PageSelectionMode.ALL
        elif pid == 1:
            return PageSelectionMode.ODD
        elif pid == 2:
            return PageSelectionMode.EVEN
        elif pid == 3:
            return PageSelectionMode.CUSTOM
        return PageSelectionMode.ALL

    def _get_target_pages_list(self) -> List[int]:
        if not self.doc_model or self.doc_model.total_pages == 0:
            return []
        mode = self._get_selected_page_mode()
        custom = self.txt_custom_range.text()
        rev = self.chk_reverse_order.isChecked()
        return get_target_pages(self.doc_model.total_pages, mode, custom, rev)

    def _on_color_mode_changed(self, btn_id: int):
        mode = self._get_selected_color_mode()
        self.preview_widget.set_color_mode(mode)
        self._update_print_queue_summary()

    def _on_page_selection_changed(self, btn_id: int):
        is_custom = (btn_id == 3)
        self.txt_custom_range.setEnabled(is_custom)
        if is_custom:
            self.txt_custom_range.setFocus()
        self._update_print_queue_summary()

    def _on_custom_range_edited(self, text: str):
        self._update_print_queue_summary()

    def _on_reverse_order_toggled(self, checked: bool):
        self._update_print_queue_summary()

    def _update_print_queue_summary(self):
        pages = self._get_target_pages_list()
        self.preview_widget.set_ordered_pages(pages)
        if not pages:
            self.lbl_page_summary.setText("Print Queue: 0 pages selected")
            return

        order_str = ""
        if len(pages) <= 8:
            order_str = f"[{', '.join(str(p) for p in pages)}]"
        else:
            order_str = f"[{pages[0]}, {pages[1]}, {pages[2]} ... {pages[-1]}]"

        rev_tag = " (Reversed)" if self.chk_reverse_order.isChecked() else ""
        self.lbl_page_summary.setText(
            f"Print Queue: {len(pages)} pages{rev_tag}\nOrder: {order_str}"
        )

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

        # Prepare processed PDF in temporary file
        temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        temp_pdf.close()

        color_mode = self._get_selected_color_mode()
        self.status_bar.showMessage("Processing print job...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        try:
            success = self.doc_model.export_processed_pdf(
                output_path=temp_pdf.name,
                selection_mode=self._get_selected_page_mode(),
                custom_range=self.txt_custom_range.text(),
                reverse=self.chk_reverse_order.isChecked(),
                color_mode=color_mode,
                render_dpi=300
            )

            if not success:
                QMessageBox.critical(self, "Error", "Failed to generate print job document.")
                return

            # Print via CUPS
            copies = self.spin_copies.value()
            page_size = self.combo_paper.currentText()
            duplex = self.combo_duplex.currentData()
            fit_page = self.chk_fit_page.isChecked()
            force_gray = (color_mode != ColorMode.COLOR)

            print_success, msg = self.cups_manager.print_file(
                file_path=temp_pdf.name,
                printer_name=printer_name,
                copies=copies,
                page_size=page_size,
                orientation="portrait",
                duplex=duplex,
                force_grayscale=force_gray,
                fit_to_page=fit_page,
                job_title=f"PrintStudio - {os.path.basename(self.doc_model.original_path)}"
            )

            if print_success:
                QMessageBox.information(
                    self,
                    "Print Sent Successfully",
                    f"Job submitted to '{printer_name}'!\n\n"
                    f"Pages: {len(pages)} {'(Reversed)' if self.chk_reverse_order.isChecked() else ''}\n"
                    f"Color Mode: {color_mode.value.capitalize()}\n"
                    f"Copies: {copies}\n\n{msg}"
                )
                self.status_bar.showMessage("Print job sent successfully.", 5000)
            else:
                QMessageBox.critical(self, "Printing Failed", f"Could not print:\n{msg}")
                self.status_bar.showMessage("Print job failed.", 5000)

        finally:
            self.progress_bar.setVisible(False)
            if os.path.exists(temp_pdf.name):
                try:
                    os.remove(temp_pdf.name)
                except Exception:
                    pass

    def action_export_pdf(self):
        if not self.doc_model or self.doc_model.total_pages == 0:
            QMessageBox.warning(self, "No Document", "Please open a PDF or image file first.")
            return

        pages = self._get_target_pages_list()
        if not pages:
            QMessageBox.warning(self, "No Pages", "No pages are selected to export.")
            return

        base_name = os.path.splitext(os.path.basename(self.doc_model.original_path))[0]
        color_tag = "bw" if self._get_selected_color_mode() != ColorMode.COLOR else "color"
        rev_tag = "_reversed" if self.chk_reverse_order.isChecked() else ""
        suggested_name = f"{base_name}_{color_tag}{rev_tag}.pdf"

        out_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Processed PDF",
            suggested_name,
            "PDF Files (*.pdf)"
        )
        if not out_path:
            return

        self.status_bar.showMessage("Exporting PDF...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)

        try:
            success = self.doc_model.export_processed_pdf(
                output_path=out_path,
                selection_mode=self._get_selected_page_mode(),
                custom_range=self.txt_custom_range.text(),
                reverse=self.chk_reverse_order.isChecked(),
                color_mode=self._get_selected_color_mode(),
                render_dpi=300
            )
            if success:
                QMessageBox.information(
                    self,
                    "Export Succeeded",
                    f"Successfully exported {len(pages)} pages to:\n{out_path}"
                )
                self.status_bar.showMessage(f"Exported to {os.path.basename(out_path)}", 4000)
            else:
                QMessageBox.critical(self, "Export Failed", "Could not generate exported PDF.")
        finally:
            self.progress_bar.setVisible(False)

    def action_system_dialog(self):
        """
        Opens the system print dialog using the processed PDF so that even if the system dialog is used,
        all page ordering, reverse, and grayscale options are strictly preserved.
        """
        if not self.doc_model or self.doc_model.total_pages == 0:
            QMessageBox.warning(self, "No Document", "Please open a PDF or image file first.")
            return

        temp_pdf = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        temp_pdf.close()

        try:
            success = self.doc_model.export_processed_pdf(
                output_path=temp_pdf.name,
                selection_mode=self._get_selected_page_mode(),
                custom_range=self.txt_custom_range.text(),
                reverse=self.chk_reverse_order.isChecked(),
                color_mode=self._get_selected_color_mode(),
                render_dpi=300
            )
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
                    job_title="PrintStudio Job"
                )
        finally:
            if os.path.exists(temp_pdf.name):
                try:
                    os.remove(temp_pdf.name)
                except Exception:
                    pass

    # Drag & Drop Support
    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        if urls:
            path = urls[0].toLocalFile()
            if path and os.path.exists(path):
                self.load_file(path)
