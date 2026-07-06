# BetterDiscordPatcher

Small macOS script that patches Discord to load BetterDiscord.

Supports Stable, PTB, Canary, and Development app detection.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/ctrlcmdshft/BetterDiscordPatcher/main/install.sh | sh
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
betterdiscord --format-config
betterdiscord --dry-run
betterdiscord --release canary
betterdiscord --update
betterdiscord --unpatch
betterdiscord --cleanup-old --dry-run
betterdiscord --no-cleanup-before-install
betterdiscord --uninstall
betterdiscord --help
```

Remove old Discord `app-*` folders after previewing. Cleanup keeps the newest
`app-*` folder and protects the version matching the installed Discord app.

```sh
betterdiscord --cleanup-old --dry-run
betterdiscord --cleanup-old
```

## Config

Config lives at:

```text
~/.config/betterdiscord-patcher/config.json
```

Command-line options override config values.

Config keys:

| Key | Meaning |
| --- | --- |
| `release` | Discord release to patch: `stable`, `auto`, `all`, `ptb`, `canary`, or `development`. |
| `notify` | Show macOS notifications. |
| `keep_open` | Patch without quitting Discord first. |
| `reopen` | Reopen Discord after patching. |
| `download` | Download or refresh `betterdiscord.asar`. |
| `wait_update` | Wait for Discord's updater to finish before patching. |
| `cleanup_before_install` | Remove old Discord `app-*` folders before patching. |
| `keep_versions` | Number of Discord `app-*` versions to keep when cleaning. |
| `discord_data` | Discord data folder to patch. |
| `bd_asar` | Destination for `betterdiscord.asar`. |

## Notes

The script can remove old Discord `app-*` folders, finds Discord's current
`discord_desktop_core` folders, writes the BetterDiscord loader to `index.js`,
and downloads `betterdiscord.asar` with ETag caching.
