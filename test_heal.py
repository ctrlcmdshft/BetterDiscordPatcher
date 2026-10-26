import io
import json
import os
import plistlib
import struct
import tempfile
import unittest
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import betterdiscord as bd


def archive(content):
    header = json.dumps({"files": {"main.js": {"offset": "0", "size": len(content)}}}).encode()
    padding = b"\0" * (-(len(header) + 4) % 4)
    payload = struct.pack("<I", len(header)) + header + padding
    pickle = struct.pack("<I", len(payload)) + payload
    return struct.pack("<II", 4, len(pickle)) + pickle + content


class FakeResponse:
    def __init__(self, data, headers):
        self._data = data
        self.headers = headers

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class HealTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "discord"
        self.core = self.data / "app-0.0.414/modules/discord_desktop_core-2/discord_desktop_core"
        self.core.mkdir(parents=True)
        (self.core / "core.asar").write_bytes(b"core")
        self.index = self.core / "index.js"
        self.original = 'module.exports = require("./core.asar");\n'
        self.index.write_text(self.original)
        self.asar = self.root / "betterdiscord.asar"
        self.asar.write_bytes(archive(b"current"))
        self.options = bd.Options(
            "stable", self.data, self.asar, False, True, True, True,
            False, "latest", False, False, 1, False,
        )
        self.addCleanup(patch.stopall)
        patch("betterdiscord.platform.system", return_value="Windows").start()
        patch("betterdiscord.discord_update_dir", return_value=None).start()
        patch("betterdiscord.log_discord_app_version").start()
        patch("betterdiscord.discord_running", return_value=False).start()
        self.quit = patch("betterdiscord.quit_discord").start()
        self.open = patch("betterdiscord.open_discord").start()
        self.download = patch("betterdiscord.download_asar", side_effect=self.download_archive).start()

    def download_archive(self, path, **kwargs):
        if not kwargs["dry_run"]:
            path.write_bytes(archive(b"restored"))
        return True

    def test_heal_restores_missing_archive_without_quitting(self):
        self.asar.unlink()
        self.index.write_text('require("/missing/betterdiscord.asar");\nmodule.exports = require("./core.asar");\n')
        self.assertTrue(bd.heal(self.options))
        self.quit.assert_not_called()
        self.open.assert_not_called()
        bd.validate_asar(self.asar.read_bytes())
        self.assertEqual(self.index.read_text(encoding="utf-8"), bd.injection_source(self.asar))
        self.assertTrue(self.download.call_args.kwargs["force"])

    def test_valid_archive_is_not_downloaded_again(self):
        self.index.write_text(bd.injection_source(self.asar))
        self.assertTrue(bd.heal(self.options))
        self.download.assert_not_called()
        self.assertFalse((self.data / ".betterdiscord-patcher").exists())

    def test_failed_download_still_guards_the_loader(self):
        self.asar.unlink()
        self.index.write_text('require("/missing/betterdiscord.asar");\n')
        self.download.side_effect = OSError("offline")
        self.assertFalse(bd.heal(self.options))
        script = self.index.read_text(encoding="utf-8")
        self.assertIn("catch (error)", script)
        self.assertIn('require("./core.asar")', script)
        self.quit.assert_not_called()

    def test_new_app_and_core_wrapper_are_patched(self):
        self.index.write_text(bd.injection_source(self.asar))
        newer = self.data / "app-0.0.500/modules/discord_desktop_core-9/discord_desktop_core"
        newer.mkdir(parents=True)
        (newer / "core.asar").write_bytes(b"core")
        (newer / "index.js").write_text(self.original)
        self.assertTrue(bd.heal(self.options))
        self.assertEqual((newer / "index.js").read_text(encoding="utf-8"), bd.injection_source(self.asar))
        self.download.assert_not_called()

    def test_doctor_flags_outdated_loader(self):
        self.index.write_text('require("/somewhere/betterdiscord.asar");\n')
        self.assertFalse(bd.doctor(self.options))

    def test_injection_javascript_parses(self):
        node = __import__("shutil").which("node")
        if not node:
            self.skipTest("node is not installed")
        script = self.root / "injection.js"
        script.write_text(bd.injection_source(self.asar), encoding="utf-8")
        __import__("subprocess").run([node, "--check", str(script)], check=True)


class DownloadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.asar = self.root / "betterdiscord.asar"
        self.addCleanup(patch.stopall)

    def test_invalid_cache_does_not_send_etag(self):
        self.asar.write_bytes(b"bad")
        self.asar.with_suffix(".etag").write_text('"abc"', encoding="utf-8")
        body = archive(b"fresh")

        def urlopen(request, timeout=30):
            self.assertFalse(request.has_header("If-none-match"))
            return FakeResponse(body, {"ETag": '"next"', "Content-Length": str(len(body))})

        with patch("betterdiscord.urllib.request.urlopen", side_effect=urlopen):
            self.assertTrue(bd.download_asar(self.asar, force=False, dry_run=False))
        self.assertEqual(self.asar.read_bytes(), body)
        self.assertEqual(self.asar.with_suffix(".etag").read_text(encoding="utf-8"), '"next"')

    def test_valid_cache_keeps_file_on_not_modified(self):
        body = archive(b"fresh")
        self.asar.write_bytes(body)
        self.asar.with_suffix(".etag").write_text('"abc"', encoding="utf-8")
        before = self.asar.stat().st_mtime_ns

        def urlopen(request, timeout=30):
            self.assertTrue(request.has_header("If-none-match"))
            raise bd.urllib.error.HTTPError(
                "https://example.test/betterdiscord.asar",
                304,
                "Not Modified",
                Message(),
                io.BytesIO(),
            )

        with patch("betterdiscord.urllib.request.urlopen", side_effect=urlopen):
            self.assertFalse(bd.download_asar(self.asar, force=False, dry_run=False))
        self.assertEqual(self.asar.stat().st_mtime_ns, before)

    def test_short_download_is_rejected(self):
        def urlopen(request, timeout=30):
            return FakeResponse(b"short", {"Content-Length": "100"})

        with patch("betterdiscord.urllib.request.urlopen", side_effect=urlopen):
            with self.assertRaisesRegex(RuntimeError, "ended early"):
                bd.download_asar(self.asar, force=True, dry_run=False)
        self.assertFalse(self.asar.exists())


class UpdateDirTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addCleanup(patch.stopall)
        patch("betterdiscord.platform.system", return_value="Darwin").start()

    def test_app_bundle_url_waits_on_its_parent_directory(self):
        state = self.root / "ShipItState.plist"
        bundle = self.root / "update.ABC" / "Discord.app"
        bundle.mkdir(parents=True)
        with state.open("wb") as file:
            plistlib.dump({"updateBundleURL": bundle.as_uri()}, file)
        release = SimpleNamespace(shipit_state=state)
        with patch("betterdiscord.discord_release_for_data", return_value=release):
            self.assertEqual(bd.discord_update_dir(self.root / "discord"), bundle.parent)

    def test_shipit_update_directory_is_preserved(self):
        state = self.root / "ShipItState.plist"
        staging = self.root / "app-0.0.419" / "ShipIt_update"
        staging.mkdir(parents=True)
        with state.open("wb") as file:
            plistlib.dump({"updateBundleURL": staging.as_uri() + "/"}, file)
        release = SimpleNamespace(shipit_state=state)
        with patch("betterdiscord.discord_release_for_data", return_value=release):
            self.assertEqual(bd.discord_update_dir(self.root / "discord"), staging)

    def test_stale_update_directory_does_not_block(self):
        directory = self.root / "update.OLD"
        directory.mkdir()
        os.utime(directory, (time_old := __import__("time").time() - 10000, time_old))
        with patch("betterdiscord.shipit_running", return_value=False), patch("betterdiscord.time.sleep") as sleep:
            self.assertTrue(bd.wait_for_update(self.root / "discord", directory, timeout=30))
        sleep.assert_not_called()

    def test_fresh_update_directory_is_waited_on(self):
        directory = self.root / "update.NEW"
        directory.mkdir()
        with patch("betterdiscord.shipit_running", return_value=False), patch(
            "betterdiscord.time.monotonic", side_effect=[0, 0, 5, 20]
        ), patch("betterdiscord.time.sleep"):
            self.assertFalse(bd.wait_for_update(self.root / "discord", directory, timeout=10))


