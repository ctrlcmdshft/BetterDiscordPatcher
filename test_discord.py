import json
import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import betterdiscord as bd

FETCH_DISCORD_APP = bd.fetch_discord_app


class DiscordTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "discord"
        self.data.mkdir()
        self.app = self.root / "Discord.app"
        self.make_version("0.0.414")
        self.options = bd.Options("stable", self.data, self.root / "bd.asar", False,
                                  True, True, False, False, "latest", False, False, 1, False)
        self.release = SimpleNamespace(app_path=self.app, app_name="Discord", name="Discord")
        self.addCleanup(patch.stopall)
        patch("betterdiscord.platform.system", return_value="Darwin").start()
        patch("betterdiscord.discord_release_for_data", return_value=self.release).start()
        patch("betterdiscord.discord_running", return_value=False).start()
        patch("betterdiscord.shipit_running", return_value=False).start()
        self.open = patch("betterdiscord.open_discord").start()
        self.fetch = patch("betterdiscord.fetch_discord_app", side_effect=self.download_app).start()

    def download_app(self, version, directory):
        app = directory / "downloaded.app"
        resources = app / "Contents/Resources"
        resources.mkdir(parents=True)
        (resources / "build_info.json").write_text(json.dumps({"version": version}))
        binary = app / "Contents/MacOS/Discord"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(version.encode())
        return app

    def make_version(self, version):
        resources = self.app / "Contents/Resources"
        resources.mkdir(parents=True, exist_ok=True)
        (resources / "build_info.json").write_text(json.dumps({"version": version}))
        binary = self.app / "Contents/MacOS/Discord"
        binary.parent.mkdir(parents=True, exist_ok=True)
        binary.write_bytes(version.encode())
        core = self.data / f"app-{version}/modules/discord_desktop_core-1/discord_desktop_core"
        core.mkdir(parents=True, exist_ok=True)
        (core / "core.asar").write_bytes(version.encode())
        (core / "index.js").write_text("module.exports = require('./core.asar');")
        (self.data / "installer.db").write_bytes(version.encode())

    def test_downgrade_downloads_app_without_retaining_old_versions(self):
        bd.downgrade_discord(self.options, "0.0.413")
        self.assertEqual(bd.discord_app_version(self.app), "0.0.413")
        self.assertFalse((self.data / "installer.db").exists())
        self.assertEqual(list(self.root.glob(".discord-downgrade-*")), [])
        self.assertFalse((self.data / ".betterdiscord-patcher/discord-backups").exists())

    def test_unavailable_download_does_not_modify_app(self):
        self.fetch.side_effect = OSError("download unavailable")
        with self.assertRaisesRegex(OSError, "unavailable"):
            bd.downgrade_discord(self.options, "0.0.413")
        self.assertEqual(bd.discord_app_version(self.app), "0.0.414")
        self.assertEqual((self.data / "installer.db").read_bytes(), b"0.0.414")

    def test_dry_run_downgrade_does_not_replace_or_back_up(self):
        bd.downgrade_discord(bd.replace(self.options, dry_run=True), "0.0.413")
        self.assertEqual(bd.discord_app_version(self.app), "0.0.414")
        self.fetch.assert_not_called()

    def test_failed_replacement_restores_current_app(self):
        real_replace = bd.os.replace
        failed = False
        def replace(source, target):
            nonlocal failed
            if Path(source).name == "downloaded.app" and Path(target) == self.app and not failed:
                failed = True
                raise OSError("cannot replace database")
            return real_replace(source, target)
        with patch("betterdiscord.os.replace", side_effect=replace):
            with self.assertRaisesRegex(OSError, "cannot replace"):
                bd.downgrade_discord(self.options, "0.0.413")
        self.assertEqual(bd.discord_app_version(self.app), "0.0.414")
        self.assertEqual((self.data / "installer.db").read_bytes(), b"0.0.414")

    def test_startup_check_ignores_old_errors_but_detects_new_errors(self):
        logs = self.data / "logs"
        logs.mkdir()
        renderer = logs / "renderer_js.log"
        renderer.write_text("fatal error: old failure\n")
        positions = bd.startup_log_positions(self.data)
        with renderer.open("a") as file:
            file.write("[info] Discord ready\n")
        self.assertTrue(bd.check_discord_errors(self.data, positions))
        with renderer.open("a") as file:
            file.write("Cannot find module 'discord_desktop_core'\n")
        self.assertFalse(bd.check_discord_errors(self.data, positions))

    def test_latest_session_does_not_report_previous_session_error(self):
        logs = self.data / "logs"
        logs.mkdir()
        (logs / "renderer_js.log").write_text("fatal error: yesterday\nsplashScreenPreload: signalReady\nready\n")
        self.assertTrue(bd.check_discord_errors(self.data))

    def test_missing_logs_are_not_reported_as_healthy(self):
        self.assertFalse(bd.check_discord_errors(self.data))

    def test_newer_version_is_rejected_without_download(self):
        with self.assertRaisesRegex(ValueError, "older Discord version"):
            bd.downgrade_discord(self.options, "0.0.415")
        self.fetch.assert_not_called()

    def test_downloaded_wrong_version_is_rejected_and_image_detached(self):
        directory = self.root / "download"
        directory.mkdir()
        def run(command, **kwargs):
            if command[:2] == ["hdiutil", "attach"]:
                shutil.copytree(self.app, directory / "mount/Discord.app")
        response = io.BytesIO(b"image")
        response.headers = {"Content-Length": "5"}
        with patch("betterdiscord.urllib.request.urlopen", return_value=response) as download, patch(
            "betterdiscord.subprocess.run", side_effect=run
        ) as command:
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                FETCH_DISCORD_APP("0.0.413", directory)
            self.assertEqual(command.call_args.args[0][:2], ["hdiutil", "detach"])
            request = download.call_args.args[0]
            self.assertEqual(request.get_header("User-agent"), f"{bd.APP_NAME}/{bd.SCRIPT_VERSION}")

    def test_bad_signature_is_rejected_before_app_replacement(self):
        directory = self.root / "download"
        directory.mkdir()
        def run(command, **kwargs):
            if command[:2] == ["hdiutil", "attach"]:
                shutil.copytree(self.app, directory / "mount/Discord.app")
            if command[0] == "codesign":
                raise subprocess.CalledProcessError(1, command)
        response = io.BytesIO(b"image")
        response.headers = {"Content-Length": "5"}
        with patch("betterdiscord.urllib.request.urlopen", return_value=response), patch(
            "betterdiscord.subprocess.run", side_effect=run
        ):
            with self.assertRaises(subprocess.CalledProcessError):
                FETCH_DISCORD_APP("0.0.414", directory)
        self.assertEqual(bd.discord_app_version(self.app), "0.0.414")

    def test_startup_verification_reports_new_error(self):
        logs = self.data / "logs"
        logs.mkdir()
        renderer = logs / "renderer_js.log"
        renderer.write_text("ready\n")
        positions = bd.startup_log_positions(self.data)
        with renderer.open("a") as file:
            file.write("fatal: Error: launch failed\n")
        self.assertFalse(bd.verify_discord_startup(self.data, positions, 1))

    def test_startup_verification_passes_when_running_without_new_errors(self):
        logs = self.data / "logs"
        logs.mkdir()
        (logs / "renderer_js.log").write_text("ready\n")
        positions = bd.startup_log_positions(self.data)
        with patch("betterdiscord.time.monotonic", side_effect=[0, 0, 0, 1]), patch(
            "betterdiscord.time.sleep"
        ), patch("betterdiscord.discord_running", return_value=True):
            self.assertTrue(bd.verify_discord_startup(self.data, positions, 1))


if __name__ == "__main__":
    unittest.main()
