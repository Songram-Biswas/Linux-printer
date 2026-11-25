"""
PDF and Image Processor for Linux Print Studio.
Handles page filtering (All, Odd, Even, Custom Range), Reverse ordering,
N-up composition (1-in-1, 2-in-1, 4-in-1), Manual Duplex sheet splitting,
and true software-level Black & White / Grayscale conversion.
"""

import os
import tempfile
from enum import Enum
from typing import Dict, List, Optional, Tuple

try:
    import pymupdf as fitz  # Modern PyMuPDF import (avoids deprecation warning)
except ImportError:
    try:
        import fitz  # Legacy PyMuPDF fallback
    except ImportError:
        fitz = None

try:
    from PIL import Image
except ImportError:
    Image = None


SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}
SUPPORTED_EXTENSIONS = {".pdf"} | SUPPORTED_IMAGE_EXTENSIONS

# Standard paper sizes in PostScript points (1 inch = 72 pt) — Portrait (width, height)
PAPER_SIZES_PT: Dict[str, Tuple[float, float]] = {
    "A4": (595.28, 841.89),
    "Letter": (612.0, 792.0),
    "Legal": (612.0, 1008.0),
    "A3": (841.89, 1190.55),
    "A5": (419.53, 595.28),
    "Executive": (522.0, 756.0),
}


def is_supported_file(file_path: str) -> bool:
    """Returns True if the file path has a supported PDF or image extension."""
    if not file_path:
        return False
    ext = os.path.splitext(file_path)[1].lower()
    return ext in SUPPORTED_EXTENSIONS


class PageSelectionMode(Enum):
    ALL = "all"
    ODD = "odd"
    EVEN = "even"
    CUSTOM = "custom"


class ColorMode(Enum):
    COLOR = "color"
    GRAYSCALE = "grayscale"       # High quality 8-bit grayscale (anti-aliased text & photos)
    MONOCHROME = "monochrome"     # Pure 1-bit Black & White (thresholded, max toner saving)


class NUpMode(Enum):
    ONE_UP = 1
    TWO_UP = 2
    FOUR_UP = 4


def parse_page_range(range_str: str, max_pages: int) -> List[int]:
    """
    Parses a page range string (e.g., '1-3, 5, 8-10') into a list of 1-based page numbers.
    Bounds checks against max_pages. Duplicate pages are preserved in specified order.
    """
    pages: List[int] = []
    if not range_str.strip():
        return list(range(1, max_pages + 1))

    parts = [p.strip() for p in range_str.split(",") if p.strip()]
    for part in parts:
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) == 2:
                try:
                    start = int(bounds[0].strip()) if bounds[0].strip() else 1
                    end = int(bounds[1].strip()) if bounds[1].strip() else max_pages
                    if start <= end:
                        for p in range(start, end + 1):
                            if 1 <= p <= max_pages:
                                pages.append(p)
                    else:
                        # e.g., 5-1
                        for p in range(start, end - 1, -1):
                            if 1 <= p <= max_pages:
                                pages.append(p)
                except ValueError:
                    continue
        else:
            try:
                p = int(part)
                if 1 <= p <= max_pages:
                    pages.append(p)
            except ValueError:
                continue

    return pages if pages else list(range(1, max_pages + 1))


def get_target_pages(
    total_pages: int,
    selection_mode: PageSelectionMode = PageSelectionMode.ALL,
    custom_range: str = "",
    reverse: bool = False
) -> List[int]:
    """
    Calculates ordered list of 1-based page numbers based on mode and reverse flag.
    """
    if total_pages <= 0:
        return []

    if selection_mode == PageSelectionMode.ALL:
        pages = list(range(1, total_pages + 1))
    elif selection_mode == PageSelectionMode.ODD:
        pages = [p for p in range(1, total_pages + 1) if p % 2 != 0]
    elif selection_mode == PageSelectionMode.EVEN:
        pages = [p for p in range(1, total_pages + 1) if p % 2 == 0]
    elif selection_mode == PageSelectionMode.CUSTOM:
        pages = parse_page_range(custom_range, total_pages)
    else:
        pages = list(range(1, total_pages + 1))

    if reverse:
        pages = list(reversed(pages))

    return pages


