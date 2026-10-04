import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import betterdiscord as bd


def plugin(name="Example", version="1.0"):
    return f"/**\n * @name {name}\n * @author Example\n * @version {version}\n * @description Example plugin\n */\nmodule.exports = class {{}};".encode()


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / "BetterDiscord/plugins"
        self.directory.mkdir(parents=True)
        self.manifest = self.root / "plugins.json"
        self.entries = [{"filename": "Example.plugin.js", "url": "https://example.test/Example.plugin.js"}]
        self.manifest.write_text(json.dumps({"plugins": self.entries}))
        self.options = bd.Options("stable", self.root / "discord", self.root / "bd.asar", False,
                                  True, True, False, False, "latest", False, False, 1, False)
        self.addCleanup(patch.stopall)
        self.fetch = patch("betterdiscord.fetch_plugin_resource", return_value=plugin()).start()
        patch("betterdiscord.discord_running", return_value=False).start()
        self.quit = patch("betterdiscord.quit_discord").start()
        self.open = patch("betterdiscord.open_discord").start()

    def install(self, options=None):
        bd.install_plugins(options or self.options, str(self.manifest), self.directory)

    def test_install_preserves_other_plugins_and_settings(self):
        settings = self.directory / "Example.config.json"
        settings.write_text('{"custom":true}')
        unrelated = self.directory / "Unrelated.plugin.js"
        unrelated.write_bytes(plugin("Unrelated"))
        self.install()
        self.assertEqual((self.directory / "Example.plugin.js").read_bytes(), plugin())
        self.assertEqual(settings.read_text(), '{"custom":true}')
        self.assertEqual(unrelated.read_bytes(), plugin("Unrelated"))

    def test_no_change_install_creates_no_backup(self):
        (self.directory / "Example.plugin.js").write_bytes(plugin())
        self.install()
        self.assertFalse((self.directory.parent / ".betterdiscord-patcher").exists())
        self.quit.assert_not_called()

    def test_preview_does_not_download_or_write_plugins(self):
        self.install(bd.replace(self.options, dry_run=True))
        self.fetch.assert_not_called()
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_bad_download_leaves_existing_plugin_unchanged(self):
        existing = self.directory / "Example.plugin.js"
        existing.write_bytes(plugin(version="old"))
        self.fetch.return_value = b"<html>Not a plugin</html>"
        with self.assertRaisesRegex(ValueError, "metadata"):
            self.install()
        self.assertEqual(existing.read_bytes(), plugin(version="old"))
        self.quit.assert_not_called()

    def test_partial_install_failure_restores_previous_plugins(self):
        self.entries.append({"filename": "Second.plugin.js", "url": "https://example.test/Second.plugin.js"})
        self.manifest.write_text(json.dumps({"plugins": self.entries}))
        existing = self.directory / "Example.plugin.js"
        existing.write_bytes(plugin(version="old"))
        self.fetch.side_effect = [plugin(), plugin("Second")]
        write = bd.atomic_write
        def failed_write(path, data):
            if path == self.directory / "Second.plugin.js":
                raise OSError("disk full")
            write(path, data)
        with patch("betterdiscord.atomic_write", side_effect=failed_write):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.install()
        self.assertEqual(existing.read_bytes(), plugin(version="old"))
        self.assertFalse((self.directory / "Second.plugin.js").exists())

    def test_path_traversal_is_rejected(self):
        self.entries[0]["filename"] = "../Example.plugin.js"
        self.manifest.write_text(json.dumps({"plugins": self.entries}))
        with self.assertRaisesRegex(ValueError, "filenames"):
            self.install()
        self.fetch.assert_not_called()

    def test_checksum_mismatch_is_rejected(self):
        self.entries[0]["sha256"] = "0" * 64
        self.manifest.write_text(json.dumps({"plugins": self.entries}))
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.install()
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_gist_page_uses_plugins_json_raw_file(self):
        gist = {"files": {"plugins.json": {"raw_url": "https://gist.githubusercontent.com/example/raw/plugins.json"}}}
        self.fetch.side_effect = [json.dumps(gist).encode(), json.dumps({"plugins": self.entries}).encode()]
        result = bd.load_plugin_manifest("https://gist.github.com/example/" + "a" * 32)
        self.assertEqual(result, self.entries)
        self.assertEqual(self.fetch.call_args.args[0], gist["files"]["plugins.json"]["raw_url"])

    def test_manifest_with_duplicate_filenames_is_rejected(self):
        self.entries.append(dict(self.entries[0]))
        self.manifest.write_text(json.dumps({"plugins": self.entries}))
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.install()
        self.fetch.assert_not_called()

    def test_duplicate_installed_plugin_under_other_filename_is_rejected(self):
        (self.directory / "OtherFilename.plugin.js").write_bytes(plugin())
        with self.assertRaisesRegex(ValueError, "different filename"):
            self.install()
        self.assertFalse((self.directory / "Example.plugin.js").exists())

    def test_running_discord_is_quit_and_reopened(self):
        with patch("betterdiscord.discord_running", side_effect=[True, False]):
            self.install()
        self.quit.assert_called_once()
        self.open.assert_called_once()


if __name__ == "__main__":
    unittest.main()
