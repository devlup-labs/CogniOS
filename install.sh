#!/usr/bin/env bash
set -euo pipefail

say() { printf 'CogniOS: %s\n' "$*"; }
warn() { printf 'CogniOS warning: %s\n' "$*" >&2; }
die() { printf 'CogniOS error: %s\n' "$*" >&2; exit 1; }

ask() {
    local answer
    [[ -r /dev/tty ]] || die "An interactive terminal is required to answer: $1"
    read -r -p "$1 [Y/n] " answer </dev/tty
    [[ -z "$answer" || "$answer" =~ ^[Yy]([Ee][Ss])?$ ]]
}

SCRIPT_PATH="${BASH_SOURCE[0]:-}"
UPDATE_MODE=false
if [[ "${1:-}" == "--update" ]]; then
    UPDATE_MODE=true
    shift
fi
(( $# == 0 )) || die "Usage: install.sh [--update]"
if (( EUID != 0 )); then
    if [[ -f "$SCRIPT_PATH" ]]; then
        say "Root access is needed to install system packages and create system-wide command, icon, and service files."
        if [[ "$UPDATE_MODE" == true ]]; then
            exec sudo --preserve-env=COGNIOS_REPO,COGNIOS_REF,COGNIOS_FORCE_DOWNLOAD bash "$SCRIPT_PATH" --update
        fi
        exec sudo --preserve-env=COGNIOS_REPO,COGNIOS_REF,COGNIOS_FORCE_DOWNLOAD bash "$SCRIPT_PATH"
    fi
    die "Piped installation needs root. Use: curl -fsSL <installer-url> | sudo bash"
fi

TARGET_USER="${SUDO_USER:-}"
[[ -n "$TARGET_USER" && "$TARGET_USER" != root ]] || die "Run with sudo from a non-root user so the install can be owned by that user."
TARGET_UID="$(id -u "$TARGET_USER")"
TARGET_HOME="$(getent passwd "$TARGET_USER" | cut -d: -f6)"
TARGET_GROUP="$(id -gn "$TARGET_USER")"
[[ -n "$TARGET_HOME" && -d "$TARGET_HOME" ]] || die "Could not find the home directory for $TARGET_USER."

as_user() {
    runuser -u "$TARGET_USER" -- env \
        HOME="$TARGET_HOME" \
        USER="$TARGET_USER" \
        LOGNAME="$TARGET_USER" \
        XDG_RUNTIME_DIR="/run/user/$TARGET_UID" \
        DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$TARGET_UID/bus" \
        "$@"
}

stop_user_daemon() {
    as_user systemctl --user stop cognios.service 2>/dev/null || true
    while IFS= read -r pid; do
        [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    done < <(pgrep -u "$TARGET_UID" -f '[c]ognios_as_daemon.py' || true)
}

install_packages() {
    local manager="$1"
    shift
    local package
    for package in "$@"; do
        if [[ "$manager" == dnf ]]; then
            dnf install -y "$package" || warn "Could not install package: $package"
        else
            apt-get install -y --no-install-recommends "$package" || warn "Could not install package: $package"
        fi
    done
}

TEMP_DIR=""
cleanup() {
    if [[ -n "$TEMP_DIR" && -d "$TEMP_DIR" ]]; then
        rm -rf -- "$TEMP_DIR"
    fi
}
trap cleanup EXIT

COGNIOS_REPO="${COGNIOS_REPO:-OWNER/cognios}"
COGNIOS_REF="${COGNIOS_REF:-main}"
SCRIPT_DIR=""
if [[ -n "$SCRIPT_PATH" && -f "$SCRIPT_PATH" ]]; then
    SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" 2>/dev/null && pwd || true)"
fi

if [[ "${COGNIOS_FORCE_DOWNLOAD:-0}" != "1" && -n "$SCRIPT_DIR" && -f "$SCRIPT_DIR/main.py" && -f "$SCRIPT_DIR/cognios_as_daemon.py" ]]; then
    SOURCE_DIR="$SCRIPT_DIR"
else
    [[ "$COGNIOS_REPO" != "OWNER/cognios" ]] || die "Set COGNIOS_REPO=owner/repository before installing from a downloaded script."
    command -v curl >/dev/null 2>&1 || die "curl is required to download CogniOS."
    command -v tar >/dev/null 2>&1 || die "tar is required to extract CogniOS."
    TEMP_DIR="$(mktemp -d)"
    say "Downloading $COGNIOS_REPO ($COGNIOS_REF)..."
    curl -fsSL "https://github.com/$COGNIOS_REPO/archive/refs/heads/$COGNIOS_REF.tar.gz" -o "$TEMP_DIR/source.tar.gz" ||
        die "Could not download the CogniOS source archive."
    tar -xzf "$TEMP_DIR/source.tar.gz" -C "$TEMP_DIR"
    SOURCE_DIR="$(dirname -- "$(find "$TEMP_DIR" -type f -name main.py -print -quit)")"
    [[ -f "$SOURCE_DIR/cognios_as_daemon.py" ]] || die "Downloaded archive does not contain the CogniOS application files."
fi

if command -v dnf >/dev/null 2>&1; then
    install_packages dnf \
        python3 python3-pip libnotify rsync xcb-util-cursor mesa-libGL nss \
        libxkbcommon-x11 xcb-util-wm xcb-util-image xcb-util-keysyms xcb-util-renderutil \
        curl tar
elif command -v apt-get >/dev/null 2>&1; then
    install_packages apt-get \
        python3 python3-venv python3-pip libnotify-bin rsync libxcb-cursor0 libgl1 libnss3 \
        libxkbcommon-x11-0 libxcb-xinerama0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
        libxcb-render-util0 libxcb-shape0 libxcb-xkb1 curl tar
else
    warn "Neither dnf nor apt-get was found; continuing without installing system packages."
fi

if [[ -f "$TARGET_HOME/.config/systemd/user/cognios.service" ]]; then
    stop_user_daemon
    as_user systemctl --user disable cognios.service 2>/dev/null || warn "Could not disable the existing per-user CogniOS service."
    backup_unit="$TARGET_HOME/.config/systemd/user/cognios.service.bak"
    if [[ -e "$backup_unit" ]]; then
        backup_unit="$backup_unit.$(date +%Y%m%d%H%M%S)"
    fi
    mv "$TARGET_HOME/.config/systemd/user/cognios.service" "$backup_unit"
fi
stop_user_daemon

mkdir -p /opt/cognios
rsync -a --delete \
    --exclude='.venv' \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='.streamlit' \
    --exclude='.env' \
    --exclude='*.db' \
    --exclude='*.db-shm' \
    --exclude='*.db-wal' \
    --exclude='*.log' \
    "$SOURCE_DIR/" /opt/cognios/

if [[ -f "$SOURCE_DIR/.env" && ! -e /opt/cognios/.env ]]; then
    cp -p "$SOURCE_DIR/.env" /opt/cognios/.env
fi

chown -R "$TARGET_USER:$TARGET_GROUP" /opt/cognios
if [[ ! -x /opt/cognios/.venv/bin/python ]]; then
    as_user python3 -m venv /opt/cognios/.venv
fi
as_user /opt/cognios/.venv/bin/python -m pip install -r /opt/cognios/requirements.txt

cat > /usr/local/bin/cognios <<'COMMAND'
#!/usr/bin/env bash
set -euo pipefail
usage() {
    printf '%s\n' \
        'Usage: cognios [--ui desktop|browser]' \
        '       cognios start|stop|restart|status|logs|update|upgrade|uninstall [--purge]'
}
case "${1:-}" in
    "")
        cd /opt/cognios
        exec .venv/bin/python main.py
        ;;
    --ui)
        cd /opt/cognios
        exec .venv/bin/python main.py "$@"
        ;;
    start|stop|restart|status)
        exec systemctl --user "$1" cognios.service
        ;;
    update|upgrade)
        exec sudo env \
            COGNIOS_REPO=devlup-labs/CogniOS \
            COGNIOS_REF=main \
            COGNIOS_FORCE_DOWNLOAD=1 \
            bash /opt/cognios/install.sh --update
        ;;
    logs)
        exec journalctl --user -u cognios.service -f
        ;;
    uninstall)
        shift
        exec sudo bash /opt/cognios/uninstall.sh "$@"
        ;;
    -h|--help)
        usage
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac
COMMAND
chmod 755 /usr/local/bin/cognios

