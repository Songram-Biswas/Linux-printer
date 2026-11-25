"""
Unit tests for PDF Processor page logic and ranges.
"""

import unittest
from linux_print_studio.core.pdf_processor import (
    parse_page_range,
    get_target_pages,
    PageSelectionMode
)


class TestPageProcessorLogic(unittest.TestCase):

    def test_parse_page_range(self):
        # Normal ranges
        self.assertEqual(parse_page_range("1-3, 5, 7-8", 10), [1, 2, 3, 5, 7, 8])
        # Out of bounds ignored or clamped
        self.assertEqual(parse_page_range("0, 1, 2, 15", 5), [1, 2])
        # Reversed sub-range (e.g. 5-3)
        self.assertEqual(parse_page_range("5-3", 5), [5, 4, 3])
        # Empty string defaults to all pages
        self.assertEqual(parse_page_range("", 4), [1, 2, 3, 4])

    def test_get_target_pages_all(self):
        pages = get_target_pages(5, PageSelectionMode.ALL, reverse=False)
        self.assertEqual(pages, [1, 2, 3, 4, 5])

        # Reversed
        rev_pages = get_target_pages(5, PageSelectionMode.ALL, reverse=True)
        self.assertEqual(rev_pages, [5, 4, 3, 2, 1])

    def test_get_target_pages_odd(self):
        pages = get_target_pages(6, PageSelectionMode.ODD, reverse=False)
        self.assertEqual(pages, [1, 3, 5])

        # Odd + Reverse (crucial feature!)
        rev_odd = get_target_pages(6, PageSelectionMode.ODD, reverse=True)
        self.assertEqual(rev_odd, [5, 3, 1])

    def test_get_target_pages_even(self):
        pages = get_target_pages(6, PageSelectionMode.EVEN, reverse=False)
        self.assertEqual(pages, [2, 4, 6])

        # Even + Reverse
        rev_even = get_target_pages(6, PageSelectionMode.EVEN, reverse=True)
        self.assertEqual(rev_even, [6, 4, 2])

    def test_get_target_pages_custom(self):
        pages = get_target_pages(10, PageSelectionMode.CUSTOM, custom_range="1, 4-6, 9", reverse=False)
        self.assertEqual(pages, [1, 4, 5, 6, 9])

        # Custom + Reverse
        rev_custom = get_target_pages(10, PageSelectionMode.CUSTOM, custom_range="1, 4-6, 9", reverse=True)
        self.assertEqual(rev_custom, [9, 6, 5, 4, 1])


if __name__ == "__main__":
    unittest.main()
