import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import betterdiscord as bd


class RepairTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.data = self.root / "discord"
        self.data.mkdir()
        self.app = self.root / "Discord.app"
        resources = self.app / "Contents/Resources"
        resources.mkdir(parents=True)
        (resources / "build_info.json").write_text('{"version":"0.0.414"}')
        self.core = self.data / "app-0.0.414/modules/discord_desktop_core-2/discord_desktop_core"
        self.asar = self.root / "betterdiscord.asar"
        self.asar.write_bytes(b"existing BetterDiscord")
        self.options = bd.Options(
            "stable", self.data, self.asar, False, True, True, True,
            False, "latest", False, True, 1, False,
        )
        self.addCleanup(patch.stopall)
        patch("betterdiscord.platform.system", return_value="Darwin").start()
        patch("betterdiscord.discord_release_for_data", return_value=SimpleNamespace(
            app_path=self.app, app_name="Discord", name="Discord",
        )).start()
        self.install = patch("betterdiscord.install").start()
        self.run = patch("betterdiscord.subprocess.run", return_value=SimpleNamespace(returncode=1)).start()
        self.open = patch("betterdiscord.open_discord", side_effect=self.rebuild).start()

    def rebuild(self, data):
        self.core.mkdir(parents=True)
        (self.core / "core.asar").write_bytes(b"core")
        (self.core / "index.js").write_text("module.exports = require('./core.asar');")

    def test_missing_core_backs_up_database_and_preserves_bd(self):
        for suffix in ("", "-wal", "-shm"):
            (self.data / ("installer.db" + suffix)).write_bytes(b"original" + suffix.encode())
        bd.repair_discord(self.options)
        backup, = self.data.glob("core-repair-backup-*")
        for suffix in ("", "-wal", "-shm"):
            self.assertEqual((backup / ("installer.db" + suffix)).read_bytes(), b"original" + suffix.encode())
        self.assertFalse((self.data / "installer.db").exists())
        repaired = self.install.call_args.args[0]
        self.assertFalse(repaired.download)
        self.assertFalse(repaired.cleanup_before_install)
        self.assertTrue(repaired.restart)

    def test_dry_run_does_not_quit_launch_or_move_database(self):
        database = self.data / "installer.db"
        database.write_bytes(b"original")
        bd.repair_discord(bd.replace(self.options, dry_run=True))
        self.assertEqual(database.read_bytes(), b"original")
        self.run.assert_not_called()
        self.open.assert_not_called()
        self.install.assert_not_called()

    def test_existing_core_leaves_database_alone(self):
        self.rebuild(self.data)
        database = self.data / "installer.db"
        database.write_bytes(b"original")
        bd.repair_discord(self.options)
        self.assertEqual(database.read_bytes(), b"original")
        self.open.assert_not_called()
        self.install.assert_called_once()


if __name__ == "__main__":
    unittest.main()
