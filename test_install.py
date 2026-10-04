import tempfile
import json
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

import betterdiscord as bd


def archive(content):
    header = json.dumps({"files": {"main.js": {"offset": "0", "size": len(content)}}}).encode()
    padding = b"\0" * (-(len(header) + 4) % 4)
    payload = struct.pack("<I", len(header)) + header + padding
    pickle = struct.pack("<I", len(payload)) + payload
    return struct.pack("<II", 4, len(pickle)) + pickle + content


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "discord"
        self.core = self.data / "app-0.0.414/modules/discord_desktop_core-2/discord_desktop_core"
        self.core.mkdir(parents=True)
        (self.core / "core.asar").write_bytes(b"core")
        self.index = self.core / "index.js"
        self.original = b"module.exports = require('./core.asar');\n"
        self.index.write_bytes(self.original)
        self.asar = self.root / "custom-name.asar"
        self.previous_archive = archive(b"previous archive")
        self.new_archive = archive(b"new archive")
        self.asar.write_bytes(self.previous_archive)
        self.options = bd.Options(
            "stable", self.data, self.asar, False, True, True, True,
            False, "latest", False, False, 1, False,
        )
        self.addCleanup(patch.stopall)
        patch("betterdiscord.platform.system", return_value="Windows").start()
        patch("betterdiscord.discord_update_dir", return_value=None).start()
        patch("betterdiscord.log_discord_app_version").start()
        self.running = patch("betterdiscord.discord_running", side_effect=[True, False]).start()
        self.quit = patch("betterdiscord.quit_discord").start()
        self.open = patch("betterdiscord.open_discord").start()
        self.download = patch("betterdiscord.download_asar", side_effect=self.download_archive).start()

    def download_archive(self, path, **kwargs):
        if not kwargs["dry_run"]:
            path.write_bytes(self.new_archive)
        return True

    def test_failed_download_leaves_discord_and_files_untouched(self):
        self.download.side_effect = OSError("network failed")
        with self.assertRaisesRegex(OSError, "network failed"):
            bd.install(self.options)
        self.quit.assert_not_called()
        self.open.assert_not_called()
        self.assertEqual(self.index.read_bytes(), self.original)
        self.assertEqual(self.asar.read_bytes(), self.previous_archive)

    def test_successful_install_and_rollback_restore_original_files(self):
        bd.install(self.options)
        self.assertEqual(self.asar.read_bytes(), self.new_archive)
        self.assertIn(b"betterdiscord", self.index.read_bytes())
        self.running.side_effect = None
        self.running.return_value = False
        bd.rollback(self.options)
        self.assertEqual(self.index.read_bytes(), self.original)
        self.assertEqual(self.asar.read_bytes(), self.previous_archive)

    def test_patch_failure_restores_archive_and_loader_and_reopens(self):
        def failed_patch(core, dry_run):
            (core / "index.js").write_bytes(b"partial change")
            raise OSError("patch failed")
        with patch("betterdiscord.patch_core", side_effect=failed_patch), patch("betterdiscord.cleanup_old_versions") as cleanup:
            with self.assertRaisesRegex(OSError, "patch failed"):
                bd.install(bd.replace(self.options, cleanup_before_install=True))
            cleanup.assert_not_called()
        self.assertEqual(self.index.read_bytes(), self.original)
        self.assertEqual(self.asar.read_bytes(), self.previous_archive)
        self.open.assert_called_once()

    def test_rollback_checks_all_backup_files_before_writing(self):
        backup = bd.create_install_backup(self.options, [self.core])
        (backup / "0").write_bytes(b"corrupt backup")
        self.index.write_bytes(b"current loader")
        with self.assertRaisesRegex(RuntimeError, "checksum"):
            bd.restore_install_backup(backup, self.options)
        self.assertEqual(self.index.read_bytes(), b"current loader")
        self.assertEqual(self.asar.read_bytes(), self.previous_archive)

    def test_preview_does_not_create_backups_or_quit(self):
        bd.install(bd.replace(self.options, dry_run=True))
        self.quit.assert_not_called()
        self.assertFalse((self.data / ".betterdiscord-patcher").exists())
        self.assertEqual(self.index.read_bytes(), self.original)

    def test_doctor_is_read_only_and_reports_missing_archive(self):
        self.asar.unlink()
        before = sorted(str(path) for path in self.root.rglob("*"))
        self.assertFalse(bd.doctor(self.options))
        self.assertEqual(before, sorted(str(path) for path in self.root.rglob("*")))
        self.quit.assert_not_called()
        self.download.assert_not_called()

    def test_no_op_install_keeps_previous_rollback_backup(self):
        self.index.write_text(bd.INJECTION)
        self.running.side_effect = None
        self.running.return_value = False
        bd.install(bd.replace(self.options, download=False))
        self.assertFalse((self.data / ".betterdiscord-patcher/backups").exists())

    def test_truncated_archive_rejected_before_quitting(self):
        def truncated(path, **kwargs):
            path.write_bytes(self.new_archive[:-2])
        self.download.side_effect = truncated
        with self.assertRaisesRegex(RuntimeError, "truncated"):
            bd.install(self.options)
        self.quit.assert_not_called()
        self.assertEqual(self.asar.read_bytes(), self.previous_archive)

    def test_atomic_write_failure_preserves_original_file(self):
        with patch("betterdiscord.os.replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                bd.atomic_write(self.asar, self.new_archive)
        self.assertEqual(self.asar.read_bytes(), self.previous_archive)
        self.assertEqual(list(self.root.glob(".custom-name.asar-*")), [])

    def test_rollback_preview_preserves_installed_files(self):
        bd.install(self.options)
        self.quit.reset_mock()
        self.running.side_effect = None
        self.running.return_value = True
        bd.rollback(bd.replace(self.options, dry_run=True))
        self.quit.assert_not_called()
        self.assertEqual(self.asar.read_bytes(), self.new_archive)
        self.assertIn(b"betterdiscord", self.index.read_bytes())

    def test_cleanup_failure_does_not_undo_successful_install(self):
        with patch("betterdiscord.sanitize_shipit_request", return_value=set()), patch(
            "betterdiscord.cleanup_old_versions", side_effect=PermissionError("locked")
        ):
            bd.install(bd.replace(self.options, cleanup_before_install=True))
        self.assertEqual(self.asar.read_bytes(), self.new_archive)
        self.assertIn(b"betterdiscord", self.index.read_bytes())
        self.open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
