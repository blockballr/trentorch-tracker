import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import notify
import sessions
from report import build_report, format_report


def _default_config():
    return Path(__file__).parent / "private" / "my.yaml"


def _print_status(st):
    if st.get("closed_note"):
        print(st["closed_note"])
    if not st["active"]:
        print(
            f"stopped | today regular {st['total_regular']:.0f}m "
            f"overtime {st['total_overtime']:.0f}m "
            f"/ target {st['daily_target_min']:.0f}m "
            f"| min to target {st['minutes_to_target']:.0f}"
        )
        return
    state = "paused" if st["paused"] else "active"
    print(
        f"{state} module {st['module']} | live {st['live_minutes']:.0f}m "
        f"(regular {st['live_regular']:.0f}m / overtime {st['live_overtime']:.0f}m) "
        f"| today regular {st['total_regular']:.0f}m "
        f"overtime {st['total_overtime']:.0f}m "
        f"/ target {st['daily_target_min']:.0f}m "
        f"| min to target {st['minutes_to_target']:.0f}"
    )


def main(argv=None):
    ap = argparse.ArgumentParser(prog="tr", description="TrenTorch study timer")
    ap.add_argument("--config", default=str(_default_config()))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start")
    p_start.add_argument("module", nargs="?")

    sub.add_parser("pause")
    sub.add_parser("resume")
    sub.add_parser("stop")
    sub.add_parser("status")
    sub.add_parser("report")

    p_watch = sub.add_parser("watch")
    p_watch.add_argument("--test", action="store_true")
    p_watch.add_argument("--interval", type=int, default=60)

    a = ap.parse_args(argv)
    cfg = a.config
    try:
        if a.cmd == "start":
            state = sessions.start(cfg, module=a.module)
            print(f"started module {state['module']} at {state['start_time']}")
            notify.fire_if_needed(sessions.maybe_alert(cfg))
            return 0
        if a.cmd == "pause":
            sessions.pause(cfg)
            print("paused")
            notify.fire_if_needed(sessions.maybe_alert(cfg))
            return 0
        if a.cmd == "resume":
            sessions.resume(cfg)
            print("resumed")
            return 0
        if a.cmd == "stop":
            rec = sessions.stop(cfg)
            print(
                f"stopped module {rec['module']}: regular {rec['regular_minutes']}m "
                f"overtime {rec['overtime_minutes']}m pauses {rec['pause_count']}"
            )
            fired = notify.fire_if_needed(sessions.maybe_alert(cfg))
            if not fired and rec.get("target_hit"):
                print(
                    "Daily target hit! Overtime is being tracked."
                )
            return 0
        if a.cmd == "status":
            st = sessions.status(cfg)
            _print_status(st)
            notify.fire_if_needed(sessions.maybe_alert(cfg))
            return 0
        if a.cmd == "report":
            print(format_report(build_report(cfg)))
            return 0
        if a.cmd == "watch":
            if a.test:
                notify.simulate_target_alert()
                return 0
            print(f"watching every {a.interval}s (ctrl-c to stop)")
            while True:
                notify.fire_if_needed(sessions.maybe_alert(cfg))
                time.sleep(max(1, int(a.interval)))
        return 1
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    except (FileNotFoundError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
