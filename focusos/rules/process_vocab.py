"""Semantic workload bucket definitions and process matching rules."""

import os
import re

WORKLOAD_BUCKETS = {
    "COMPILATION": {
        "gcc", "g++", "cc1", "cc1plus", "clang", "clang++",
        "make", "cmake", "ninja", "rustc", "cargo", "javac",
        "ld", "as", "collect2", "mvn", "gradle", "go"
    },
    "CODING": {
        "code", "code-insiders", "cursor", "pycharm", "idea",
        "sublime_text", "sublime", "vim", "nvim", "emacs",
        "gedit", "kate", "antigravity-ide", "antigravity",
        "python", "python3", "node", "npm", "yarn", "git",
        "bash", "zsh", "fish", "rust-analyzer", "gopls", "pytest",
        "agy", "terminal", "gnome-terminal", "gnome-terminal-server",
        "alacritty", "kitty", "wezterm", "tmux"
    },
    "BROWSING": {
        "chrome", "chromium", "google-chrome", "google-chrome-stable",
        "firefox", "brave", "msedge", "opera", "vivaldi", "epiphany"
    },
    "VIDEO_CALL": {
        "zoom", "teams", "discord", "meet", "slack",
        "skype", "webex", "telegram"
    },
    "GAMING": {
        "steam", "csgo", "dota2", "hl2_linux", "minecraft",
        "lutris", "wine", "proton"
    },
    "MEDIA_PROCESSING": {
        "ffmpeg", "handbrake", "blender", "kdenlive",
        "obs", "vlc"
    },
}

# Critical system/session processes that must NEVER be modified by optimization
PROTECTED_NAMES = {
    "systemd", "init", "kthreadd", "migration", "ksoftirqd", "kworker",
    "rcu_sched", "rcu_preempt", "rcu", "watchdog", "kdevtmpfs", "xorg", "pipewire", "pulseaudio",
    "gnome-shell", "plasmashell", "sddm", "lightdm", "gdm", "wayland",
    "dbus-daemon", "networkmanager", "wireplumber", "mutter", "systemd-resolved",
    "systemd-udevd", "systemd-journald", "polkitd", "accounts-daemon", "irqbalance",
    "mutter-x11-frames", "upowerd"
}


def match_process_to_bucket(proc_name: str) -> str | None:
    """Matches a process name to a workload bucket using delimited token / word-boundary matching."""
    if not proc_name or not isinstance(proc_name, str):
        return None

    name_lower = os.path.basename(proc_name.strip().lower())

    for bucket, tokens in WORKLOAD_BUCKETS.items():
        for token in tokens:
            pattern = rf"(^|[^a-z0-9]){re.escape(token)}([^a-z0-9]|$)"
            if re.search(pattern, name_lower):
                return bucket

    return None


def is_protected_process(proc_name: str) -> bool:
    """Returns True if the process name belongs to the protected system process list."""
    if not proc_name or not isinstance(proc_name, str):
        return True

    name_lower = os.path.basename(proc_name.strip().lower())
    if name_lower.startswith("kworker") or name_lower.startswith("rcu") or name_lower.startswith("mt76"):
        return True

    for prot in PROTECTED_NAMES:
        pattern = rf"(^|[^a-z0-9]){re.escape(prot)}([^a-z0-9]|$)"
        if re.search(pattern, name_lower):
            return True

    return False


if __name__ == "__main__":
    assert match_process_to_bucket("gcc") == "COMPILATION"
    assert match_process_to_bucket("cc1plus") == "COMPILATION"
    assert match_process_to_bucket("chrome") == "BROWSING"
    assert match_process_to_bucket("google-chrome") == "BROWSING"
    assert match_process_to_bucket("code") == "CODING"
    assert match_process_to_bucket("bash") is None
    assert match_process_to_bucket("random_proc") is None
    assert is_protected_process("systemd") is True
    assert is_protected_process("gcc") is False
    assert is_protected_process("uninitialized") is False
    print("[✔] process_vocab tests passed successfully.")
