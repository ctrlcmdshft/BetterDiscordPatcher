# BetterDiscordPatcher

![macOS](https://img.shields.io/badge/macOS-supported-0A84FF)
![Windows](https://img.shields.io/badge/Windows-supported-FF9F0A)
![Python](https://img.shields.io/badge/python-3.x-34C759)

Small patcher that installs the BetterDiscord loader into Discord's desktop
core.

Small cross-platform patcher for BetterDiscord on macOS and Windows.

## Install

macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/ctrlcmdshft/BetterDiscordPatcher/main/install.sh | sh
```

Windows:

```powershell
irm https://raw.githubusercontent.com/ctrlcmdshft/BetterDiscordPatcher/main/install.ps1 | iex
```

The Windows installer places the script under `%LOCALAPPDATA%\BetterDiscordPatcher`,
creates `betterdiscord.cmd`, and adds that directory to the user `PATH`.

## Commands

```sh
betterdiscord
betterdiscord --version
betterdiscord --doctor
betterdiscord --rollback --dry-run
betterdiscord --rollback
betterdiscord --check-update
betterdiscord --ptb
betterdiscord --canary
betterdiscord --all
betterdiscord --dry-run
betterdiscord --repair --dry-run
betterdiscord --repair
betterdiscord --edit-config
betterdiscord --format-config
betterdiscord --cleanup-old --dry-run
betterdiscord --list-bd-releases 10
betterdiscord --downgrade --dry-run
betterdiscord --downgrade --bd-previous 3
betterdiscord --bd-release v1.14.0
betterdiscord --unpatch
betterdiscord --update
betterdiscord --uninstall
```

`auto` detects installed Discord apps in `/Applications`. Explicit release flags
target that release's app name, data folder, updater state, and reopen behavior.

## Config

Config paths:

```text
~/.config/betterdiscord-patcher/config.json
%APPDATA%\BetterDiscordPatcher\config.json
```

Command-line options override config values. Reformat an existing config with:

```sh
betterdiscord --format-config
```

Generated config:

```json
{
  "discord_data": "~/Library/Application Support/discord",
  "bd_asar": "~/Library/Application Support/BetterDiscord/data/betterdiscord.asar",
  "download": true,
  "wait_update": true,
  "cleanup_before_install": true,
  "keep_versions": 1,
  "keep_open": false,
  "reopen": true,
  "notify": false
}
```

The example above shows macOS paths. Windows uses `%LOCALAPPDATA%` for Discord
data and `%APPDATA%` for BetterDiscord/config paths.

Release flags choose which Discord install to target without changing the saved
config path:

```sh
betterdiscord --stable
betterdiscord --ptb
betterdiscord --canary
betterdiscord --all
betterdiscord --auto
```

Check the installed script version with:

```sh
betterdiscord --version
```

Check for a newer script version with:

```sh
betterdiscord --check-update
```

The script also warns during normal runs when a newer version is available.
Interactive runs can offer to update immediately and then continue the original command.
Use `betterdiscord --update` to refresh the installed script from GitHub.

| Key | Meaning |
| --- | --- |
| `discord_data` | Discord data folder to patch. |
| `bd_asar` | Destination for `betterdiscord.asar`. |
| `download` | Download or refresh `betterdiscord.asar`. |
| `wait_update` | Wait for Discord's updater to finish before patching. |
| `cleanup_before_install` | Remove old Discord `app-*` folders after successful patching (legacy option name). |
| `keep_versions` | Number of Discord `app-*` versions to keep when cleaning. |
| `keep_open` | Patch without quitting Discord first. |
| `reopen` | Reopen Discord only if it was running before patching. |
| `notify` | Show macOS notifications. |

## Repair

On macOS, if Discord reports `Cannot find module 'discord_desktop_core'`, run:

```sh
betterdiscord --repair --dry-run
betterdiscord --repair
```

When the current Discord core files are missing, repair quits Discord, moves its
updater database into a `core-repair-backup-*` folder inside the Discord data
folder, and reopens Discord to download the missing files. It then restores the
BetterDiscord loader, keeping your existing BetterDiscord version when available.
Your settings, plugins, and themes are preserved. Internet access is required to
rebuild missing files. Repair skips old-version cleanup and currently supports
macOS only. If core files already exist, it only restores the loader.

## Diagnostics and Rollback

```sh
betterdiscord --doctor
betterdiscord --rollback --dry-run
betterdiscord --rollback
```

`--doctor` checks local version folders, core loaders, the BetterDiscord file,
and available backups without changing files or offering a script update.
It exits with a nonzero status when file checks find a problem. It does not
test plugin compatibility or whether Discord can connect.

Installations stage downloads before quitting Discord or changing installed
files. Before replacing an archive or patching a loader, the script saves the
previous files under `.betterdiscord-patcher/backups` in the Discord data folder.
Files are replaced atomically, and a failed installation attempts to restore
that backup. Downloads are checked for valid archive structure and truncated
file contents before installation. Cleanup runs only after installation succeeds and preserves the
installed macOS app version.

`--rollback` restores the latest completed installation backup after checking
its file checksums. It does not downgrade Discord itself, restore deleted old
app folders, or undo plugin and theme changes. If Discord has updated and none
of the saved cores remain installed, rollback stops without changing files.
BetterDiscord's archive is shared between releases, so restoring it also affects
other Discord releases using that archive. Backups remain available for manual
recovery; a no-change installation does not replace the latest backup.

Use `--ptb` or `--canary` to diagnose or roll back that release. `--doctor` and
`--rollback` cannot be combined with other actions such as `--repair` or `--downgrade`.

## Cleanup

Cleanup only removes old `app-*` folders and keeps the newest app version folder.

```sh
betterdiscord --cleanup-old --dry-run
betterdiscord --cleanup-old
```

## Downgrade

Downgrade downloads the previous stable BetterDiscord `betterdiscord.asar`
release, then patches Discord's desktop core. You can also install a specific
BetterDiscord release tag or choose from recent prior stable releases.

```sh
betterdiscord --list-bd-releases 10
betterdiscord --downgrade --dry-run
betterdiscord --downgrade
betterdiscord --downgrade --bd-previous 3
betterdiscord --bd-release previous:3
betterdiscord --bd-release v1.14.0
```

## Uninstall

```sh
betterdiscord --unpatch
betterdiscord --uninstall
```

`--unpatch` removes the BetterDiscord loader from Discord. `--uninstall` removes
the script command, removes its Windows `PATH` entry, and keeps config unless
you confirm removal or pass `--remove-config`.
