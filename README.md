# trentorch-tracker
Personal roadmap tracker for TrenTorch. Standalone, read-only adapter.

MIT licensed. Does not write into a TrenTorch clone.

## Forecast
```
python tracker.py --update --config private/my.yaml
python tracker.py --update --config private/my.yaml --auto-adjust
python tracker.py --update --config private/my.yaml --trentorch-path C:/path/to/TrenTorch
python tracker.py --update --config private/my.yaml --skill-mult 1.2
```

### Your pace (40h/week, 6 days, Sun off)
```
python tracker.py --update --config private/my.yaml
```
- ~6.67h/day, proficient 2026-11-03 (Module 13 Transformers), finish 2026-12-11

### Anyone else (10h/week, 5 days)
```
# copy private/my.example.yaml to private/my.yaml
# set hours_per_week: 10, days_per_week: 5, trentorch_path: <their clone>
python tracker.py --update --config private/my.yaml
```
Computed from the same defaults (start 2026-09-15, 20% buffer):
- ~2.0h/day, proficient 2027-02-25, finish 2027-07-07 (~50.6 weeks)

Weeks to finish stay the same when you switch 5/6/7 days at the same weekly hours; daily load and calendar due dates move.

### Estimate controls
- `skill_mult` (config or `--skill-mult`) multiplies every module/milestone estimate hour. Default 1.0.
- `--trentorch-path` overrides the clone path in config for one run.
- Milestone titles are read from the clone `data/milestones/` when present; hours still come from `timeline.defaults.yaml`.
- If `user_data/progress.json` is missing, completed modules fall back to `~/.trentorch/profile.json` `modules_completed`.
- Observed ratio = actual logged hours / estimate hours on modules that have session time.
- When that ratio is more than 10% off 1.0 and auto-adjust is on, remaining hours are scaled before dates are computed.
- Report always prints the ratio diagnosis. Forecast dates stay on base estimates unless `auto_adjust: true` or `--auto-adjust`.

Invalid config (bad `days_per_week`, missing path, `skill_mult <= 0`) exits 2.

## Study timer
```
python tr.py start [module]
python tr.py pause
python tr.py resume
python tr.py stop
python tr.py status
python tr.py report
python tr.py weekly
python tr.py heatmap
python tr.py heatmap --html
python tr.py heatmap --html path\to\out.html --weeks 12
python tr.py watch
python tr.py watch --test
```

Daily target = `(hours_per_week / days_per_week) * 60` minutes (40/6 → 400).
Regular time fills up to the target; the rest is overtime. Alert fires once per day.
Timer state and sessions live under `private/` and are never committed.

Notifications: terminal bell + message always. Optional toast via BurntToast (Windows) or notify-send (Linux) when available; missing modules are ignored.

`heatmap --html` writes a self-contained dark HTML grid next to the config (`heatmap.html`) or to the path you pass. Open it in a browser for screenshots. Terminal heatmap stays the default when `--html` is omitted.

## Config template
`private/my.example.yaml` is tracked. Copy it to `private/my.yaml` (gitignored) and point `trentorch_path` at your clone.

## Limitations
- Hours for curriculum items come from `timeline.defaults.yaml`, not from live file sizes.
- Auto-adjust scales remaining estimates only; it does not rewrite completed modules.
- Toast support is best-effort; bell always works.
- No GUI. CLI only, Python 3.10+.
- Never writes into the TrenTorch clone.

## Tests
```
C:\Users\user\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests -q
```
