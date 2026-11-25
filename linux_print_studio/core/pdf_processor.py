"""
PDF and Image Processor for Linux Print Studio.
Handles page filtering (All, Odd, Even, Custom Range), Reverse ordering,
and true software-level Black & White / Grayscale conversion.
"""

import os
from enum import Enum
from typing import List, Optional, Tuple

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from PIL import Image, ImageOps
except ImportError:
    Image = None
    ImageOps = None


class PageSelectionMode(Enum):
    ALL = "all"
    ODD = "odd"
    EVEN = "even"
    CUSTOM = "custom"


class ColorMode(Enum):
    COLOR = "color"
    GRAYSCALE = "grayscale"       # High quality 8-bit grayscale (anti-aliased text & photos)
    MONOCHROME = "monochrome"     # Pure 1-bit Black & White (thresholded, max toner saving)


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
    fast page rendering, live color conversion preview, and print preparation.
    """

    def __init__(self, file_path: str):
        self.original_path = file_path
        self.is_image = False
        self._temp_files: List[str] = []
        self.doc: Optional[fitz.Document] = None

        self._load_file(file_path)

    def _load_file(self, file_path: str):
        ext = os.path.splitext(file_path)[1].lower()
        image_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tif", ".tiff"}

        if ext in image_extensions:
            self.is_image = True
            # Open directly via PyMuPDF or convert
            try:
                # PyMuPDF supports opening images directly as documents
                img_doc = fitz.open(file_path)
                pdf_bytes = img_doc.convert_to_pdf()
                self.doc = fitz.open("pdf", pdf_bytes)
            except Exception:
                # Fallback via Pillow
                import tempfile
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

    def render_preview_pixmap(
        self,
        page_num_1_based: int,
        color_mode: ColorMode = ColorMode.COLOR,
        zoom: float = 1.0,
        dpi: int = 150
    ) -> Optional[fitz.Pixmap]:
        """
        Renders a page into a PyMuPDF Pixmap according to color_mode and zoom.
        """
        if not self.doc or page_num_1_based < 1 or page_num_1_based > len(self.doc):
            return None

        page = self.doc[page_num_1_based - 1]
        mat = fitz.Matrix(zoom, zoom)

        if color_mode == ColorMode.COLOR:
            pix = page.get_pixmap(matrix=mat, alpha=False)
        elif color_mode == ColorMode.GRAYSCALE:
            # Render directly in 8-bit Gray colorspace
            pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY, alpha=False)
        elif color_mode == ColorMode.MONOCHROME:
            # 8-bit Gray then binarize (Pure B&W threshold)
            gray_pix = page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY, alpha=False)
            # Thresholding using PIL for speed and quality
            img = Image.frombytes("L", [gray_pix.width, gray_pix.height], gray_pix.samples)
            # Threshold: standard 140 for crisp black on white
            table = [0 if i < 140 else 255 for i in range(256)]
            bw_img = img.point(table, "1").convert("L")
            # Convert back to PyMuPDF Pixmap
            pix = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, bw_img.width, bw_img.height), False)
            pix.set_samples(bw_img.tobytes())

        return pix

    def export_processed_pdf(
        self,
        output_path: str,
        selection_mode: PageSelectionMode = PageSelectionMode.ALL,
        custom_range: str = "",
        reverse: bool = False,
        color_mode: ColorMode = ColorMode.COLOR,
        render_dpi: int = 300
    ) -> bool:
        """
        Builds the final PDF to print or save.
        Applies:
        1. Exact page selection & ordering (including reverse).
        2. Software-enforced Grayscale or Monochrome conversion if selected.
           When Grayscale or Monochrome is requested, pages are converted into
           pure single-channel Gray/Monochrome data with no RGB/CMYK channels,
           guaranteeing that printers cannot print color even if the driver is set to color!
        """
        if not self.doc or self.total_pages == 0:
            return False

        target_pages = get_target_pages(self.total_pages, selection_mode, custom_range, reverse)
        if not target_pages:
            return False

        out_pdf = fitz.open()

        if color_mode == ColorMode.COLOR:
            # Pure vector/stream copy of selected pages in requested order
            for page_num in target_pages:
                out_pdf.insert_pdf(self.doc, from_page=page_num - 1, to_page=page_num - 1)
        else:
            # True Black & White / Grayscale conversion
            scale = render_dpi / 72.0
            mat = fitz.Matrix(scale, scale)

            for page_num in target_pages:
                orig_page = self.doc[page_num - 1]
                orig_rect = orig_page.rect  # width and height in points

                # Render page in pure grayscale
                gray_pix = orig_page.get_pixmap(matrix=mat, colorspace=fitz.csGRAY, alpha=False)

                if color_mode == ColorMode.MONOCHROME:
                    # Threshold for pure 1-bit black/white
                    img = Image.frombytes("L", [gray_pix.width, gray_pix.height], gray_pix.samples)
                    table = [0 if i < 140 else 255 for i in range(256)]
                    bw_img = img.point(table, "1").convert("L")
                    raw_bytes = bw_img.tobytes()
                else:
                    raw_bytes = gray_pix.samples

                # Create a grayscale pixmap
                final_pix = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, gray_pix.width, gray_pix.height), False)
                final_pix.set_samples(raw_bytes)

                # Insert page with original physical dimensions
                new_page = out_pdf.new_page(width=orig_rect.width, height=orig_rect.height)
                # Insert grayscale image spanning entire page rect
                new_page.insert_image(orig_rect, pixmap=final_pix)

        out_pdf.save(output_path, deflate=True, garbage=3)
        out_pdf.close()
        return True

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
