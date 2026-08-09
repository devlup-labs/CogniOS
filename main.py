import logging

from cognios_as_daemon import run_daemon


def main() -> None:
    logging.info(
        "Starting CogniOS through main.py. "
        "BlackBox recording, heartbeat, detection, and replay are enabled."
    )
    run_daemon()


if __name__ == "__main__":
    main()
