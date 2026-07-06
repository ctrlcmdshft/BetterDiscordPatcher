# BetterDiscordPatcher

Small script that patches Discord to load BetterDiscord.

This branch contains early Windows support groundwork. macOS remains the stable
path until Windows install and patch flows are tested on a Windows machine.

## Install

macOS:

```sh
curl -fsSL https://raw.githubusercontent.com/ctrlcmdshft/BetterDiscordPatcher/main/install.sh | sh
```

Windows branch preview:

```powershell
irm https://raw.githubusercontent.com/ctrlcmdshft/BetterDiscordPatcher/windows/install.ps1 | iex
```

The installer creates a config file and asks whether to open it. If the command
is not found after install, add `~/.local/bin` to your `PATH`.

## Use

```sh
betterdiscord
```

Other useful commands:

```sh
betterdiscord --edit-config
betterdiscord --dry-run
betterdiscord --update
betterdiscord --unpatch
betterdiscord --uninstall
betterdiscord --help
```

## Config

Config lives at:

```text
~/.config/betterdiscord-patcher/config.json
%APPDATA%\BetterDiscordPatcher\config.json
```

Command-line options override config values.

Config keys:

| Key | Meaning |
| --- | --- |
| `notify` | Show macOS notifications. |
| `keep_open` | Patch without quitting Discord first. |
| `reopen` | Reopen Discord after patching. |
| `download` | Download or refresh `betterdiscord.asar`. |
| `force_download` | Ignore the cached ETag and download again. |
| `wait_update` | Wait for Discord's updater to finish before patching. |
| `dry_run` | Show actions without writing files. |
| `verbose` | Show more detailed logs. |
| `discord_data` | Discord data folder to patch. |
| `bd_asar` | Destination for `betterdiscord.asar`. |

## Notes

The script finds Discord's current `discord_desktop_core`, writes the
BetterDiscord loader to `index.js`, and downloads `betterdiscord.asar` with
ETag caching.
