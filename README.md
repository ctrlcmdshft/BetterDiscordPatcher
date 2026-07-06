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
betterdiscord --check-update
betterdiscord --ptb
betterdiscord --canary
betterdiscord --all
betterdiscord --dry-run
betterdiscord --edit-config
betterdiscord --format-config
betterdiscord --cleanup-old --dry-run
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
Interactive runs can offer to update immediately.
Use `betterdiscord --update` to refresh the installed script from GitHub.

| Key | Meaning |
| --- | --- |
| `discord_data` | Discord data folder to patch. |
| `bd_asar` | Destination for `betterdiscord.asar`. |
| `download` | Download or refresh `betterdiscord.asar`. |
| `wait_update` | Wait for Discord's updater to finish before patching. |
| `cleanup_before_install` | Remove old Discord `app-*` folders before patching. |
| `keep_versions` | Number of Discord `app-*` versions to keep when cleaning. |
| `keep_open` | Patch without quitting Discord first. |
| `reopen` | Reopen Discord only if it was running before patching. |
| `notify` | Show macOS notifications. |

## Cleanup

Cleanup only removes old `app-*` folders and keeps the newest app version folder.

```sh
betterdiscord --cleanup-old --dry-run
betterdiscord --cleanup-old
```

## Uninstall

```sh
betterdiscord --unpatch
betterdiscord --uninstall
```

`--unpatch` removes the BetterDiscord loader from Discord. `--uninstall` removes
the script command, removes its Windows `PATH` entry, and keeps config unless
you confirm removal or pass `--remove-config`.