def group_pages_into_sheets(pages: List[int], n_up: int = 1) -> List[List[int]]:
    """
    Groups a flat list of 1-based page numbers into physical sheets for N-up printing.
    Example: [1, 2, 3, 4, 5] with n_up=2 -> [[1, 2], [3, 4], [5]].
    """
    if not pages:
        return []
    step = max(1, int(n_up))
    return [pages[i:i + step] for i in range(0, len(pages), step)]


def split_manual_duplex_sheets(
    sheets: List[List[int]],
    reverse_even: bool = True
) -> Tuple[List[List[int]], List[List[int]], bool]:
    """
    Splits an ordered list of logical sheets into Pass 1 (odd-indexed sheets: 1, 3, 5...)
    and Pass 2 (even-indexed sheets: 2, 4, 6..., reversed by default for standard trays).

    Returns:
        (pass1_odd_sheets, pass2_even_sheets, has_trailing_odd_sheet)
        where has_trailing_odd_sheet is True when total sheets > 1 and odd, meaning the
        last sheet printed in Pass 1 has no back side and should be set aside before flipping.
    """
    if not sheets:
        return [], [], False

    pass1 = sheets[0::2]
    pass2 = sheets[1::2]
    if reverse_even:
        pass2 = list(reversed(pass2))

    has_trailing_odd = (len(sheets) > 1 and len(sheets) % 2 == 1)
    return pass1, pass2, has_trailing_odd


def compute_nup_layout(
    n_up: NUpMode,
    src_width: float,
    src_height: float,
    paper_size: str = "A4"
) -> Tuple[float, float, int, int]:
    """
    Computes optimal target sheet dimensions (width, height) in points and grid (cols, rows)
    for N-up composition based on whether the source pages are portrait or landscape.
    """
    base_w, base_h = PAPER_SIZES_PT.get(paper_size, PAPER_SIZES_PT["A4"])
    src_is_landscape = src_width > src_height

    if n_up == NUpMode.TWO_UP:
        if src_is_landscape:
            # Landscape slides -> Portrait sheet, 1 col x 2 rows (stacked top & bottom)
            return base_w, base_h, 1, 2
        else:
            # Portrait pages -> Landscape sheet, 2 cols x 1 row (side by side)
            return base_h, base_w, 2, 1
    elif n_up == NUpMode.FOUR_UP:
        if src_is_landscape:
            # Landscape slides -> Landscape sheet, 2 cols x 2 rows
            return base_h, base_w, 2, 2
        else:
            # Portrait pages -> Portrait sheet, 2 cols x 2 rows
            return base_w, base_h, 2, 2

    # 1-in-1 fallback
    return src_width, src_height, 1, 1


def convert_image_to_pdf(image_path: str, temp_pdf_path: str) -> bool:
    """
    Converts any supported image (PNG, JPG, TIFF, BMP, WebP) into a temporary single-page PDF.
    """
    try:
        img = Image.open(image_path)
        # Handle RGBA images by converting to RGB with white background
        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode in ("RGBA", "LA") else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        img.save(temp_pdf_path, "PDF", resolution=300.0)
        return True
    except Exception as e:
        print(f"Error converting image to PDF: {e}")
        return False


