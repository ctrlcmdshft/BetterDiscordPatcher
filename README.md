# BetterDiscordCLIInstaller

Small macOS command-line installer for BetterDiscord.

## Install

```sh
curl -fsSL https://raw.githubusercontent.com/ctrlcmdshft/BetterDiscordCLIInstaller/main/install.sh | sh
```

Installs to:

```text
~/Library/Application Support/BetterDiscordCLIInstaller
~/.local/bin/betterdiscord
~/.config/betterdiscord-cli-installer/config.json
```

The install script creates the config file if needed and asks whether to open it.
To open config automatically during install:

```sh
BDI_EDIT_CONFIG=1 curl -fsSL https://raw.githubusercontent.com/ctrlcmdshft/BetterDiscordCLIInstaller/main/install.sh | sh
```

If `betterdiscord` is not found after install, add this to your shell profile:

```sh
export PATH="$HOME/.local/bin:$PATH"
```

## Use

```sh
betterdiscord
```

Common commands:

```sh
betterdiscord --edit-config
betterdiscord --show-config
betterdiscord --dry-run
betterdiscord --update
betterdiscord --unpatch
betterdiscord --uninstall
```

Useful options:

```text
--no-notify         Disable macOS notifications
--keep-open         Patch without quitting Discord first
--no-reopen         Quit Discord for patching but do not reopen it
--no-download       Skip downloading betterdiscord.asar
--force-download    Ignore the cached ETag and download again
--verbose           Show debug logs
```

## Config

Persistent settings live at:

```text
~/.config/betterdiscord-cli-installer/config.json
```

Settings are applied in this order:

```text
defaults < config file < command-line options
```

Use a different config file:

```sh
betterdiscord --config ~/path/to/config.json --show-config
```

## Remove

Remove BetterDiscord from Discord:

```sh
betterdiscord --unpatch
```

Remove this installer:

```sh
betterdiscord --uninstall
```

`--uninstall` asks whether to remove config if one exists. To remove the config
without prompting:

```sh
betterdiscord --uninstall --remove-config
```

## How It Works

The script finds Discord's current `discord_desktop_core` by locating
`core.asar`, writes `index.js` beside it, and downloads
`betterdiscord.asar` with ETag caching.
