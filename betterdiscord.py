#!/usr/bin/env python3
import argparse
import json
import logging
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

LOG = logging.getLogger("betterdiscord")

HOME = Path.home()
BD_ASAR_URL = "https://github.com/rauenzi/BetterDiscordApp/releases/latest/download/betterdiscord.asar"
APP_NAME = "BetterDiscordPatcher"
SCRIPT_VERSION = "2.1.2"
REPO = "ctrlcmdshft/BetterDiscordPatcher"
BRANCH = "main"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
SUPPORTED_SYSTEMS = {"Darwin", "Windows"}
WINDOWS_RELEASE_DIRS = {
    "stable": "Discord",
    "ptb": "DiscordPTB",
    "canary": "DiscordCanary",
}
MAC_RELEASE_DIRS = {
    "stable": "discord",
    "ptb": "discordptb",
    "canary": "discordcanary",
}
RELEASE_ORDER = ("stable", "ptb", "canary")


def env_path(name: str, fallback: Path) -> Path:
    value = os.environ.get(name)
    return Path(value) if value else fallback


def default_discord_data(release: str = "stable") -> Path:
    system = platform.system()
    if system == "Windows":
        return env_path("LOCALAPPDATA", HOME / "AppData/Local") / WINDOWS_RELEASE_DIRS[release]
    return HOME / "Library/Application Support" / MAC_RELEASE_DIRS[release]


def default_bd_asar() -> Path:
    system = platform.system()
    if system == "Windows":
        return env_path("APPDATA", HOME / "AppData/Roaming") / "BetterDiscord/data/betterdiscord.asar"
    return HOME / "Library/Application Support/BetterDiscord/data/betterdiscord.asar"


def default_config_path() -> Path:
    system = platform.system()
    if system == "Windows":
        return env_path("APPDATA", HOME / "AppData/Roaming") / f"{APP_NAME}/config.json"
    return HOME / ".config/betterdiscord-patcher/config.json"


def default_install_dir() -> Path:
    system = platform.system()
    if system == "Windows":
        return env_path("LOCALAPPDATA", HOME / "AppData/Local") / APP_NAME
    return HOME / f"Library/Application Support/{APP_NAME}"


def default_bin_path() -> Path:
    system = platform.system()
    if system == "Windows":
        return default_install_dir() / "betterdiscord.cmd"
    return HOME / ".local/bin/betterdiscord"


DISCORD_DATA = default_discord_data()
DISCORD_APP = Path("/Applications/Discord.app")
BD_ASAR = default_bd_asar()
CONFIG_PATH = default_config_path()
INSTALL_DIR = default_install_dir()
BIN_PATH = default_bin_path()
CONFIG_TEMPLATE = {
    "release": "stable",
    "notify": False,
    "keep_open": False,
    "reopen": True,
    "download": True,
    "force_download": False,
    "wait_update": True,
    "cleanup_before_install": True,
    "keep_versions": 1,
    "dry_run": False,
    "verbose": False,
    "discord_data": DISCORD_DATA,
    "bd_asar": BD_ASAR,
}


@dataclass(frozen=True)
class DiscordRelease:
    key: str
    name: str
    app_name: str
    bundle_id: str
    app_path: Path
    data_path: Path
    shipit_state: Path


DISCORD_RELEASES = {
    "stable": DiscordRelease(
        key="stable",
        name="Discord",
        app_name="Discord",
        bundle_id="com.hnc.Discord",
        app_path=Path("/Applications/Discord.app"),
        data_path=HOME / "Library/Application Support/discord",
        shipit_state=HOME / "Library/Caches/com.hnc.Discord.ShipIt/ShipItState.plist",
    ),
    "ptb": DiscordRelease(
        key="ptb",
        name="Discord PTB",
        app_name="Discord PTB",
        bundle_id="com.hnc.DiscordPTB",
        app_path=Path("/Applications/Discord PTB.app"),
        data_path=HOME / "Library/Application Support/discordptb",
        shipit_state=HOME / "Library/Caches/com.hnc.DiscordPTB.ShipIt/ShipItState.plist",
    ),
    "canary": DiscordRelease(
        key="canary",
        name="Discord Canary",
        app_name="Discord Canary",
        bundle_id="com.hnc.DiscordCanary",
        app_path=Path("/Applications/Discord Canary.app"),
        data_path=HOME / "Library/Application Support/discordcanary",
        shipit_state=HOME / "Library/Caches/com.hnc.DiscordCanary.ShipIt/ShipItState.plist",
    ),
    "development": DiscordRelease(
        key="development",
        name="Discord Development",
        app_name="Discord Development",
        bundle_id="com.hnc.DiscordDevelopment",
        app_path=Path("/Applications/Discord Development.app"),
        data_path=HOME / "Library/Application Support/discorddevelopment",
        shipit_state=HOME / "Library/Caches/com.hnc.DiscordDevelopment.ShipIt/ShipItState.plist",
    ),
}

