"""
Unit tests for PDF Processor page logic, N-up composition, Manual Duplex splitting,
and end-to-end PyMuPDF export/preview rendering.
"""

import os
import tempfile
import unittest

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from linux_print_studio.core.pdf_processor import (
    parse_page_range,
    get_target_pages,
    group_pages_into_sheets,
    split_manual_duplex_sheets,
    compute_nup_layout,
    is_supported_file,
    PageSelectionMode,
    ColorMode,
    NUpMode,
    DocumentModel,
)


class TestPageProcessorLogic(unittest.TestCase):

    def test_parse_page_range(self):
        self.assertEqual(parse_page_range("1-3, 5, 7-8", 10), [1, 2, 3, 5, 7, 8])
        self.assertEqual(parse_page_range("0, 1, 2, 15", 5), [1, 2])
        self.assertEqual(parse_page_range("5-3", 5), [5, 4, 3])
        self.assertEqual(parse_page_range("", 4), [1, 2, 3, 4])

    def test_get_target_pages_all(self):
        self.assertEqual(get_target_pages(5, PageSelectionMode.ALL, reverse=False), [1, 2, 3, 4, 5])
        self.assertEqual(get_target_pages(5, PageSelectionMode.ALL, reverse=True), [5, 4, 3, 2, 1])

    def test_get_target_pages_odd(self):
        self.assertEqual(get_target_pages(6, PageSelectionMode.ODD, reverse=False), [1, 3, 5])
        self.assertEqual(get_target_pages(6, PageSelectionMode.ODD, reverse=True), [5, 3, 1])

    def test_get_target_pages_even(self):
        self.assertEqual(get_target_pages(6, PageSelectionMode.EVEN, reverse=False), [2, 4, 6])
        self.assertEqual(get_target_pages(6, PageSelectionMode.EVEN, reverse=True), [6, 4, 2])

    def test_get_target_pages_custom(self):
        self.assertEqual(
            get_target_pages(10, PageSelectionMode.CUSTOM, custom_range="1, 4-6, 9", reverse=False),
            [1, 4, 5, 6, 9]
        )
        self.assertEqual(
            get_target_pages(10, PageSelectionMode.CUSTOM, custom_range="1, 4-6, 9", reverse=True),
            [9, 6, 5, 4, 1]
        )

    def test_is_supported_file(self):
        self.assertTrue(is_supported_file("/tmp/doc.pdf"))
        self.assertTrue(is_supported_file("/tmp/photo.JPG"))
        self.assertTrue(is_supported_file("/tmp/scan.webp"))
        self.assertFalse(is_supported_file("/tmp/notes.txt"))
        self.assertFalse(is_supported_file(""))

    def test_group_pages_into_sheets(self):
        self.assertEqual(group_pages_into_sheets([1, 2, 3, 4], 1), [[1], [2], [3], [4]])
        self.assertEqual(group_pages_into_sheets([1, 2, 3, 4, 5], 2), [[1, 2], [3, 4], [5]])
        self.assertEqual(group_pages_into_sheets([1, 2, 3, 4, 5], 4), [[1, 2, 3, 4], [5]])
        self.assertEqual(group_pages_into_sheets([], 2), [])

    def test_split_manual_duplex_sheets_even_total(self):
        sheets = [[1], [2], [3], [4], [5], [6]]
        p1, p2, trailing = split_manual_duplex_sheets(sheets, reverse_even=True)
        self.assertEqual(p1, [[1], [3], [5]])
        self.assertEqual(p2, [[6], [4], [2]])
        self.assertFalse(trailing)

    def test_split_manual_duplex_sheets_odd_total(self):
        sheets = [[1], [2], [3], [4], [5]]
        p1, p2, trailing = split_manual_duplex_sheets(sheets, reverse_even=True)
        self.assertEqual(p1, [[1], [3], [5]])
        self.assertEqual(p2, [[4], [2]])
        self.assertTrue(trailing)

    def test_split_manual_duplex_with_nup(self):
        # 8 pages in 2-in-1 -> 4 composed sheets
        sheets = group_pages_into_sheets([1, 2, 3, 4, 5, 6, 7, 8], 2)
        p1, p2, trailing = split_manual_duplex_sheets(sheets, reverse_even=True)
        self.assertEqual(p1, [[1, 2], [5, 6]])
        self.assertEqual(p2, [[7, 8], [3, 4]])
        self.assertFalse(trailing)

    def test_compute_nup_layout(self):
        # Portrait source -> 2-up landscape (2x1)
        w, h, cols, rows = compute_nup_layout(NUpMode.TWO_UP, 595, 842, "A4")
        self.assertGreater(w, h)
        self.assertEqual((cols, rows), (2, 1))

        # Landscape slides -> 2-up portrait (1x2)
        w, h, cols, rows = compute_nup_layout(NUpMode.TWO_UP, 960, 540, "A4")
        self.assertGreater(h, w)
        self.assertEqual((cols, rows), (1, 2))

        # Portrait source -> 4-up portrait (2x2)
        w, h, cols, rows = compute_nup_layout(NUpMode.FOUR_UP, 595, 842, "A4")
        self.assertGreater(h, w)
        self.assertEqual((cols, rows), (2, 2))

        # Landscape slides -> 4-up landscape (2x2)
        w, h, cols, rows = compute_nup_layout(NUpMode.FOUR_UP, 960, 540, "A4")
        self.assertGreater(w, h)
        self.assertEqual((cols, rows), (2, 2))


