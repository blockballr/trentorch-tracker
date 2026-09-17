def terminal_alert(message):
    print(message)
    print("\a", end="", flush=True)
    return True


def simulate_target_alert():
    return terminal_alert(
        "Daily target hit! (test) You've done 6h 40m. Overtime is being tracked."
    )


def fire_if_needed(alert_result):
    if alert_result and alert_result.get("fired"):
        return terminal_alert(alert_result["message"])
    return False
