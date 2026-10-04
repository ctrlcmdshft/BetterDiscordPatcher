import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import betterdiscord as bd


class DiscordStartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / "discord"
        self.data.mkdir()
        self.addCleanup(patch.stopall)
        patch("betterdiscord.platform.system", return_value="Darwin").start()

    def renderer_log(self, content):
        logs = self.data / "logs"
        logs.mkdir()
        renderer = logs / "renderer_js.log"
        renderer.write_text(content)
        return renderer

    def test_startup_check_ignores_old_errors_but_detects_new_errors(self):
        renderer = self.renderer_log("fatal error: old failure\n")
        positions = bd.startup_log_positions(self.data)
        with renderer.open("a") as file:
            file.write("[info] Discord ready\n")
        self.assertTrue(bd.check_discord_errors(self.data, positions))
        with renderer.open("a") as file:
            file.write("Cannot find module 'discord_desktop_core'\n")
        self.assertFalse(bd.check_discord_errors(self.data, positions))

    def test_latest_session_does_not_report_previous_session_error(self):
        self.renderer_log("fatal error: yesterday\nsplashScreenPreload: signalReady\nready\n")
        self.assertTrue(bd.check_discord_errors(self.data))

    def test_missing_logs_are_not_reported_as_healthy(self):
        self.assertFalse(bd.check_discord_errors(self.data))

    def test_startup_verification_reports_new_error(self):
        renderer = self.renderer_log("ready\n")
        positions = bd.startup_log_positions(self.data)
        with renderer.open("a") as file:
            file.write("fatal: Error: launch failed\n")
        self.assertFalse(bd.verify_discord_startup(self.data, positions, 1))

    def test_startup_verification_passes_when_running_without_new_errors(self):
        self.renderer_log("ready\n")
        positions = bd.startup_log_positions(self.data)
        with patch("betterdiscord.time.monotonic", side_effect=[0, 0, 0, 1]), patch(
            "betterdiscord.time.sleep"
        ), patch("betterdiscord.discord_running", return_value=True):
            self.assertTrue(bd.verify_discord_startup(self.data, positions, 1))


if __name__ == "__main__":
    unittest.main()