INJECTION = """\
// BetterDiscord's Injection Script
const path = require("path");
const electron = require("electron");

let userConfig = path.join(electron.app.getPath("userData"), "..");

if (process.platform !== "win32" && process.platform !== "darwin") {
    userConfig = process.env.XDG_CONFIG_HOME || path.join(process.env.HOME, ".config");
    if (process.env.HOST_XDG_CONFIG_HOME) userConfig = process.env.HOST_XDG_CONFIG_HOME;
}

require(path.join(userConfig, "BetterDiscord", "data", "betterdiscord.asar"));

module.exports = require("./core.asar");
"""


@dataclass
class Options:
    release: str
    discord_data: Path
    bd_asar: Path
    notify: bool
    restart: bool
    reopen: bool
    download: bool
    force_download: bool
    wait_update: bool
    cleanup_before_install: bool
    keep_versions: int
    dry_run: bool


def main() -> int:
    args = parse_args()
    args.target_discord_data = resolve_target_discord_data(args)
    args.discord_data = args.target_discord_data[0]
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s" if args.verbose else "%(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    if platform.system() not in SUPPORTED_SYSTEMS:
        LOG.error("This installer currently supports macOS and Windows only.")
        return 1

    if should_check_for_script_update(args):
        if maybe_handle_script_update(args.raw_base, args.update_dir.expanduser()):
            return 0

    if args.check_update:
        return 0 if report_script_update_status(args.raw_base) else 1

    if args.init_config:
        write_config(args.config, overwrite=args.force)
        return 0

    if args.format_config:
        format_config(args.config)
        return 0

    if args.edit_config:
        edit_config(args.config)
        return 0

    if args.show_config:
        print(json.dumps(options_dict(args), indent=2))
        return 0

    if args.update:
        update_script(args.update_dir.expanduser(), args.raw_base)
        return 0

    if args.unpatch:
        try:
            for discord_data in args.target_discord_data:
                unpatch_discord(
                    discord_data,
                    restart=not args.keep_open,
                    reopen=args.reopen,
                    dry_run=args.dry_run,
                )
        except Exception as error:
            LOG.error("Unpatch failed: %s", error)
            return 1
        return 0

    if args.cleanup_old:
        try:
            for discord_data in args.target_discord_data:
                cleanup_old_versions(discord_data, keep=args.keep_versions, dry_run=args.dry_run)
        except Exception as error:
            LOG.error("Cleanup failed: %s", error)
            return 1
        return 0

    if args.uninstall:
        uninstall_script(
            args.update_dir.expanduser(),
            args.bin_path.expanduser(),
            args.config.expanduser(),
            remove_config=args.remove_config,
            dry_run=args.dry_run,
        )
        return 0

    try:
        for discord_data in args.target_discord_data:
            options = Options(
                release=release_name_for_discord_data(discord_data),
                discord_data=discord_data,
                bd_asar=args.bd_asar.expanduser(),
                notify=args.notify,
                restart=not args.keep_open,
                reopen=args.reopen,
                download=args.download,
                force_download=args.force_download,
                wait_update=args.wait_update,
                cleanup_before_install=args.cleanup_before_install,
                keep_versions=args.keep_versions,
                dry_run=args.dry_run,
            )
            install(options)
        return 0
    except Exception as error:
        LOG.error("Install failed: %s", error)
        return 1


def parse_args() -> argparse.Namespace:
    pre_parser = argparse.ArgumentParser(add_help=False)
    pre_parser.add_argument("--config", type=Path, default=Path(os.environ.get("BD_CONFIG", CONFIG_PATH)))
    pre_args, _ = pre_parser.parse_known_args()

    defaults = merged_defaults(pre_args.config.expanduser())
    parser = argparse.ArgumentParser(description="Small BetterDiscord patcher script.")
    parser.set_defaults(**defaults)

    parser.add_argument("--config", type=Path, default=pre_args.config, help="config file path")
    parser.add_argument("--init-config", action="store_true", help="create a config file with current defaults")
    parser.add_argument("--format-config", action="store_true", help="rewrite the config file in the standard order")
    parser.add_argument("--edit-config", action="store_true", help="open the config file for editing")
    parser.add_argument("--show-config", action="store_true", help="print config values and exit")
    parser.add_argument("--check-update", action="store_true", help="check whether a newer script version is available")
    parser.add_argument("--update", action="store_true", help="update this installer script from GitHub")
    parser.add_argument("--uninstall", action="store_true", help="remove the installer script")
    parser.add_argument("--remove-config", action="store_true", help="also remove config with --uninstall")
    parser.add_argument("--unpatch", action="store_true", help="remove the BetterDiscord loader from Discord")
    parser.add_argument("--cleanup-old", action="store_true", help="remove old Discord app version folders")
    parser.add_argument(
        "--update-dir",
        type=Path,
        default=Path(os.environ.get("BDI_INSTALL_DIR", INSTALL_DIR)),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--bin-path",
        type=Path,
        default=Path(os.environ.get("BDI_BIN_PATH", BIN_PATH)),
        help=argparse.SUPPRESS,
    )
    parser.add_argument(
        "--raw-base",
        default=os.environ.get(
            "BDI_RAW_BASE",
            f"https://raw.githubusercontent.com/{os.environ.get('BDI_REPO', REPO)}/{os.environ.get('BDI_BRANCH', BRANCH)}",
        ),
        help=argparse.SUPPRESS,
    )
    parser.add_argument("--force", action="store_true", help="overwrite an existing config with --init-config")
    parser.add_argument("--version", action="version", version=f"%(prog)s {SCRIPT_VERSION}")

    release = parser.add_mutually_exclusive_group()
    release.add_argument("--stable", dest="release", action="store_const", const="stable", help="target Discord stable")
    release.add_argument("--ptb", dest="release", action="store_const", const="ptb", help="target Discord PTB")
    release.add_argument("--canary", dest="release", action="store_const", const="canary", help="target Discord Canary")
    release.add_argument("--all", dest="release", action="store_const", const="all", help="target every installed Discord release")
    release.add_argument("--auto", dest="release", action="store_const", const="auto", help="target the first installed Discord release")

    notify = parser.add_mutually_exclusive_group()
    notify.add_argument("--notify", dest="notify", action="store_true", help="enable macOS notifications")
    notify.add_argument("--no-notify", dest="notify", action="store_false", help="disable macOS notifications")

    open_mode = parser.add_mutually_exclusive_group()
    open_mode.add_argument("--restart", dest="keep_open", action="store_false", help="quit Discord before patching")
    open_mode.add_argument("--keep-open", dest="keep_open", action="store_true", help="patch without quitting Discord first")

    reopen = parser.add_mutually_exclusive_group()
    reopen.add_argument("--reopen", dest="reopen", action="store_true", help="reopen Discord after patching")
    reopen.add_argument("--no-reopen", dest="reopen", action="store_false", help="do not reopen Discord after patching")

    download = parser.add_mutually_exclusive_group()
    download.add_argument("--download", dest="download", action="store_true", help="download betterdiscord.asar")
    download.add_argument("--no-download", dest="download", action="store_false", help="skip downloading betterdiscord.asar")

    wait_update = parser.add_mutually_exclusive_group()
    wait_update.add_argument("--wait-update", dest="wait_update", action="store_true", help="wait for Discord ShipIt updates")
    wait_update.add_argument("--skip-update-wait", dest="wait_update", action="store_false", help="do not wait for Discord ShipIt updates")

    cleanup_install = parser.add_mutually_exclusive_group()
    cleanup_install.add_argument("--cleanup-before-install", dest="cleanup_before_install", action="store_true", help="remove old Discord app version folders before patching")
    cleanup_install.add_argument("--no-cleanup-before-install", dest="cleanup_before_install", action="store_false", help="keep old Discord app version folders before patching")

    parser.add_argument("--force-download", action="store_true", default=defaults["force_download"], help="download betterdiscord.asar even if cached")
    parser.add_argument("--dry-run", action="store_true", default=defaults["dry_run"], help="show what would change without writing files")
    parser.add_argument("--verbose", "-v", action="store_true", default=defaults["verbose"], help="show debug logs")
    parser.add_argument("--keep-versions", type=int, default=defaults["keep_versions"], help="number of Discord app versions to keep when cleaning old versions")
    parser.add_argument("--discord-data", type=Path, default=defaults["discord_data"], help="Discord data folder")
    parser.add_argument("--bd-asar", type=Path, default=defaults["bd_asar"], help="BetterDiscord asar output path")
    parser.set_defaults(release="stable")
    args = parser.parse_args()
    args.release_explicit = any(
        arg in {"--stable", "--ptb", "--canary", "--all", "--auto"}
        for arg in sys.argv[1:]
    )
    args.discord_data_explicit = any(
        arg == "--discord-data" or arg.startswith("--discord-data=")
        for arg in sys.argv[1:]
    )
    return args


def should_check_for_script_update(args: argparse.Namespace) -> bool:
    if args.update or args.init_config or args.format_config or args.edit_config or args.check_update:
        return False
    return True


def maybe_handle_script_update(raw_base: str, install_dir: Path) -> bool:
    latest_version = latest_script_version(raw_base)
    if not latest_version:
        return False
    if version_tuple(latest_version) > version_tuple(SCRIPT_VERSION):
        LOG.info(
            "Update available: %s (installed: %s). Run `betterdiscord --update`.",
            latest_version,
            SCRIPT_VERSION,
        )
        if sys.stdin.isatty() and confirm("Update now?", default=True):
            update_script(install_dir, raw_base)
            return True
    return False


def report_script_update_status(raw_base: str) -> bool:
    latest_version = latest_script_version(raw_base)
    if not latest_version:
        LOG.error("Could not determine the latest script version.")
        return False
    if version_tuple(latest_version) > version_tuple(SCRIPT_VERSION):
        LOG.info("Update available: %s (installed: %s)", latest_version, SCRIPT_VERSION)
        return True
    LOG.info("You are up to date: %s", SCRIPT_VERSION)
    return True


def latest_script_version(raw_base: str) -> Optional[str]:
    try:
        request = urllib.request.Request(
            f"{raw_base.rstrip('/')}/betterdiscord.py",
            headers={"User-Agent": f"{APP_NAME}/{SCRIPT_VERSION}"},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            content = response.read().decode("utf-8", errors="ignore")
    except Exception as error:
        LOG.debug("Could not check for script updates: %s", error)
        return None

    match = re.search(r'^SCRIPT_VERSION = "([^"]+)"$', content, re.MULTILINE)
    if not match:
        LOG.debug("Could not find SCRIPT_VERSION in remote script.")
        return None
    return match.group(1)


def version_tuple(value: str) -> tuple[int, ...]:
    parts = []
    for piece in value.split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            numbers = re.match(r"(\d+)", piece)
            parts.append(int(numbers.group(1)) if numbers else 0)
    return tuple(parts)


def resolve_target_discord_data(args: argparse.Namespace) -> list[Path]:
    if args.discord_data_explicit:
        return [args.discord_data.expanduser()]
    if not args.release_explicit and args.discord_data != built_in_defaults()["discord_data"]:
        return [args.discord_data.expanduser()]

    release = args.release
    if release == "all":
        targets = [default_discord_data(name) for name in RELEASE_ORDER if default_discord_data(name).exists()]
        if targets:
            return targets
        checked = ", ".join(str(default_discord_data(name)) for name in RELEASE_ORDER)
        raise FileNotFoundError(f"No installed Discord releases found. Checked: {checked}")
    if release == "auto":
        for name in RELEASE_ORDER:
            candidate = default_discord_data(name)
            if candidate.exists():
                args.release = name
                return [candidate]
        return [default_discord_data("stable")]
    return [default_discord_data(release)]


def built_in_defaults() -> dict:
    return CONFIG_TEMPLATE.copy()


def merged_defaults(config_path: Path) -> dict:
    defaults = built_in_defaults()
    defaults.update(read_config(config_path))
    return defaults


def read_config(path: Path) -> dict:
    if not path.exists():
        return {}
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        return {}
    data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError(f"Config must be a JSON object: {path}")

    result = {}
    bool_keys = {
        "notify",
        "keep_open",
        "reopen",
        "download",
        "force_download",
        "wait_update",
        "cleanup_before_install",
        "dry_run",
        "verbose",
    }
    path_keys = {"discord_data", "bd_asar"}
    for key, value in data.items():
        if key in bool_keys:
            if not isinstance(value, bool):
                raise ValueError(f"Config value must be true or false: {key}")
            result[key] = value
        elif key in path_keys:
            if not isinstance(value, str):
                raise ValueError(f"Config value must be a path string: {key}")
            result[key] = Path(value).expanduser()
        elif key == "keep_versions":
            if not isinstance(value, int) or value < 1:
                raise ValueError("Config keep_versions must be an integer of 1 or greater.")
            result[key] = value
        elif key == "release":
            if not isinstance(value, str):
                raise ValueError("Config release must be a string.")
        else:
            raise ValueError(f"Unknown config key: {key}")
    return result


def write_config(path: Path, overwrite: bool) -> None:
    path = path.expanduser()
    if path.exists() and not overwrite:
        raise FileExistsError(f"Config already exists: {path}. Use --force to overwrite.")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = options_dict(argparse.Namespace(**built_in_defaults()))
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    LOG.info("Wrote config: %s", path)


def format_config(path: Path) -> None:
    path = path.expanduser()
    defaults = merged_defaults(path)
    data = options_dict(argparse.Namespace(**defaults))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    LOG.info("Formatted config: %s", path)


def edit_config(path: Path) -> None:
    path = path.expanduser()
    if not path.exists():
        write_config(path, overwrite=False)
    else:
        format_config(path)

    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        subprocess.run([editor, str(path)], check=True)
        return
    if platform.system() == "Windows":
        os.startfile(path)  # type: ignore[attr-defined]
        return
    subprocess.run(["open", "-t", str(path)], check=True)


def options_dict(args: argparse.Namespace) -> dict:
    return {
        "discord_data": str(args.discord_data),
        "bd_asar": str(args.bd_asar),
        "download": args.download,
        "wait_update": args.wait_update,
        "cleanup_before_install": args.cleanup_before_install,
        "keep_versions": args.keep_versions,
        "keep_open": args.keep_open,
        "reopen": args.reopen,
        "notify": args.notify,
    }


def update_script(install_dir: Path, raw_base: str) -> None:
    LOG.info("Updating installer script from %s", raw_base)
    install_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("betterdiscord.py", "README.md", "install.sh", "install.ps1"):
        download_file(f"{raw_base.rstrip('/')}/{filename}", install_dir / filename)
    (install_dir / "betterdiscord").write_text(
        '#!/bin/zsh\nDIR="${0:A:h}"\npython3 "$DIR/betterdiscord.py" "$@"\n',
        encoding="utf-8",
    )
    (install_dir / "betterdiscord").chmod(0o755)
    (install_dir / "install.sh").chmod(0o755)
    if platform.system() == "Windows":
        (install_dir / "betterdiscord.cmd").write_text(
            f'@echo off\r\npython "{install_dir / "betterdiscord.py"}" %*\r\n',
            encoding="utf-8",
        )
    subprocess.run([sys.executable, "-m", "py_compile", str(install_dir / "betterdiscord.py")], check=True)
    LOG.info("Updated installer script: %s", install_dir)


def download_file(url: str, destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    LOG.info("Download %s", url)
    request = urllib.request.Request(url, headers={"User-Agent": "BetterDiscordPatcher/2.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        temporary.write_bytes(response.read())
    temporary.replace(destination)


def uninstall_script(
    install_dir: Path,
    bin_path: Path,
    config_path: Path,
    remove_config: bool,
    dry_run: bool,
) -> None:
    if not remove_config and config_path.exists():
        remove_config = confirm("Remove config too?", default=False)

    if platform.system() == "Windows":
        if dry_run:
            remove_path(bin_path, dry_run)
            remove_path(install_dir, dry_run)
            remove_windows_user_path_entry(bin_path.parent, dry_run)
            if remove_config:
                remove_path(config_path, dry_run)
            else:
                LOG.info("Keeping config: %s", config_path)
            return

        schedule_windows_uninstall(
            install_dir,
            bin_path,
            config_path,
            remove_config=remove_config,
        )
        LOG.info("Scheduled Windows uninstall cleanup.")
        return

    remove_path(bin_path, dry_run)
    remove_path(install_dir, dry_run)
    if remove_config:
        remove_path(config_path, dry_run)
        config_parent = config_path.parent
        if not dry_run and config_parent.exists() and not any(config_parent.iterdir()):
            config_parent.rmdir()
    else:
        LOG.info("Keeping config: %s", config_path)


def confirm(prompt: str, default: bool = False) -> bool:
    if not sys.stdin.isatty():
        return default
    suffix = "[Y/n]" if default else "[y/N]"
    try:
        answer = input(f"{prompt} {suffix} ").strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    return answer in {"y", "yes"}


def remove_path(path: Path, dry_run: bool) -> None:
    if not path.exists() and not path.is_symlink():
        LOG.info("Not found: %s", path)
        return
    LOG.info("%sRemove: %s", "[dry-run] " if dry_run else "", path)
    if dry_run:
        return
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def remove_windows_user_path_entry(path: Path, dry_run: bool) -> None:
    target = str(path.expanduser().resolve())
    current = os.environ.get("PATH", "")
    try:
        stored = os.environ.get("PATH", "")
        user_path = stored
        if platform.system() == "Windows":
            result = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    '[Environment]::GetEnvironmentVariable("Path", "User")',
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                user_path = result.stdout.strip()
    except Exception as error:
        LOG.debug("Could not read Windows user PATH: %s", error)
        user_path = current

    entries = [entry for entry in user_path.split(";") if entry.strip()]
    kept = []
    removed = False
    for entry in entries:
        try:
            normalized = str(Path(entry).expanduser().resolve())
        except Exception:
            normalized = os.path.normcase(os.path.normpath(entry))
        if os.path.normcase(normalized) == os.path.normcase(target):
            removed = True
            continue
        kept.append(entry)

    if not removed:
        LOG.info("PATH entry not found: %s", path)
        return

    LOG.info("%sRemove from user PATH: %s", "[dry-run] " if dry_run else "", path)
    if dry_run:
        return
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            'param([string]$value) [Environment]::SetEnvironmentVariable("Path", $value, "User")',
            ";".join(kept),
        ],
        check=False,
    )


def schedule_windows_uninstall(
    install_dir: Path,
    bin_path: Path,
    config_path: Path,
    remove_config: bool,
) -> None:
    helper_path = Path(tempfile.gettempdir()) / f"betterdiscord-uninstall-{os.getpid()}.ps1"
    helper_path.write_text(
        """\
param(
    [int]$ParentPid,
    [string]$InstallDir,
    [string]$BinPath,
    [string]$ConfigPath,
    [string]$PathEntry,
    [int]$RemoveConfig
)

while (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) {
    Start-Sleep -Milliseconds 250
}

function Remove-PathIfExists {
    param([string]$Target)
    if (Test-Path -LiteralPath $Target) {
        Remove-Item -LiteralPath $Target -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$entries = @()
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (-not [string]::IsNullOrWhiteSpace($currentPath)) {
    $entries = $currentPath.Split(";", [System.StringSplitOptions]::RemoveEmptyEntries) |
        Where-Object {
            -not [string]::Equals(
                [System.IO.Path]::GetFullPath($_),
                [System.IO.Path]::GetFullPath($PathEntry),
                [System.StringComparison]::OrdinalIgnoreCase
            )
        }
}
[Environment]::SetEnvironmentVariable("Path", ($entries -join ";"), "User")

Remove-PathIfExists $BinPath
Remove-PathIfExists $InstallDir

if ($RemoveConfig -ne 0) {
    Remove-PathIfExists $ConfigPath
    $configParent = Split-Path -Parent $ConfigPath
    if ((Test-Path -LiteralPath $configParent) -and -not (Get-ChildItem -LiteralPath $configParent -Force -ErrorAction SilentlyContinue)) {
        Remove-Item -LiteralPath $configParent -Force -ErrorAction SilentlyContinue
    }
}

Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
""",
        encoding="utf-8",
    )
    subprocess.Popen(
        [
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-WindowStyle",
            "Hidden",
            "-File",
            str(helper_path),
            "-ParentPid",
            str(os.getpid()),
            "-InstallDir",
            str(install_dir),
            "-BinPath",
            str(bin_path),
            "-ConfigPath",
            str(config_path),
            "-PathEntry",
            str(bin_path.parent),
            "-RemoveConfig",
            "1" if remove_config else "0",
        ],
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def cleanup_old_versions(discord_data: Path, keep: int, dry_run: bool) -> list[Path]:
    if keep < 1:
        raise ValueError("--keep-versions must be 1 or greater")

    versions = discord_version_dirs(discord_data)
    cleanup_candidates = [path for path in versions if path.name.startswith("app-")]
    kept = cleanup_candidates[-keep:]
    removable = [path for path in cleanup_candidates if path not in kept]
    preserved = [path for path in versions if path not in removable]

    LOG.info("Discord app-* versions found: %d", len(cleanup_candidates))
    if kept:
        LOG.info("Keeping: %s", ", ".join(path.name for path in kept))
    if not removable:
        LOG.info("No old Discord app version folders to remove.")
        return preserved

    for version_dir in removable:
        remove_path(version_dir, dry_run)
    return preserved


def unpatch_discord(discord_data: Path, restart: bool, reopen: bool, dry_run: bool) -> None:
    index_paths = discord_core_index_paths(discord_data)
    restored_script = 'module.exports = require("./core.asar");\n'
    patched_paths = []

    for index_js in index_paths:
        if not index_js.exists():
            continue
        content = index_js.read_text(encoding="utf-8", errors="ignore")
        if "betterdiscord" in content.lower():
            patched_paths.append(index_js)

    if not patched_paths:
        LOG.info("No BetterDiscord patch found under %s", discord_data)
        return

    was_running = restart and discord_running(discord_data)
    if was_running and restart and not dry_run:
        quit_discord(discord_data)

    try:
        for index_js in patched_paths:
            LOG.info("%sRestore: %s", "[dry-run] " if dry_run else "", index_js)
            if not dry_run:
                index_js.write_text(restored_script, encoding="utf-8")
    finally:
        if was_running and restart and reopen and not dry_run:
            open_discord(discord_data)


def install(options: Options) -> None:
    LOG.info("BetterDiscord installer script v%s", SCRIPT_VERSION)
    LOG.info("Release: %s", options.release)
    LOG.info("Discord data: %s", options.discord_data)
    LOG.info("BetterDiscord asar: %s", options.bd_asar)
    notify("BetterDiscord", "Preparing installation", options.notify)

    if options.download:
        download_asar(options.bd_asar, force=options.force_download, dry_run=options.dry_run)

    version_dirs = None
    if options.cleanup_before_install:
        version_dirs = cleanup_old_versions(
            options.discord_data,
            keep=options.keep_versions,
            dry_run=options.dry_run,
        )

    version_dir = latest_version_dir(options.discord_data, version_dirs=version_dirs)
    core_dirs = discord_core_dirs(options.discord_data, version_dirs=version_dirs)
    LOG.info("Latest Discord version: %s", version_dir.name)
    LOG.info("Discord cores found: %d", len(core_dirs))

    was_running = discord_running(options.discord_data)
    if was_running and options.restart and not options.dry_run:
        quit_discord(options.discord_data)

    try:
        if options.download:
            download_asar(options.bd_asar, force=options.force_download, dry_run=options.dry_run)
        changed = 0
        for core_dir in core_dirs:
            if patch_core(core_dir, dry_run=options.dry_run):
                changed += 1
        LOG.info("Discord cores patched: %d", changed)
        log_discord_app_version()
    finally:
        if was_running and options.restart and options.reopen and not options.dry_run:
            open_discord(options.discord_data)

    notify("BetterDiscord", "Installation complete", options.notify)


def latest_version_dir(discord_data: Path, version_dirs: Optional[list[Path]] = None) -> Path:
    return (version_dirs or discord_version_dirs(discord_data))[-1]


def release_name_for_discord_data(discord_data: Path) -> str:
    if platform.system() == "Windows":
        name = discord_data.name.lower()
        for release, dirname in WINDOWS_RELEASE_DIRS.items():
            if dirname.lower() == name:
                return release
        return "custom"

    name = discord_data.name.lower()
    for release, dirname in MAC_RELEASE_DIRS.items():
        if dirname.lower() == name:
            return release
    return "custom"


def windows_process_name(discord_data: Path) -> str:
    release = release_name_for_discord_data(discord_data)
    if release == "ptb":
        return "DiscordPTB.exe"
    if release == "canary":
        return "DiscordCanary.exe"
    return "Discord.exe"


def discord_version_dirs(discord_data: Path) -> list[Path]:
    if not discord_data.exists():
        raise FileNotFoundError(f"Discord data folder not found: {discord_data}")
    try:
        versions = sorted((p for p in discord_data.iterdir() if version_key(p)), key=version_key)
    except PermissionError as error:
        raise PermissionError(f"Cannot read Discord data folder: {discord_data}") from error
    if not versions:
        raise FileNotFoundError(f"No Discord version folders found in {discord_data}")
    return versions


def version_key(path: Path) -> tuple[int, ...]:
    name = path.name
    prefix = 1 if name.startswith("app-") else 0
    if prefix:
        name = name[4:]
    return (prefix,) + tuple(int(p) for p in name.split(".")) if name.replace(".", "").isdigit() else ()


def core_key(path: Path) -> tuple[int, int]:
    if path.name == "discord_desktop_core":
        return (0, 0)
    suffix = path.name.removeprefix("discord_desktop_core-")
    return (1, int(suffix)) if suffix.isdigit() else (0, 0)


def find_core_dir(version_dir: Path) -> Path:
    modules = version_dir / "modules"
    candidates = [modules / "discord_desktop_core"]

    if modules.exists():
        wrappers = sorted(
            (p for p in modules.iterdir() if p.is_dir() and p.name.startswith("discord_desktop_core")),
            key=core_key,
            reverse=True,
        )
        for wrapper in wrappers:
            candidates.extend((wrapper / "discord_desktop_core", wrapper))

    for candidate in candidates:
        if (candidate / "core.asar").exists():
            return candidate

    for core_asar in sorted(version_dir.rglob("core.asar")):
        if "discord_desktop_core" in str(core_asar):
            return core_asar.parent

    found = []
    if modules.exists():
        found = [str(p) for p in sorted(modules.rglob("*")) if "discord_desktop_core" in str(p)]
    raise FileNotFoundError(
        "No Discord desktop-core core.asar found.\n"
        f"Searched:\n        {join_paths(candidates)}\n"
        f"Found desktop-core paths:\n        {join_paths(found[:50])}"
    )


def discord_core_dirs(discord_data: Path, version_dirs: Optional[list[Path]] = None) -> list[Path]:
    version_dirs = version_dirs or discord_version_dirs(discord_data)
    core_dirs = []
    seen = set()
    for version_dir in version_dirs:
        modules = version_dir / "modules"
        if not modules.exists():
            continue
        for core_asar in sorted(modules.rglob("core.asar")):
            if "discord_desktop_core" not in str(core_asar):
                continue
            core_dir = core_asar.parent
            if core_dir not in seen:
                seen.add(core_dir)
                core_dirs.append(core_dir)

    if not core_dirs:
        raise FileNotFoundError(f"No Discord desktop-core folders found under {discord_data}")
    return core_dirs


def discord_core_index_paths(discord_data: Path) -> list[Path]:
    return [core_dir / "index.js" for core_dir in discord_core_dirs(discord_data)]


def patch_core(core_dir: Path, dry_run: bool) -> bool:
    index_js = core_dir / "index.js"
    if index_js.exists() and "betterdiscord" in index_js.read_text(encoding="utf-8", errors="ignore").lower():
        LOG.info("Already patched: %s", index_js)
        return False
    LOG.info("%sPatch: %s", "[dry-run] " if dry_run else "", index_js)
    if not dry_run:
        index_js.write_text(INJECTION, encoding="utf-8")
    return True


def download_asar(path: Path, force: bool, dry_run: bool) -> bool:
    etag_path = path.with_suffix(".etag")
    request = urllib.request.Request(BD_ASAR_URL, headers={"User-Agent": "BetterDiscordPatcher/2.0"})
    if path.exists() and etag_path.exists() and not force:
        request.add_header("If-None-Match", etag_path.read_text(encoding="utf-8").strip())

    LOG.info("%sDownload BetterDiscord asar", "[dry-run] " if dry_run else "")
    if dry_run:
        return False

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
            etag = response.headers.get("ETag")
    except urllib.error.HTTPError as error:
        if error.code == 304:
            LOG.info("BetterDiscord asar is already up to date.")
            return False
        raise

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if etag:
        etag_path.write_text(etag, encoding="utf-8")
    LOG.info("Saved %d KB to %s", len(data) // 1024, path)
    return True


def discord_update_dir() -> Optional[Path]:
    if platform.system() == "Windows":
        return None
    state = HOME / "Library/Caches/com.hnc.Discord.ShipIt/ShipItState.plist"
    try:
        with state.open("rb") as file:
            url = plistlib.load(file).get("updateBundleURL", "")
    except FileNotFoundError:
        return None
    if url.startswith("file://"):
        url = url[7:-13]
    return Path(url) if url else None


def wait_for_update(release: DiscordRelease, update_dir: Optional[Path], timeout: float = 180.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not shipit_running(release) and (update_dir is None or not update_dir.exists()):
            return True
        LOG.info("Waiting for %s updater...", release.name)
        time.sleep(2)
    return False


def discord_running(discord_data: Optional[Path] = None) -> bool:
    if platform.system() == "Windows":
        process_name = windows_process_name(discord_data or DISCORD_DATA)
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
            capture_output=True,
            text=True,
            check=False,
        )
        return process_name in result.stdout
    return subprocess.run(["pgrep", "-x", "Discord"], capture_output=True).returncode == 0


def shipit_running() -> bool:
    if platform.system() == "Windows":
        return False
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
    return any("ShipIt" in line and release.name in line for line in result.stdout.splitlines())


def quit_discord(discord_data: Optional[Path] = None) -> None:
    LOG.info("Quitting Discord")
    if platform.system() == "Windows":
        target = discord_data or DISCORD_DATA
        process_name = windows_process_name(target)
        subprocess.run(["taskkill", "/IM", process_name, "/T", "/F"], check=False, capture_output=True)
        deadline = time.time() + 15
        while time.time() < deadline and discord_running(target):
            time.sleep(0.25)
        return
    subprocess.run(["osascript", "-e", 'quit app "Discord"'], check=False)
    deadline = time.time() + 10
    while time.time() < deadline and discord_running(release):
        time.sleep(0.25)


def open_discord(discord_data: Optional[Path] = None) -> None:
    LOG.info("Reopening Discord")
    if platform.system() == "Windows":
        target = discord_data or DISCORD_DATA
        process_name = windows_process_name(target)
        update_exe = target / "Update.exe"
        if update_exe.exists():
            subprocess.run(
                [str(update_exe), "--processStart", process_name],
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return

        version_dir = latest_version_dir(target)
        discord_exe = version_dir / process_name
        if discord_exe.exists():
            subprocess.run(
                [str(discord_exe)],
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return

        LOG.warning("Could not find a Windows Discord executable to reopen.")
        return
    subprocess.run(["open", "-a", "Discord"], check=False)


def log_discord_app_version() -> None:
    if platform.system() == "Windows":
        return
    try:
        with (release.app_path / "Contents/Info.plist").open("rb") as file:
            version = plistlib.load(file).get("CFBundleShortVersionString")
            return str(version) if version else None
    except Exception as error:
        LOG.debug("Could not read %s app version: %s", release.name, error)
        return None


def notify(title: str, message: str, enabled: bool) -> None:
    if not enabled:
        return
    if platform.system() == "Windows":
        return
    script = f'display notification "{escape_osa(message)}" with title "{escape_osa(title)}"'
    subprocess.run(["osascript", "-e", script], check=False)


def escape_osa(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def join_paths(paths) -> str:
    return "\n        ".join(str(path) for path in paths) if paths else "(none)"


if __name__ == "__main__":
    sys.exit(main())
