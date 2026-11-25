"""
CUPS Printer Manager for Linux.
Discovers local and network CUPS printers, detects default printer and PPD capabilities,
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


@dataclass
class PrinterCapabilities:
    is_gutenprint: bool = False
    has_stp_ink_set_black: bool = False
    has_stp_ink_type_gray: bool = False
    gray_color_model: Optional[str] = "Gray"
    supports_duplex: bool = True


class CupsManager:
    """
    Manages interaction with CUPS on Linux, including driver-aware option selection
    (e.g., Gutenprint Canon/Epson ink-set alignment and hardware duplex detection).
    """

    def __init__(self):
        self.lpstat_bin = shutil.which("lpstat")
        self.lp_bin = shutil.which("lp")
        self.lpoptions_bin = shutil.which("lpoptions")
        self.cancel_bin = shutil.which("cancel")
        self._cap_cache: Dict[str, PrinterCapabilities] = {}

    @property
    def is_cups_available(self) -> bool:
        return bool(self.lpstat_bin and self.lp_bin)

    @staticmethod
    def _parse_lpoptions_output(output: str) -> Optional[PrinterCapabilities]:
        """
        Parses `lpoptions -p <printer> -l` output into PrinterCapabilities.
        Returns None if output does not look like valid PPD option lines.
        """
        options: Dict[str, List[str]] = {}
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if ":" not in line or "/" not in line.split(":", 1)[0]:
                continue
            key_part, values_part = line.split(":", 1)
            opt_name = key_part.split("/", 1)[0].strip()
            values = [v.lstrip("*").strip() for v in values_part.split() if v.strip()]
            if opt_name and values:
                options[opt_name] = values

        if not options:
            return None

        is_gutenprint = any(
            k in options for k in ("StpInkSet", "StpInkType", "StpQuality", "StpColorPrecision")
        )
        has_stp_ink_set_black = "Black" in options.get("StpInkSet", [])
        has_stp_ink_type_gray = "Gray" in options.get("StpInkType", [])

        # Detect exact Grayscale ColorModel value supported by this PPD
        gray_cm: Optional[str] = None
        cm_vals = options.get("ColorModel", [])
        for candidate in ("Gray", "Grayscale", "KGray", "Black"):
            if candidate in cm_vals:
                gray_cm = candidate
                break

        # Detect hardware duplex support in PPD
        duplex_keys = ("Duplex", "JCLDuplex", "EFDuplex", "KD03Duplex", "CNDuplex")
        supports_duplex = any(
            len(options.get(k, [])) > 1 for k in duplex_keys
        )

        return PrinterCapabilities(
            is_gutenprint=is_gutenprint,
            has_stp_ink_set_black=has_stp_ink_set_black,
            has_stp_ink_type_gray=has_stp_ink_type_gray,
            gray_color_model=gray_cm,
            supports_duplex=supports_duplex,
        )

    def get_printer_capabilities(
        self,
        printer_name: str,
        refresh: bool = False
    ) -> PrinterCapabilities:
        """
        Queries `lpoptions -p <printer_name> -l` to detect driver-specific options
        (Gutenprint StpInkSet/StpInkType, ColorModel values, hardware Duplex support).
        """
        if not printer_name or printer_name == "Print_to_PDF":
            return PrinterCapabilities(supports_duplex=False)

        if not refresh and printer_name in self._cap_cache:
            return self._cap_cache[printer_name]

        default_caps = PrinterCapabilities()
        if not self.lpoptions_bin:
            return default_caps

        try:
            proc = subprocess.run(
                [self.lpoptions_bin, "-p", printer_name, "-l"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if proc.returncode == 0 and proc.stdout:
                parsed = self._parse_lpoptions_output(proc.stdout)
                if parsed is not None:
                    self._cap_cache[printer_name] = parsed
                    return parsed
        except Exception as e:
            print(f"Error querying printer options for {printer_name}: {e}")

        return default_caps

    def get_printers(self) -> List[PrinterInfo]:
        """
        Discovers all configured CUPS printers using `lpstat -p -d`.
        Returns a list of PrinterInfo objects.
        """
        self._cap_cache.clear()
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
        orientation: str = "auto",      # 'auto', 'portrait', 'landscape'
        duplex: str = "simplex",        # 'simplex', 'long-edge', 'short-edge'
        force_grayscale: bool = False,
        fit_to_page: bool = True,
        job_title: str = "Linux Print Studio Job"
    ) -> Tuple[bool, str]:
        """
        Executes standard CUPS `lp` command with driver-safe options.
        Returns (success: bool, message: str).
        """
        if not self.lp_bin:
            return False, "CUPS 'lp' command line tool not found on system."

        caps = self.get_printer_capabilities(printer_name)
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

        # Duplex (only send two-sided flags when printer hardware supports duplex)
        if duplex == "long-edge" and caps.supports_duplex:
            cmd.extend(["-o", "sides=two-sided-long-edge"])
        elif duplex == "short-edge" and caps.supports_duplex:
            cmd.extend(["-o", "sides=two-sided-short-edge"])
        elif duplex == "simplex" or not caps.supports_duplex:
            cmd.extend(["-o", "sides=one-sided"])

        # Fit to page
        if fit_to_page:
            cmd.extend(["-o", "fit-to-page"])

        # Driver-aware Black & White / Grayscale enforcement
        if force_grayscale:
            if caps.is_gutenprint and caps.has_stp_ink_set_black:
                # CRITICAL for Gutenprint Canon/Epson printers (e.g. PIXMA iP2772):
                # Setting ColorModel=Gray WITHOUT StpInkSet=Black causes Gutenprint to emit
                # a mismatched ESC(t (4-channel CMYK) + ESC(L (1-channel K) header that Canon
                # firmware silently drops without feeding paper!
                # Setting StpInkSet=Black (+ StpInkType=Gray) generates a valid Black-only stream.
                cmd.extend(["-o", "StpInkSet=Black"])
                if caps.has_stp_ink_type_gray:
                    cmd.extend(["-o", "StpInkType=Gray"])
                if caps.gray_color_model:
                    cmd.extend(["-o", f"ColorModel={caps.gray_color_model}"])
            else:
                if caps.gray_color_model:
                    cmd.extend(["-o", f"ColorModel={caps.gray_color_model}"])
                cmd.extend(["-o", "print-color-mode=monochrome"])

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
