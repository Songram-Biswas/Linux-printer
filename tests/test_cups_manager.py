"""
Unit tests for CupsManager printer detection and option building.
"""

import unittest
from unittest.mock import patch, MagicMock
from linux_print_studio.core.cups_manager import CupsManager


class TestCupsManager(unittest.TestCase):

    def setUp(self):
        self.mgr = CupsManager()

    @patch("subprocess.run")
    def test_get_printers_parsing(self, mock_run):
        # Mock lpstat -d output
        mock_d = MagicMock()
        mock_d.returncode = 0
        mock_d.stdout = "system default destination: HP_LaserJet_1020\n"

        # Mock lpstat -p output
        mock_p = MagicMock()
        mock_p.returncode = 0
        mock_p.stdout = (
            "printer Canon_LBP2900 is idle.  enabled since Wed Nov 25 21:00:00 2026\n"
            "printer HP_LaserJet_1020 is idle.  enabled since Wed Nov 25 20:30:00 2026\n"
            "printer Epson_L3150 now printing Epson_L3150-101.  enabled since Wed Nov 25 21:10:00 2026\n"
        )

        def side_effect(cmd, **kwargs):
            if "-d" in cmd:
                return mock_d
            if "-p" in cmd:
                return mock_p
            return MagicMock(returncode=1)

        mock_run.side_effect = side_effect
        self.mgr.lpstat_bin = "/usr/bin/lpstat"
        self.mgr.lp_bin = "/usr/bin/lp"

        printers = self.mgr.get_printers()
        self.assertEqual(len(printers), 3)

        hp = next(p for p in printers if p.name == "HP_LaserJet_1020")
        self.assertTrue(hp.is_default)
        self.assertEqual(hp.status, "idle")
        self.assertIn("[Default]", hp.description)

        epson = next(p for p in printers if p.name == "Epson_L3150")
        self.assertFalse(epson.is_default)
        self.assertEqual(epson.status, "printing")

    @patch("subprocess.run")
    def test_print_command_arguments(self, mock_run):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "request id is HP_LaserJet_1020-42 (1 file(s))\n"
        mock_run.return_value = mock_res

        self.mgr.lp_bin = "/usr/bin/lp"

        success, msg = self.mgr.print_file(
            file_path="/tmp/test.pdf",
            printer_name="HP_LaserJet_1020",
            copies=2,
            page_size="A4",
            orientation="portrait",
            duplex="long-edge",
            force_grayscale=True,
            fit_to_page=True
        )

        self.assertTrue(success)
        self.assertIn("HP_LaserJet_1020-42", msg)

        # Verify command arguments passed to subprocess
        called_cmd = mock_run.call_args[0][0]
        self.assertIn("-d", called_cmd)
        self.assertIn("HP_LaserJet_1020", called_cmd)
        self.assertIn("-n", called_cmd)
        self.assertIn("2", called_cmd)
        self.assertIn("-o", called_cmd)
        self.assertIn("PageSize=A4", called_cmd)
        self.assertIn("sides=two-sided-long-edge", called_cmd)
        self.assertIn("ColorModel=Gray", called_cmd)
        self.assertIn("print-color-mode=monochrome", called_cmd)
        self.assertIn("fit-to-page", called_cmd)
        self.assertIn("/tmp/test.pdf", called_cmd)

    @patch("subprocess.run")
    def test_print_command_auto_orientation_omits_flag(self, mock_run):
        mock_res = MagicMock()
        mock_res.returncode = 0
        mock_res.stdout = "request id is HP_LaserJet_1020-43 (1 file(s))\n"
        mock_run.return_value = mock_res
        self.mgr.lp_bin = "/usr/bin/lp"

        success, _ = self.mgr.print_file(
            file_path="/tmp/nup.pdf",
            printer_name="HP_LaserJet_1020",
            orientation="auto"
        )
        self.assertTrue(success)
        called_cmd = mock_run.call_args[0][0]
        self.assertFalse(any("orientation-requested" in arg for arg in called_cmd))

    @patch("subprocess.run")
    def test_gutenprint_canon_ip2772_black_only_and_no_duplex(self, mock_run):
        lpoptions_out = (
            "PageSize/Media Size: Letter *A4 A5\n"
            "ColorModel/Color Model: Gray Black *RGB CMYK\n"
            "StpInkType/Ink Type: *CMYK RGB Gray\n"
            "StpInkSet/Ink Set: *Both Black Color\n"
            "StpQuality/Print Quality: *None Standard\n"
        )
        mock_opt = MagicMock(returncode=0, stdout=lpoptions_out)
        mock_lp = MagicMock(returncode=0, stdout="request id is iP2772-155 (1 file(s))\n")

        def side_effect(cmd, **kwargs):
            if "lpoptions" in cmd[0]:
                return mock_opt
            return mock_lp

        mock_run.side_effect = side_effect
        self.mgr.lp_bin = "/usr/bin/lp"
        self.mgr.lpoptions_bin = "/usr/bin/lpoptions"

        caps = self.mgr.get_printer_capabilities("iP2772", refresh=True)
        self.assertTrue(caps.is_gutenprint)
        self.assertTrue(caps.has_stp_ink_set_black)
        self.assertTrue(caps.has_stp_ink_type_gray)
        self.assertEqual(caps.gray_color_model, "Gray")
        self.assertFalse(caps.supports_duplex)

        success, _ = self.mgr.print_file(
            file_path="/tmp/test.pdf",
            printer_name="iP2772",
            duplex="short-edge",
            force_grayscale=True
        )
        self.assertTrue(success)
        called_cmd = mock_run.call_args[0][0]
        self.assertIn("StpInkSet=Black", called_cmd)
        self.assertIn("StpInkType=Gray", called_cmd)
        self.assertIn("ColorModel=Gray", called_cmd)
        self.assertIn("sides=one-sided", called_cmd)
        self.assertNotIn("sides=two-sided-short-edge", called_cmd)


if __name__ == "__main__":
    unittest.main()
