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
built-in defaults < config file < environment variables < command-line options
```

Environment overrides are also supported:

```sh
BD_NOTIFY=0 betterdiscord
BD_KEEP_OPEN=1 betterdiscord
BD_REOPEN=0 betterdiscord
BD_DOWNLOAD=0 betterdiscord
BD_FORCE_DOWNLOAD=1 betterdiscord
BD_WAIT_UPDATE=0 betterdiscord
BD_DRY_RUN=1 betterdiscord
BD_VERBOSE=1 betterdiscord
BD_DISCORD_DATA=/path/to/discord betterdiscord
BD_ASAR=/path/to/betterdiscord.asar betterdiscord
```

The installer finds Discord's current `discord_desktop_core` by locating
`core.asar`, then writes `index.js` beside it using BetterDiscord's injection
script.
