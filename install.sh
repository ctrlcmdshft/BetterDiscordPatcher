#!/bin/sh
set -eu

APP_NAME="BetterDiscordCLIInstaller"
INSTALL_DIR="${BDI_INSTALL_DIR:-"$HOME/Library/Application Support/$APP_NAME"}"
BIN_DIR="${BDI_BIN_DIR:-"$HOME/.local/bin"}"
BIN_PATH="${BDI_BIN_PATH:-"$BIN_DIR/betterdiscord"}"
REPO="${BDI_REPO:-ctrlcmdshft/BetterDiscordCLIInstaller}"
BRANCH="${BDI_BRANCH:-main}"
RAW_BASE="${BDI_RAW_BASE:-https://raw.githubusercontent.com/$REPO/$BRANCH}"

say() {
    printf '%s\n' "$1"
}

need() {
    if ! command -v "$1" >/dev/null 2>&1; then
        say "Missing required command: $1"
        exit 1
    fi
}

download() {
    url="$1"
    dest="$2"
    tmp="$dest.tmp"
    say "Downloading $url"
    curl -fsSL "$url" -o "$tmp"
    mv "$tmp" "$dest"
}

need curl
need python3

if [ "$(uname -s)" != "Darwin" ]; then
    say "This installer supports macOS only."
    exit 1
fi

mkdir -p "$INSTALL_DIR"
mkdir -p "$(dirname "$BIN_PATH")"
download "$RAW_BASE/betterdiscord.py" "$INSTALL_DIR/betterdiscord.py"
download "$RAW_BASE/README.md" "$INSTALL_DIR/README.md"

cat >"$INSTALL_DIR/betterdiscord" <<'EOF'
#!/bin/zsh
DIR="${0:A:h}"
python3 "$DIR/betterdiscord.py" "$@"
EOF
chmod +x "$INSTALL_DIR/betterdiscord"

python3 -m py_compile "$INSTALL_DIR/betterdiscord.py"

tmp_wrapper="$INSTALL_DIR/betterdiscord-bin"
cat >"$tmp_wrapper" <<EOF
#!/bin/zsh
python3 "$INSTALL_DIR/betterdiscord.py" "\$@"
EOF

if [ -w "$(dirname "$BIN_PATH")" ]; then
    cp "$tmp_wrapper" "$BIN_PATH"
    chmod +x "$BIN_PATH"
else
    say "Installing global command with sudo: $BIN_PATH"
    sudo cp "$tmp_wrapper" "$BIN_PATH"
    sudo chmod +x "$BIN_PATH"
fi
rm -f "$tmp_wrapper"

say "Installed: $INSTALL_DIR"
say "Command: betterdiscord"
case ":$PATH:" in
    *":$(dirname "$BIN_PATH"):"*) ;;
    *) say "Add this to your shell profile if needed: export PATH=\"$(dirname "$BIN_PATH"):\$PATH\"" ;;
esac
say "Try: betterdiscord --help"