class TestDocumentModelNUpAndExport(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.sample_pdf = os.path.join(self.tmpdir.name, "sample_5p.pdf")
        doc = fitz.open()
        for i in range(1, 6):
            page = doc.new_page(width=595, height=842)
            page.insert_text((72, 100), f"Sample Page {i}", fontsize=28, color=(0.8, 0.1, 0.1))
        doc.save(self.sample_pdf)
        doc.close()
        self.model = DocumentModel(self.sample_pdf)

    def tearDown(self):
        self.model.close()
        self.tmpdir.cleanup()

    def test_export_2up_color_and_grayscale(self):
        out_color = os.path.join(self.tmpdir.name, "out_2up_color.pdf")
        ok = self.model.export_processed_pdf(
            output_path=out_color,
            color_mode=ColorMode.COLOR,
            n_up=NUpMode.TWO_UP,
            paper_size="A4",
            draw_borders=True
        )
        self.assertTrue(ok)
        res = fitz.open(out_color)
        self.assertEqual(len(res), 3)  # 5 pages -> 3 sheets
        # Portrait source in 2-up produces Landscape sheet
        self.assertGreater(res[0].rect.width, res[0].rect.height)
        res.close()

        out_gray = os.path.join(self.tmpdir.name, "out_2up_gray.pdf")
        ok_g = self.model.export_processed_pdf(
            output_path=out_gray,
            color_mode=ColorMode.GRAYSCALE,
            render_dpi=100,
            n_up=NUpMode.TWO_UP,
            paper_size="A4"
        )
        self.assertTrue(ok_g)
        res_g = fitz.open(out_gray)
        self.assertEqual(len(res_g), 3)
        res_g.close()

    def test_export_4up_monochrome_and_preview(self):
        out_4up = os.path.join(self.tmpdir.name, "out_4up_mono.pdf")
        ok = self.model.export_processed_pdf(
            output_path=out_4up,
            color_mode=ColorMode.MONOCHROME,
            render_dpi=100,
            n_up=NUpMode.FOUR_UP,
            paper_size="A4"
        )
        self.assertTrue(ok)
        res = fitz.open(out_4up)
        self.assertEqual(len(res), 2)  # 5 pages -> 2 sheets
        self.assertGreater(res[0].rect.height, res[0].rect.width)
        res.close()

        pix = self.model.render_sheet_preview_pixmap(
            sheet_pages=[1, 2, 3, 4],
            n_up=NUpMode.FOUR_UP,
            color_mode=ColorMode.GRAYSCALE,
            zoom=0.5
        )
        self.assertIsNotNone(pix)
        self.assertEqual(pix.colorspace.n, 1)  # Pure grayscale channel

    def test_export_explicit_manual_duplex_sheets(self):
        sheets = group_pages_into_sheets([1, 2, 3, 4, 5], 1)
        p1, p2, trailing = split_manual_duplex_sheets(sheets, reverse_even=True)
        self.assertTrue(trailing)

        out_p1 = os.path.join(self.tmpdir.name, "duplex_p1.pdf")
        out_p2 = os.path.join(self.tmpdir.name, "duplex_p2.pdf")
        self.assertTrue(self.model.export_processed_pdf(out_p1, color_mode=ColorMode.COLOR, explicit_sheets=p1))
        self.assertTrue(self.model.export_processed_pdf(out_p2, color_mode=ColorMode.COLOR, explicit_sheets=p2))

        d1 = fitz.open(out_p1)
        d2 = fitz.open(out_p2)
        self.assertEqual(len(d1), 3)
        self.assertEqual(len(d2), 2)
        self.assertIn("Sample Page 4", d2[0].get_text())
        self.assertIn("Sample Page 2", d2[1].get_text())
        d1.close()
        d2.close()


if __name__ == "__main__":
    unittest.main()
