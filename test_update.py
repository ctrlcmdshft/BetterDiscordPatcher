import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import betterdiscord as bd


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.script = self.directory / "betterdiscord.py"
        self.script.write_text('SCRIPT_VERSION = "2.2.0"\n')
        self.addCleanup(patch.stopall)
        self.latest = patch("betterdiscord.latest_script_version", return_value="2.2.1").start()
        self.download = patch("betterdiscord.download_file", side_effect=self.fetch).start()

    def fetch(self, url, destination):
        destination.write_text('SCRIPT_VERSION = "2.2.1"\n' if destination.name == "betterdiscord.py" else "content\n")

    def test_up_to_date_does_not_replace_files(self):
        self.latest.return_value = "2.2.0"
        before = self.script.stat().st_mtime_ns
        with self.assertLogs(bd.LOG, level="INFO") as logs:
            self.assertTrue(bd.update_script(self.directory, "https://example.test"))
        self.assertIn("You are up to date: 2.2.0", "\n".join(logs.output))
        self.assertEqual(self.script.stat().st_mtime_ns, before)
        self.download.assert_not_called()

    def test_newer_local_version_is_not_downgraded(self):
        self.latest.return_value = "2.1.9"
        self.assertTrue(bd.update_script(self.directory, "https://example.test"))
        self.download.assert_not_called()

    def test_network_check_failure_returns_failure_without_writes(self):
        self.latest.return_value = None
        self.assertFalse(bd.update_script(self.directory, "https://example.test"))
        self.download.assert_not_called()
        self.assertEqual(self.script.read_text(), 'SCRIPT_VERSION = "2.2.0"\n')

    def test_download_failure_preserves_installed_script(self):
        self.download.side_effect = OSError("offline")
        self.assertFalse(bd.update_script(self.directory, "https://example.test"))
        self.assertEqual(self.script.read_text(), 'SCRIPT_VERSION = "2.2.0"\n')

    def test_success_reports_installed_and_updated_versions(self):
        with self.assertLogs(bd.LOG, level="INFO") as logs:
            self.assertTrue(bd.update_script(self.directory, "https://example.test"))
        self.assertIn("Updated patcher: 2.2.0 -> 2.2.1", "\n".join(logs.output))
        self.assertEqual(self.script.read_text(), 'SCRIPT_VERSION = "2.2.1"\n')

    def test_invalid_python_is_rejected_before_replacement(self):
        def invalid(url, destination):
            self.fetch(url, destination)
            if destination.name == "betterdiscord.py":
                with destination.open("a") as file:
                    file.write("this is invalid syntax !")
        self.download.side_effect = invalid
        self.assertFalse(bd.update_script(self.directory, "https://example.test"))
        self.assertEqual(self.script.read_text(), 'SCRIPT_VERSION = "2.2.0"\n')


if __name__ == "__main__":
    unittest.main()
