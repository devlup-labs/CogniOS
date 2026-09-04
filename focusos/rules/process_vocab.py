"""Semantic workload bucket definitions and process matching rules."""

WORKLOAD_BUCKETS = {
    "COMPILATION": {
        "gcc", "g++", "cc1", "cc1plus", "clang", "clang++",
        "make", "cmake", "ninja", "rustc", "cargo", "javac",
        "ld", "as", "collect2", "mvn", "gradle", "go"
    },
    "CODING": {
        "code", "code-insiders", "cursor", "pycharm", "idea",
        "sublime_text", "sublime", "vim", "nvim", "emacs",
        "gedit", "kate"
    },
    "BROWSING": {
        "chrome", "chromium", "firefox", "brave", "msedge",
        "opera", "vivaldi"
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
    "rcu_sched", "watchdog", "kdevtmpfs", "xorg", "pipewire", "pulseaudio",
    "gnome-shell", "plasmashell", "sddm", "lightdm", "gdm", "wayland",
    "dbus-daemon", "networkmanager"
}


def match_process_to_bucket(proc_name: str) -> str | None:
    """Matches a process name to a workload bucket using substring / token matching."""
    if not proc_name or not isinstance(proc_name, str):
        return None

    name_lower = proc_name.strip().lower()

    for bucket, tokens in WORKLOAD_BUCKETS.items():
        for token in tokens:
            if token in name_lower:
                return bucket

    return None


def is_protected_process(proc_name: str) -> bool:
    """Returns True if the process name belongs to the protected system process list."""
    if not proc_name or not isinstance(proc_name, str):
        return True

    name_lower = proc_name.strip().lower()
    return any(prot in name_lower for prot in PROTECTED_NAMES)


if __name__ == "__main__":
    assert match_process_to_bucket("gcc") == "COMPILATION"
    assert match_process_to_bucket("cc1plus") == "COMPILATION"
    assert match_process_to_bucket("chrome") == "BROWSING"
    assert match_process_to_bucket("code") == "CODING"
    assert match_process_to_bucket("random_proc") is None
    assert is_protected_process("systemd") is True
    assert is_protected_process("gcc") is False
    print("[✔] process_vocab tests passed successfully.")