class DocumentModel:
    """
    Represents an opened document (PDF or converted image), providing
    fast page rendering, N-up sheet composition, live color conversion preview,
    and print/export preparation.
    """

    def __init__(self, file_path: str):
        self.original_path = file_path
        self.is_image = False
        self._temp_files: List[str] = []
        self.doc: Optional[fitz.Document] = None

        self._load_file(file_path)

    def _load_file(self, file_path: str):
        ext = os.path.splitext(file_path)[1].lower()

        if ext in SUPPORTED_IMAGE_EXTENSIONS:
            self.is_image = True
            # Open directly via PyMuPDF or convert via Pillow fallback
            try:
                img_doc = fitz.open(file_path)
                pdf_bytes = img_doc.convert_to_pdf()
                img_doc.close()
                self.doc = fitz.open("pdf", pdf_bytes)
            except Exception:
                tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
                tmp.close()
                self._temp_files.append(tmp.name)
                convert_image_to_pdf(file_path, tmp.name)
                self.doc = fitz.open(tmp.name)
        else:
            self.doc = fitz.open(file_path)

    @property
    def total_pages(self) -> int:
        if self.doc:
            return len(self.doc)
        return 0

    def get_page_size_pt(self, page_num_1_based: int) -> Tuple[float, float]:
        """Returns width and height of page in points."""
        if not self.doc or page_num_1_based < 1 or page_num_1_based > len(self.doc):
            return 595.28, 841.89  # Default A4
        page = self.doc[page_num_1_based - 1]
        rect = page.rect
        return rect.width, rect.height

    def get_sheet_size_pt(
        self,
        sheet_pages: List[int],
        n_up: NUpMode = NUpMode.ONE_UP,
        paper_size: str = "A4"
    ) -> Tuple[float, float]:
        """Returns width and height in points for a composed sheet."""
        if not sheet_pages:
            return PAPER_SIZES_PT.get(paper_size, PAPER_SIZES_PT["A4"])
        src_w, src_h = self.get_page_size_pt(sheet_pages[0])
        if n_up == NUpMode.ONE_UP:
            return src_w, src_h
        sheet_w, sheet_h, _, _ = compute_nup_layout(n_up, src_w, src_h, paper_size)
        return sheet_w, sheet_h

    def _compose_sheets_to_pdf(
        self,
        sheets: List[List[int]],
        n_up: NUpMode = NUpMode.ONE_UP,
        paper_size: str = "A4",
        draw_borders: bool = True
    ) -> "fitz.Document":
        """
        Builds a vector in-memory PyMuPDF Document where each output page represents
        one physical sheet (either 1-in-1 copy or 2-in-1 / 4-in-1 composed grid).
        """
        composed = fitz.open()
        if not self.doc:
            return composed

        if n_up == NUpMode.ONE_UP:
            for sheet in sheets:
                for page_num in sheet:
                    if 1 <= page_num <= self.total_pages:
                        composed.insert_pdf(self.doc, from_page=page_num - 1, to_page=page_num - 1)
            return composed

        margin = 18.0
        gutter = 12.0

        for sheet in sheets:
            valid_pages = [p for p in sheet if 1 <= p <= self.total_pages]
            if not valid_pages:
                continue

            first_w, first_h = self.get_page_size_pt(valid_pages[0])
            sheet_w, sheet_h, cols, rows = compute_nup_layout(n_up, first_w, first_h, paper_size)
            new_page = composed.new_page(width=sheet_w, height=sheet_h)

            cell_w = (sheet_w - 2 * margin - (cols - 1) * gutter) / cols
            cell_h = (sheet_h - 2 * margin - (rows - 1) * gutter) / rows

            for idx, page_num in enumerate(valid_pages):
                col = idx % cols
                row = idx // cols
                x0 = margin + col * (cell_w + gutter)
                y0 = margin + row * (cell_h + gutter)
                cell_rect = fitz.Rect(x0, y0, x0 + cell_w, y0 + cell_h)

                # Place source page preserving aspect ratio and vector crispness
                new_page.show_pdf_page(cell_rect, self.doc, page_num - 1, keep_proportion=True)

                if draw_borders:
                    # Compute exact fitted rectangle so border hugs the placed page nicely
                    pw, ph = self.get_page_size_pt(page_num)
                    if pw > 0 and ph > 0:
                        scale = min(cell_w / pw, cell_h / ph)
                        draw_w = pw * scale
                        draw_h = ph * scale
                        bx0 = x0 + (cell_w - draw_w) / 2.0
                        by0 = y0 + (cell_h - draw_h) / 2.0
                        border_rect = fitz.Rect(bx0, by0, bx0 + draw_w, by0 + draw_h)
                    else:
                        border_rect = cell_rect

                    new_page.draw_rect(
                        border_rect,
                        color=(0.68, 0.68, 0.68),
                        width=0.6
                    )

        return composed

    @staticmethod
    def _render_page_with_color_mode(
        page: "fitz.Page",
        color_mode: ColorMode,
        zoom: float
    ) -> "fitz.Pixmap":
        """Renders a single PyMuPDF page with exact color mode enforcement."""
        mat = fitz.Matrix(zoom, zoom)

        if color_mode == ColorMode.COLOR:
            return page.get_pixmap(matrix=mat, alpha=False)
        elif color_mode == ColorMode.GRAYSCALE:
            return page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY, alpha=False)
        else:
            # ColorMode.MONOCHROME: 8-bit Gray then binarize (Pure B&W threshold)
            gray_pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY, alpha=False)
            img = Image.frombytes("L", [gray_pix.width, gray_pix.height], gray_pix.samples)
            table = [0 if i < 140 else 255 for i in range(256)]
            bw_img = img.point(table, "1").convert("L")
            return fitz.Pixmap(fitz.csGRAY, bw_img.width, bw_img.height, bw_img.tobytes(), False)

    def render_preview_pixmap(
        self,
        page_num_1_based: int,
        color_mode: ColorMode = ColorMode.COLOR,
        zoom: float = 1.0,
        dpi: int = 150
    ) -> Optional["fitz.Pixmap"]:
        """
        Renders a single source page into a PyMuPDF Pixmap according to color_mode and zoom.
        """
        if not self.doc or page_num_1_based < 1 or page_num_1_based > len(self.doc):
            return None

        page = self.doc[page_num_1_based - 1]
        return self._render_page_with_color_mode(page, color_mode, zoom)

    def render_sheet_preview_pixmap(
        self,
        sheet_pages: List[int],
        n_up: NUpMode = NUpMode.ONE_UP,
        color_mode: ColorMode = ColorMode.COLOR,
        zoom: float = 1.0,
        paper_size: str = "A4",
        draw_borders: bool = True
    ) -> Optional["fitz.Pixmap"]:
        """
        Renders a composed sheet (1-in-1, 2-in-1, or 4-in-1) into a PyMuPDF Pixmap
        with live color mode conversion.
        """
        if not self.doc or not sheet_pages:
            return None

        if n_up == NUpMode.ONE_UP:
            return self.render_preview_pixmap(sheet_pages[0], color_mode=color_mode, zoom=zoom)

        temp_doc = self._compose_sheets_to_pdf(
            [sheet_pages],
            n_up=n_up,
            paper_size=paper_size,
            draw_borders=draw_borders
        )
        try:
            if len(temp_doc) == 0:
                return None
            return self._render_page_with_color_mode(temp_doc[0], color_mode, zoom)
        finally:
            temp_doc.close()

    def export_processed_pdf(
        self,
        output_path: str,
        selection_mode: PageSelectionMode = PageSelectionMode.ALL,
        custom_range: str = "",
        reverse: bool = False,
        color_mode: ColorMode = ColorMode.COLOR,
        render_dpi: int = 300,
        n_up: NUpMode = NUpMode.ONE_UP,
        paper_size: str = "A4",
        draw_borders: bool = True,
        explicit_sheets: Optional[List[List[int]]] = None
    ) -> bool:
        """
        Builds the final PDF to print or save.
        Applies:
        1. Exact page selection & ordering (including reverse) or explicit sheet grouping.
        2. N-up layout composition (1-in-1, 2-in-1, 4-in-1) with smart orientation & borders.
        3. Software-enforced Grayscale or Monochrome conversion if selected.
           When Grayscale or Monochrome is requested, pages are converted into
           pure single-channel Gray/Monochrome data with no RGB/CMYK channels,
           guaranteeing that printers cannot print color even if the driver is set to color!
        """
        if not self.doc or self.total_pages == 0:
            return False

        if explicit_sheets is not None:
            sheets = [s for s in explicit_sheets if s]
        else:
            target_pages = get_target_pages(self.total_pages, selection_mode, custom_range, reverse)
            if not target_pages:
                return False
            sheets = group_pages_into_sheets(target_pages, n_up.value)

        if not sheets:
            return False

        # Compose vector sheets first (handles both 1-in-1 and N-up cleanly)
        composed_doc = self._compose_sheets_to_pdf(
            sheets=sheets,
            n_up=n_up,
            paper_size=paper_size,
            draw_borders=draw_borders
        )

        try:
            if len(composed_doc) == 0:
                return False

            if color_mode == ColorMode.COLOR:
                composed_doc.save(output_path, deflate=True, garbage=3)
                return True

            # True Black & White / Grayscale rasterization (single-channel Gray)
            out_pdf = fitz.open()
            scale = render_dpi / 72.0

            try:
                for sheet_page in composed_doc:
                    rect = sheet_page.rect
                    final_pix = self._render_page_with_color_mode(sheet_page, color_mode, scale)
                    new_page = out_pdf.new_page(width=rect.width, height=rect.height)
                    new_page.insert_image(rect, pixmap=final_pix)

                out_pdf.save(output_path, deflate=True, garbage=3)
                return True
            finally:
                out_pdf.close()
        finally:
            composed_doc.close()

    def close(self):
        if self.doc:
            self.doc.close()
            self.doc = None
        for tmp in self._temp_files:
            if os.path.exists(tmp):
                try:
                    os.remove(tmp)
                except Exception:
                    pass
        self._temp_files.clear()

    def __del__(self):
        self.close()