mkdir -p /usr/share/applications /usr/share/icons/hicolor/256x256/apps
if [[ -f /opt/cognios/assets/image.png ]]; then
    install -m 644 /opt/cognios/assets/image.png /usr/share/icons/hicolor/256x256/apps/cognios.png
    ICON="cognios"
else
    ICON="utilities-system-monitor"
fi
cat > /usr/share/applications/cognios.desktop <<DESKTOP
[Desktop Entry]
Type=Application
Name=CogniOS
Comment=System observability and diagnostics
Exec=cognios --ui desktop
Icon=$ICON
Terminal=false
Categories=System;Monitor;
DESKTOP

mkdir -p /etc/systemd/user
cat > /etc/systemd/user/cognios.service <<'SERVICE'
[Unit]
Description=CogniOS telemetry daemon

[Service]
Type=simple
WorkingDirectory=/opt/cognios
ExecStartPre=/bin/sleep 5
ExecStart=/opt/cognios/.venv/bin/python /opt/cognios/cognios_as_daemon.py
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
SERVICE
systemctl --global enable cognios.service

command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database /usr/share/applications || true
command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true

if [[ "$UPDATE_MODE" == true ]]; then
    as_user systemctl --user daemon-reload &&
        as_user systemctl --user restart cognios.service
elif ask "Start the daemon now?"; then
    as_user systemctl --user daemon-reload &&
        as_user systemctl --user start cognios.service
fi

say "Installation complete."
say "Open the UI with: cognios"
say "Check the daemon with: cognios status"
say "Uninstall with: cognios uninstall (use --purge to remove saved data)"
