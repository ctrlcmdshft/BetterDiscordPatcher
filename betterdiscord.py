#!/usr/bin/env python3
import argparse
import json
import logging
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

LOG = logging.getLogger("betterdiscord")

HOME = Path.home()
DISCORD_DATA = HOME / "Library/Application Support/discord"
DISCORD_APP = Path("/Applications/Discord.app")
BD_ASAR = HOME / "Library/Application Support/BetterDiscord/data/betterdiscord.asar"
BD_ASAR_URL = "https://github.com/rauenzi/BetterDiscordApp/releases/latest/download/betterdiscord.asar"
CONFIG_PATH = HOME / ".config/betterdiscord-cli-installer/config.json"
APP_NAME = "BetterDiscordCLIInstaller"
INSTALL_DIR = HOME / f"Library/Application Support/{APP_NAME}"
BIN_PATH = HOME / ".local/bin/betterdiscord"
REPO = "ctrlcmdshft/BetterDiscordCLIInstaller"
BRANCH = "main"
RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}"
CONFIG_TEMPLATE = {
    "notify": False,
    "keep_open": False,
    "reopen": True,
    "download": True,
    "force_download": False,
    "wait_update": True,
    "dry_run": False,
    "verbose": False,
    "discord_data": DISCORD_DATA,
    "bd_asar": BD_ASAR,
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
    discord_data: Path
    bd_asar: Path
    notify: bool
    restart: bool
    reopen: bool
    download: bool
    force_download: bool
    wait_update: bool
    dry_run: bool


def main() -> int:
    args = parse_args()
    logging.basicConfig(
        format="%(asctime)s %(levelname)s: %(message)s" if args.verbose else "%(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    if platform.system() != "Darwin":
        LOG.error("This installer currently supports macOS only.")
        return 1

    if args.init_config:
        write_config(args.config, overwrite=args.force)
        return 0

    if args.edit_config:
        edit_config(args.config)
        return 0

    if args.show_config:
        print(json.dumps(options_dict(args), indent=2, sort_keys=True))
        return 0

    if args.update:
        update_script(args.update_dir.expanduser(), args.raw_base)
        return 0

    if args.unpatch:
        unpatch_discord(args.discord_data.expanduser(), dry_run=args.dry_run)
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

    options = Options(
        discord_data=args.discord_data.expanduser(),
        bd_asar=args.bd_asar.expanduser(),
        notify=args.notify,
        restart=not args.keep_open,
        reopen=args.reopen,
        download=args.download,
        force_download=args.force_download,
        wait_update=args.wait_update,
        dry_run=args.dry_run,
    )

    try:
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
    parser = argparse.ArgumentParser(description="Small macOS BetterDiscord installer script.")
    parser.set_defaults(**defaults)

    parser.add_argument("--config", type=Path, default=pre_args.config, help="config file path")
    parser.add_argument("--init-config", action="store_true", help="create a config file with current defaults")
    parser.add_argument("--edit-config", action="store_true", help="open the config file for editing")
    parser.add_argument("--show-config", action="store_true", help="print effective settings and exit")
    parser.add_argument("--update", action="store_true", help="update this installer script from GitHub")
    parser.add_argument("--uninstall", action="store_true", help="remove the installer script")
    parser.add_argument("--remove-config", action="store_true", help="also remove config with --uninstall")
    parser.add_argument("--unpatch", action="store_true", help="remove BetterDiscord from Discord")
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

    parser.add_argument("--force-download", action="store_true", default=defaults["force_download"], help="download betterdiscord.asar even if cached")
    parser.add_argument("--dry-run", action="store_true", default=defaults["dry_run"], help="show what would change without writing files")
    parser.add_argument("--verbose", "-v", action="store_true", default=defaults["verbose"], help="show debug logs")
    parser.add_argument("--discord-data", type=Path, default=defaults["discord_data"], help="Discord data folder")
    parser.add_argument("--bd-asar", type=Path, default=defaults["bd_asar"], help="BetterDiscord asar output path")
    return parser.parse_args()


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
    bool_keys = {"notify", "keep_open", "reopen", "download", "force_download", "wait_update", "dry_run", "verbose"}
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
        else:
            raise ValueError(f"Unknown config key: {key}")
    return result


def write_config(path: Path, overwrite: bool) -> None:
    path = path.expanduser()
    if path.exists() and not overwrite:
        raise FileExistsError(f"Config already exists: {path}. Use --force to overwrite.")
    path.parent.mkdir(parents=True, exist_ok=True)
    data = options_dict(argparse.Namespace(**built_in_defaults()))
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    LOG.info("Wrote config: %s", path)


def edit_config(path: Path) -> None:
    path = path.expanduser()
    if not path.exists():
        write_config(path, overwrite=False)

    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        subprocess.run([editor, str(path)], check=True)
        return
    subprocess.run(["open", "-t", str(path)], check=True)


def options_dict(args: argparse.Namespace) -> dict:
    return {
        "bd_asar": str(args.bd_asar),
        "discord_data": str(args.discord_data),
        "download": args.download,
        "dry_run": args.dry_run,
        "force_download": args.force_download,
        "keep_open": args.keep_open,
        "notify": args.notify,
        "reopen": args.reopen,
        "verbose": args.verbose,
        "wait_update": args.wait_update,
    }


def update_script(install_dir: Path, raw_base: str) -> None:
    LOG.info("Updating installer script from %s", raw_base)
    install_dir.mkdir(parents=True, exist_ok=True)
    for filename in ("betterdiscord.py", "README.md", "install.sh"):
        download_file(f"{raw_base.rstrip('/')}/{filename}", install_dir / filename)
    (install_dir / "betterdiscord").write_text(
        '#!/bin/zsh\nDIR="${0:A:h}"\npython3 "$DIR/betterdiscord.py" "$@"\n',
        encoding="utf-8",
    )
    (install_dir / "betterdiscord").chmod(0o755)
    (install_dir / "install.sh").chmod(0o755)
    subprocess.run([sys.executable, "-m", "py_compile", str(install_dir / "betterdiscord.py")], check=True)
    LOG.info("Updated installer script: %s", install_dir)


def download_file(url: str, destination: Path) -> None:
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    LOG.info("Download %s", url)
    request = urllib.request.Request(url, headers={"User-Agent": "BetterDiscordInstaller/2.0"})
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
    remove_path(bin_path, dry_run)
    remove_path(install_dir, dry_run)
    if remove_config:
        remove_path(config_path, dry_run)
        config_parent = config_path.parent
        if not dry_run and config_parent.exists() and not any(config_parent.iterdir()):
            config_parent.rmdir()
    else:
        LOG.info("Keeping config: %s", config_path)


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


def unpatch_discord(discord_data: Path, dry_run: bool) -> None:
    version_dir = latest_version_dir(discord_data)
    core_dir = find_core_dir(version_dir)
    index_js = core_dir / "index.js"
    restored_script = 'module.exports = require("./core.asar");\n'
    if index_js.exists():
        content = index_js.read_text(encoding="utf-8", errors="ignore")
        if "betterdiscord" not in content.lower():
            LOG.info("No BetterDiscord patch found: %s", index_js)
            return
    LOG.info("%sRestore: %s", "[dry-run] " if dry_run else "", index_js)
    if not dry_run:
        index_js.write_text(restored_script, encoding="utf-8")


def install(options: Options) -> None:
    LOG.info("BetterDiscord installer script")
    LOG.info("Discord data: %s", options.discord_data)
    LOG.info("BetterDiscord asar: %s", options.bd_asar)
    notify("BetterDiscord", "Preparing installation", options.notify)

    update_dir = discord_update_dir()
    if options.wait_update and not wait_for_update(update_dir):
        notify("BetterDiscord", "Discord is still updating", options.notify)
        raise RuntimeError("Discord update did not finish in time")

    version_dir = latest_version_dir(options.discord_data)
    core_dir = find_core_dir(version_dir)
    LOG.info("Discord version: %s", version_dir.name)
    LOG.info("Discord core: %s", core_dir)

    was_running = discord_running()
    if was_running and options.restart and not options.dry_run:
        quit_discord()

    try:
        if options.download:
            download_asar(options.bd_asar, force=options.force_download, dry_run=options.dry_run)
        patch_core(core_dir, dry_run=options.dry_run)
        log_discord_app_version()
    finally:
        if was_running and options.restart and options.reopen and not options.dry_run:
            open_discord()

    notify("BetterDiscord", "Installation complete", options.notify)


def latest_version_dir(discord_data: Path) -> Path:
    versions = sorted((p for p in discord_data.iterdir() if version_key(p)), key=version_key)
    if not versions:
        raise FileNotFoundError(f"No Discord version folders found in {discord_data}")
    return versions[-1]


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
    request = urllib.request.Request(BD_ASAR_URL, headers={"User-Agent": "BetterDiscordInstaller/2.0"})
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
    state = HOME / "Library/Caches/com.hnc.Discord.ShipIt/ShipItState.plist"
    try:
        with state.open("rb") as file:
            url = plistlib.load(file).get("updateBundleURL", "")
    except FileNotFoundError:
        return None
    if url.startswith("file://"):
        url = url[7:-13]
    return Path(url) if url else None


def wait_for_update(update_dir: Optional[Path], timeout: float = 180.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not shipit_running() and (update_dir is None or not update_dir.exists()):
            return True
        LOG.info("Waiting for Discord updater...")
        time.sleep(2)
    return False


def discord_running() -> bool:
    return subprocess.run(["pgrep", "-x", "Discord"], capture_output=True).returncode == 0


def shipit_running() -> bool:
    result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
    return any("ShipIt" in line and "Discord" in line for line in result.stdout.splitlines())


def quit_discord() -> None:
    LOG.info("Quitting Discord")
    subprocess.run(["osascript", "-e", 'quit app "Discord"'], check=False)
    deadline = time.time() + 10
    while time.time() < deadline and discord_running():
        time.sleep(0.25)


def open_discord() -> None:
    LOG.info("Reopening Discord")
    subprocess.run(["open", "-a", "Discord"], check=False)


def log_discord_app_version() -> None:
    try:
        with (DISCORD_APP / "Contents/Info.plist").open("rb") as file:
            LOG.info("Discord app version: %s", plistlib.load(file).get("CFBundleShortVersionString", "unknown"))
    except Exception as error:
        LOG.debug("Could not read Discord app version: %s", error)


def notify(title: str, message: str, enabled: bool) -> None:
    if not enabled:
        return
    script = f'display notification "{escape_osa(message)}" with title "{escape_osa(title)}"'
    subprocess.run(["osascript", "-e", script], check=False)


def escape_osa(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def join_paths(paths) -> str:
    return "\n        ".join(str(path) for path in paths) if paths else "(none)"


if __name__ == "__main__":
    sys.exit(main())
