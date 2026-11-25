"""
CUPS Printer Manager for Linux.
Discovers local and network CUPS printers, detects default printer,
and submits print jobs via standard CUPS utilities (`lpstat`, `lpoptions`, `lp`).
"""

import shutil
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class PrinterInfo:
    name: str
    description: str
    is_default: bool
    status: str  # 'idle', 'printing', 'stopped', 'unknown'


class CupsManager:
    """
    Manages interaction with CUPS on Linux.
    """

    def __init__(self):
        self.lpstat_bin = shutil.which("lpstat")
        self.lp_bin = shutil.which("lp")
        self.lpoptions_bin = shutil.which("lpoptions")
        self.cancel_bin = shutil.which("cancel")

    @property
    def is_cups_available(self) -> bool:
        return bool(self.lpstat_bin and self.lp_bin)

    def get_printers(self) -> List[PrinterInfo]:
        """
        Discovers all configured CUPS printers using `lpstat -p -d`.
        Returns a list of PrinterInfo objects.
        """
        printers: List[PrinterInfo] = []
        default_printer: Optional[str] = None

        if not self.is_cups_available:
            # Fallback for environments without CUPS
            printers.append(
                PrinterInfo(
                    name="Print_to_PDF",
                    description="Export as PDF Document",
                    is_default=True,
                    status="idle"
                )
            )
            return printers

        try:
            # 1. Get default printer: lpstat -d
            proc_d = subprocess.run(
                [self.lpstat_bin, "-d"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if proc_d.returncode == 0:
                for line in proc_d.stdout.splitlines():
                    if "system default destination:" in line.lower():
                        default_printer = line.split(":", 1)[1].strip()

            # 2. Get printer list & status: lpstat -p
            proc_p = subprocess.run(
                [self.lpstat_bin, "-p"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if proc_p.returncode == 0:
                for line in proc_p.stdout.splitlines():
                    line_clean = line.strip()
                    if line_clean.startswith("printer "):
                        parts = line_clean.split()
                        if len(parts) >= 2:
                            p_name = parts[1]
                            status = "idle"
                            if "is idle" in line_clean:
                                status = "idle"
                            elif "printing" in line_clean:
                                status = "printing"
                            elif "disabled" in line_clean or "stopped" in line_clean:
                                status = "stopped"

                            is_def = (p_name == default_printer)
                            desc = f"{p_name} ({status})"
                            if is_def:
                                desc += " [Default]"

                            printers.append(
                                PrinterInfo(
                                    name=p_name,
                                    description=desc,
                                    is_default=is_def,
                                    status=status
                                )
                            )

            # If no printers found, add PDF export option
            if not printers:
                printers.append(
                    PrinterInfo(
                        name="Print_to_PDF",
                        description="Export as PDF Document",
                        is_default=True,
                        status="idle"
                    )
                )

        except Exception as e:
            print(f"Error querying CUPS printers: {e}")
            printers.append(
                PrinterInfo(
                    name="Print_to_PDF",
                    description="Export as PDF Document",
                    is_default=True,
                    status="idle"
                )
            )

        return printers

    def print_file(
        self,
        file_path: str,
        printer_name: str,
        copies: int = 1,
        page_size: str = "A4",
        orientation: str = "portrait",  # 'portrait', 'landscape'
        duplex: str = "simplex",        # 'simplex', 'long-edge', 'short-edge'
        force_grayscale: bool = False,
        fit_to_page: bool = True,
        job_title: str = "Linux Print Studio Job"
    ) -> Tuple[bool, str]:
        """
        Executes standard CUPS `lp` command with all options.
        Returns (success: bool, message: str).
        """
        if not self.lp_bin:
            return False, "CUPS 'lp' command line tool not found on system."

        cmd = [self.lp_bin, "-d", printer_name]

        # Copies
        if copies > 1:
            cmd.extend(["-n", str(copies)])

        # Job title
        if job_title:
            cmd.extend(["-t", job_title])

        # Page size
        if page_size:
            cmd.extend(["-o", f"PageSize={page_size}"])

        # Orientation
        if orientation == "landscape":
            cmd.extend(["-o", "orientation-requested=4"])
        elif orientation == "portrait":
            cmd.extend(["-o", "orientation-requested=3"])

        # Duplex
        if duplex == "long-edge":
            cmd.extend(["-o", "sides=two-sided-long-edge"])
        elif duplex == "short-edge":
            cmd.extend(["-o", "sides=two-sided-short-edge"])
        elif duplex == "simplex":
            cmd.extend(["-o", "sides=one-sided"])

        # Fit to page
        if fit_to_page:
            cmd.extend(["-o", "fit-to-page"])

        # Color mode enforcement in CUPS
        if force_grayscale:
            cmd.extend([
                "-o", "ColorModel=Gray",
                "-o", "print-color-mode=monochrome"
            ])

        cmd.append(file_path)

        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            if res.returncode == 0:
                job_id = res.stdout.strip()
                return True, f"Print job submitted successfully!\n{job_id}"
            else:
                err = res.stderr.strip() or res.stdout.strip()
                return False, f"CUPS error (Exit {res.returncode}): {err}"
        except Exception as e:
            return False, f"Failed to execute print command: {str(e)}"
