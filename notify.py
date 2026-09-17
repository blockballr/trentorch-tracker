import subprocess
import sys


def _escape_ps(s):
    return s.replace("'", "''")


def _toast_windows(message):
    ps = (
        "try {"
        " Import-Module BurntToast -ErrorAction Stop;"
        f" New-BurntToastNotification -Text '{_escape_ps(message)}' -ErrorAction Stop"
        "} catch { exit 1 }"
    )
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        timeout=10,
    )
    return r.returncode == 0


def _toast_linux(message):
    r = subprocess.run(
        ["notify-send", "TrenTorch", message],
        capture_output=True,
        timeout=5,
    )
    return r.returncode == 0


def try_toast(message):
    """Optional platform toast. Failure is silent; bell already fired."""
    try:
        if sys.platform == "win32":
            return _toast_windows(message)
        if sys.platform.startswith("linux"):
            return _toast_linux(message)
    except Exception:
        return False
    return False


def terminal_alert(message, toast=True):
    print(message)
    print("\a", end="", flush=True)
    if toast:
        try_toast(message)
    return True


def simulate_target_alert():
    return terminal_alert(
        "Daily target hit! (test) You've done 6h 40m. Overtime is being tracked."
    )


def fire_if_needed(alert_result):
    if alert_result and alert_result.get("fired"):
        return terminal_alert(alert_result["message"])
    return False
