"""
Interactive 1-Click Manual Duplex Dialog for Linux Print Studio.
Guides the user between Pass 1 (Odd sheets) and Pass 2 (Reversed Even sheets).
"""

from typing import List
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QFrame
)


def _format_sheet_sequence(sheets: List[List[int]], n_up: int) -> str:
    """Formats a list of sheets concisely for display."""
    if not sheets:
        return "None"

    if n_up == 1:
        items = [str(s[0]) for s in sheets if s]
    else:
        items = [
            f"({','.join(str(p) for p in s)})"
            for s in sheets if s
        ]

    if len(items) <= 8:
        return ", ".join(items)
    return f"{', '.join(items[:4])}, ..., {', '.join(items[-2:])}"


class ManualDuplexDialog(QDialog):
    """
    Modal prompt displayed after Pass 1 (Odd sheets) has been submitted to CUPS.
    Lets the user flip/reinsert the paper stack and trigger Pass 2 (Even sheets).
    """

    def __init__(
        self,
        pass1_sheets: List[List[int]],
        even_sheets_normal: List[List[int]],
        has_trailing_odd: bool,
        n_up: int = 1,
        printer_name: str = "",
        parent=None
    ):
        super().__init__(parent)
        self.pass1_sheets = pass1_sheets
        self.even_sheets_normal = even_sheets_normal
        self.has_trailing_odd = has_trailing_odd
        self.n_up = n_up
        self.printer_name = printer_name

        self.setWindowTitle("Manual Duplex — Step 2 of 2")
        self.setMinimumWidth(460)
        self.setMaximumWidth(560)
        self.setModal(True)

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(12)

        # Header
        lbl_title = QLabel("🔄 Flip & Reinsert Paper for Back Side", self)
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        layout.addWidget(lbl_title)

        if self.printer_name:
            lbl_printer = QLabel(f"Printer: {self.printer_name}", self)
            lbl_printer.setStyleSheet("color: #90caf9; font-size: 12px;")
            layout.addWidget(lbl_printer)

        # Step 1 / Step 2 Status Card
        status_card = QFrame(self)
        status_card.setObjectName("stepCard")
        status_layout = QVBoxLayout(status_card)
        status_layout.setContentsMargins(12, 10, 12, 10)
        status_layout.setSpacing(6)

        unit = "pages" if self.n_up == 1 else f"sheets ({self.n_up}-in-1)"
        pass1_seq = _format_sheet_sequence(self.pass1_sheets, self.n_up)
        lbl_p1 = QLabel(
            f"✅ <b>Step 1 Sent (Odd):</b> {len(self.pass1_sheets)} {unit} — [{pass1_seq}]",
            self
        )
        lbl_p1.setWordWrap(True)
        lbl_p1.setStyleSheet("color: #81c784;")

        self.lbl_p2 = QLabel("", self)
        self.lbl_p2.setWordWrap(True)
        self.lbl_p2.setStyleSheet("color: #ce93d8;")

        status_layout.addWidget(lbl_p1)
        status_layout.addWidget(self.lbl_p2)
        layout.addWidget(status_card)

        # Instructions Card
        inst_card = QFrame(self)
        inst_card.setObjectName("stepCard")
        inst_layout = QVBoxLayout(inst_card)
        inst_layout.setContentsMargins(12, 10, 12, 10)
        inst_layout.setSpacing(6)

        lbl_inst_head = QLabel("📋 Instructions:", self)
        lbl_inst_head.setStyleSheet("font-weight: bold; color: #7cc0ff;")

        lbl_inst = QLabel(
            "1. Wait until all <b>Odd</b> pages finish printing.<br>"
            "2. Take the printed stack, flip it over, and place it back into the paper tray.<br>"
            "3. Click <b>Continue — Print Even Pages</b> below.",
            self
        )
        lbl_inst.setWordWrap(True)
        lbl_inst.setTextFormat(Qt.TextFormat.RichText)

        inst_layout.addWidget(lbl_inst_head)
        inst_layout.addWidget(lbl_inst)
        layout.addWidget(inst_card)

        # Conditional Odd-Sheet Warning
        if self.has_trailing_odd and self.pass1_sheets:
            last_sheet = self.pass1_sheets[-1]
            last_desc = (
                f"Page {last_sheet[0]}"
                if self.n_up == 1
                else f"Pages {', '.join(str(p) for p in last_sheet)}"
            )
            warn_card = QFrame(self)
            warn_card.setObjectName("warningCard")
            warn_layout = QVBoxLayout(warn_card)
            warn_layout.setContentsMargins(12, 10, 12, 10)

            lbl_warn = QLabel(
                f"⚠️ <b>Odd total sheet count!</b><br>"
                f"Remove the last printed sheet (<b>{last_desc}</b>) and set it aside "
                f"before reinserting the remaining <b>{len(self.even_sheets_normal)}</b> "
                f"sheet(s) into the tray so the back sides match properly.",
                self
            )
            lbl_warn.setWordWrap(True)
            lbl_warn.setTextFormat(Qt.TextFormat.RichText)
            lbl_warn.setStyleSheet("color: #ffd599;")
            warn_layout.addWidget(lbl_warn)
            layout.addWidget(warn_card)

        # Reverse Even Toggle (Checked by default!)
        self.chk_reverse_even = QCheckBox(
            "🔄 Print Even pages in Reverse Order (Recommended)",
            self
        )
        self.chk_reverse_even.setChecked(True)
        self.chk_reverse_even.setToolTip(
            "Prints Even pages back-to-front so the last printed Odd page gets its matching Even back first."
        )
        self.chk_reverse_even.toggled.connect(self._update_pass2_label)
        layout.addWidget(self.chk_reverse_even)

        self._update_pass2_label()

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_continue = QPushButton("🖨️ Continue — Print Even Pages", self)
        self.btn_continue.setObjectName("primaryButton")
        self.btn_continue.setDefault(True)
        self.btn_continue.clicked.connect(self.accept)

        btn_row.addWidget(self.btn_cancel)
        btn_row.addWidget(self.btn_continue)
        layout.addLayout(btn_row)

    def _update_pass2_label(self):
        sheets = self.get_pass2_sheets()
        unit = "pages" if self.n_up == 1 else f"sheets ({self.n_up}-in-1)"
        seq = _format_sheet_sequence(sheets, self.n_up)
        order_tag = "Reversed" if self.chk_reverse_even.isChecked() else "Normal order"
        self.lbl_p2.setText(
            f"⏳ <b>Step 2 Next (Even — {order_tag}):</b> {len(sheets)} {unit} — [{seq}]"
        )

    def get_pass2_sheets(self) -> List[List[int]]:
        """Returns the exact sheet sequence for Pass 2 based on the reverse toggle."""
        if self.chk_reverse_even.isChecked():
            return list(reversed(self.even_sheets_normal))
        return list(self.even_sheets_normal)
