# BetterDiscordCLIInstaller

Small macOS BetterDiscord installer.

One-line install:

```sh
curl -fsSL https://raw.githubusercontent.com/ctrlcmdshft/BetterDiscordCLIInstaller/main/install.sh | sh
```

By default this installs files to:

```text
~/Library/Application Support/BetterDiscordCLIInstaller
~/.local/bin/betterdiscord
~/.config/betterdiscord-cli-installer/config.json
```

During install, the config file is created if missing. The installer will ask
whether to open it for editing. You can force that behavior with:

```sh
BDI_EDIT_CONFIG=1 curl -fsSL https://raw.githubusercontent.com/ctrlcmdshft/BetterDiscordCLIInstaller/main/install.sh | sh
```

Run:

```sh
betterdiscord
```

Useful options:

```sh
--init-config      Create the user config file
--edit-config      Open the user config file for editing
--show-config      Print the effective settings
--no-notify         Disable macOS notifications
--keep-open         Patch without quitting Discord first
--no-reopen         Quit Discord for patching but do not reopen it
--no-download       Skip downloading betterdiscord.asar
--force-download    Ignore the cached ETag and download again
--dry-run           Show what would change without writing files
--verbose           Show debug logs
```

Persistent config:

```sh
betterdiscord --init-config
betterdiscord --edit-config
```

This creates:

```text
~/.config/betterdiscord-cli-installer/config.json
```

Edit that file to set normal behavior:

```json
{
  "download": true,
  "dry_run": false,
  "force_download": false,
  "keep_open": false,
  "notify": false,
  "reopen": true,
  "verbose": false,
  "wait_update": true,
  "discord_data": "~/Library/Application Support/discord",
  "bd_asar": "~/Library/Application Support/BetterDiscord/data/betterdiscord.asar"
}
```

Settings are applied in this order:

```text
defaults < config file < command-line options
```

Use `--config` to load a different config file:

```sh
betterdiscord --config ~/path/to/config.json --show-config
```

The same path can also be supplied with `BD_CONFIG` for scripts that need it.

The installer finds Discord's current `discord_desktop_core` by locating
`core.asar`, then writes `index.js` beside it using BetterDiscord's injection
script.
