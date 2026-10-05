#!/usr/bin/env bash
set -euo pipefail

say() { printf 'CogniOS: %s\n' "$*"; }
warn() { printf 'CogniOS warning: %s\n' "$*" >&2; }
die() { printf 'CogniOS error: %s\n' "$*" >&2; exit 1; }

main() {
    local purge=false
    (( $# <= 1 )) || die "Usage: uninstall.sh [--purge]"
    case "${1:-}" in
        "")
            ;;
        --purge)
            purge=true
            ;;
        *)
            die "Usage: uninstall.sh [--purge]"
            ;;
    esac

    local script_path="${BASH_SOURCE[0]:-}"
    if (( EUID != 0 )); then
        if [[ -f "$script_path" ]]; then
            say "Root access is needed to remove system service and launcher files."
            exec sudo bash "$script_path" "$@"
        fi
        die "Piped uninstall needs root. Use: curl -fsSL <uninstaller-url> | sudo bash"
    fi

    local target_user="${SUDO_USER:-}"
    [[ -n "$target_user" && "$target_user" != root ]] || die "Run with sudo from a non-root user."
    local target_uid target_home target_group
    target_uid="$(id -u "$target_user")"
    target_home="$(getent passwd "$target_user" | cut -d: -f6)"
    target_group="$(id -gn "$target_user")"
    [[ -n "$target_home" && -d "$target_home" ]] || die "Could not find the home directory for $target_user."

    as_user() {
        runuser -u "$target_user" -- env \
            HOME="$target_home" \
            USER="$target_user" \
            LOGNAME="$target_user" \
            XDG_RUNTIME_DIR="/run/user/$target_uid" \
            DBUS_SESSION_BUS_ADDRESS="unix:path=/run/user/$target_uid/bus" \
            "$@"
    }

    as_user systemctl --user stop cognios.service 2>/dev/null || true
    while IFS= read -r pid; do
        [[ -n "$pid" ]] && kill "$pid" 2>/dev/null || true
    done < <(pgrep -u "$target_uid" -f '[c]ognios_as_daemon.py' || true)

    systemctl --global disable cognios.service 2>/dev/null || warn "Could not disable the globally enabled CogniOS service."
    rm -f /etc/systemd/user/cognios.service
    rm -f /usr/local/bin/cognios
    rm -f /usr/share/applications/cognios.desktop
    rm -f /usr/share/icons/hicolor/256x256/apps/cognios.png

    command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database /usr/share/applications || true
    command -v gtk-update-icon-cache >/dev/null 2>&1 && gtk-update-icon-cache -f -t /usr/share/icons/hicolor || true

    if [[ "$purge" != true && -d /opt/cognios ]]; then
        local backup_root="$target_home/cognios-data-backup"
        local backup_dir file relative_path destination_dir
        mkdir -p "$backup_root"
        chown "$target_user:$target_group" "$backup_root"
        backup_dir="$(mktemp -d "$backup_root/backup-$(date +%Y%m%d-%H%M%S).XXXXXX")"
        chown "$target_user:$target_group" "$backup_dir"

        while IFS= read -r -d '' file; do
            relative_path="${file#/opt/cognios/}"
            destination_dir="$backup_dir/$(dirname -- "$relative_path")"
            mkdir -p "$destination_dir"
            mv -- "$file" "$destination_dir/"
        done < <(find /opt/cognios -type f \( -name '*.db' -o -name '*.db-*' -o -name '*.sqlite' -o -name '*.sqlite-*' -o -name '*.sqlite3' \) -print0)

        if [[ -f /opt/cognios/.env ]]; then
            mv -- /opt/cognios/.env "$backup_dir/.env"
        fi
        if [[ -n "$(find "$backup_dir" -mindepth 1 -print -quit)" ]]; then
            chown -R "$target_user:$target_group" "$backup_dir"
        fi
        if [[ -z "$(find "$backup_dir" -mindepth 1 -print -quit)" ]]; then
            rmdir "$backup_dir"
            rmdir "$backup_root" 2>/dev/null || true
        else
            say "Saved databases and .env under $backup_dir"
        fi
    fi

    rm -rf -- /opt/cognios
    rm -f /etc/systemd/user/default.target.wants/cognios.service
    say "CogniOS has been uninstalled."
    if [[ "$purge" == true ]]; then
        say "Purged application data."
    else
        say "Database files and .env were moved to $target_home/cognios-data-backup (when present)."
    fi
}

main "$@"
exit $?