class CleanupTests(unittest.TestCase):
    def test_active_version_is_kept_even_when_a_newer_folder_exists(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        data = root / "discord"
        app = root / "Discord.app"
        resources = app / "Contents/Resources"
        resources.mkdir(parents=True)
        (resources / "build_info.json").write_text('{"version":"0.0.414"}', encoding="utf-8")
        for name in ("app-0.0.414", "app-0.0.500"):
            core = data / name / "modules/discord_desktop_core-1/discord_desktop_core"
            core.mkdir(parents=True)
            (core / "core.asar").write_bytes(b"core")
        with patch("betterdiscord.platform.system", return_value="Darwin"), patch(
            "betterdiscord.discord_release_for_data",
            return_value=SimpleNamespace(app_path=app),
        ):
            bd.cleanup_old_versions(data, keep=1, dry_run=False)
        self.assertTrue((data / "app-0.0.414").exists())
        self.assertTrue((data / "app-0.0.500").exists())


class ReleaseTargetTests(unittest.TestCase):
    def test_development_folder_does_not_target_stable(self):
        with patch("betterdiscord.platform.system", return_value="Darwin"):
            release = bd.discord_release_for_data(
                Path("/Users/x/Library/Application Support/discorddevelopment")
            )
        self.assertIsNotNone(release)
        self.assertEqual(release.app_name, "Discord Development")

    def test_windows_development_process_name(self):
        with patch("betterdiscord.platform.system", return_value="Windows"):
            self.assertEqual(
                bd.windows_process_name(Path("DiscordDevelopment")),
                "DiscordDevelopment.exe",
            )

    def test_custom_windows_folder_does_not_kill_stable_discord(self):
        with patch("betterdiscord.platform.system", return_value="Windows"), patch(
            "betterdiscord.subprocess.run"
        ) as run:
            bd.quit_discord(Path(r"C:\Users\x\AppData\Local\NotDiscord"))
        run.assert_not_called()


class WatcherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.plist = self.root / "heal.plist"
        self.log = self.root / "logs" / "heal.log"
        self.data = self.root / "discord"
        self.asar = self.root / "BetterDiscord" / "data" / "betterdiscord.asar"
        self.config = self.root / "config.json"
        self.addCleanup(patch.stopall)
        patch("betterdiscord.platform.system", return_value="Darwin").start()
        patch("betterdiscord.watcher_plist_path", return_value=self.plist).start()
        patch("betterdiscord.watcher_log_path", return_value=self.log).start()
        self.run = patch("betterdiscord.subprocess.run", return_value=SimpleNamespace(
            returncode=0, stdout="", stderr="",
        )).start()

    def test_install_writes_launchd_plist_and_loads_it(self):
        bd.install_watcher([self.data], self.asar, self.config, dry_run=False)
        loaded = plistlib.loads(self.plist.read_bytes())
        self.assertEqual(loaded["Label"], bd.WATCHER_LABEL)
        self.assertIn("--heal", loaded["ProgramArguments"])
        self.assertIn(str(self.config), loaded["ProgramArguments"])
        self.assertIn(str(self.asar.parent), loaded["WatchPaths"])
        self.assertIn(str(self.data), loaded["WatchPaths"])
        self.assertEqual(loaded["StartInterval"], bd.WATCHER_INTERVAL_SECONDS)
        self.assertTrue(any(call.args[0][:2] == ["launchctl", "bootstrap"] for call in self.run.call_args_list))

    def test_dry_run_does_not_write_or_load(self):
        bd.install_watcher([self.data], self.asar, self.config, dry_run=True)
        self.assertFalse(self.plist.exists())
        self.run.assert_not_called()

    def test_remove_unloads_and_deletes_plist(self):
        self.plist.write_bytes(b"plist")
        bd.remove_watcher(dry_run=False)
        self.assertFalse(self.plist.exists())
        self.assertTrue(any(call.args[0][:2] == ["launchctl", "bootout"] for call in self.run.call_args_list))

    def test_windows_task_command_includes_heal(self):
        with patch("betterdiscord.platform.system", return_value="Windows"):
            bd.install_watcher([self.data], self.asar, self.config, dry_run=False)
        command = self.run.call_args.args[0]
        self.assertEqual(command[:3], ["schtasks", "/Create", "/F"])
        self.assertIn("--heal", command[-1])
        self.assertIn(str(self.config), command[-1])


if __name__ == "__main__":
    unittest.main()
