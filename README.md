# BetterDiscordPatcher

![macOS](https://img.shields.io/badge/macOS-supported-0A84FF)
![Python](https://img.shields.io/badge/python-3.x-34C759)
![Shell](https://img.shields.io/badge/install-curl%20%7C%20sh-FF9F0A)

Small macOS patcher that installs the BetterDiscord loader into Discord's
desktop core.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/ctrlcmdshft/BetterDiscordPatcher/main/install.sh | sh
```

The installer creates a config file, installs the `betterdiscord` command, and
offers to open the config. Add `~/.local/bin` to `PATH` if the command is not
found after install.

## Commands

```sh
betterdiscord
betterdiscord --dry-run
betterdiscord --edit-config
betterdiscord --format-config
betterdiscord --release canary
betterdiscord --cleanup-old --dry-run
betterdiscord --unpatch
betterdiscord --update
betterdiscord --uninstall
```

## Releases

Default release is `stable`.

```sh
betterdiscord --release stable
betterdiscord --release auto
betterdiscord --release ptb
betterdiscord --release canary
betterdiscord --release development
betterdiscord --release all
```

`auto` detects installed Discord apps in `/Applications`. Explicit release flags
target that release's app name, data folder, updater state, and reopen behavior.

## Config

Config lives at:

```text
~/.config/betterdiscord-patcher/config.json
```

Command-line options override config values. Reformat an existing config with:

```sh
betterdiscord --format-config
```

Generated config:

```json
{
  "release": "stable",
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

| Key | Meaning |
| --- | --- |
| `release` | Discord release to patch: `stable`, `auto`, `all`, `ptb`, `canary`, or `development`. |
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

Cleanup only removes old `app-*` folders. It keeps the newest `app-*` folder and
protects the version matching the installed Discord app.

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
the script command and asks before removing config.
