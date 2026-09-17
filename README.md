# trentorch-tracker
Personal roadmap tracker for TrenTorch. Standalone, read-only adapter.

## Forecast
```
python tracker.py --update --config private/my.yaml
```

### Your pace (40h/week, 6 days, Sun off)
```
python tracker.py --update --config private/my.yaml
```
- ~6.67h/day, proficient 2026-11-03 (through Module 13 Transformers), finish 2026-12-11

### Anyone else (10h/week, 5 days)
```
# copy private/my.example.yaml to private/my.yaml
# set hours_per_week: 10, days_per_week: 5, trentorch_path: <their clone>
python tracker.py --update --config private/my.yaml
```
- ~50 weeks (~12 months), ~2h/day

## Study timer
Short command entrypoint is `python tr.py`. Config defaults to `private/my.yaml`.

```
python tr.py start [module]   # start timer; module defaults to progress.last_worked
python tr.py pause
python tr.py resume
python tr.py stop             # append session to private/sessions.jsonl
python tr.py status           # active/paused, regular vs overtime, min to target
python tr.py report           # actuals vs estimates across modules
python tr.py watch            # foreground 60s loop; alert when daily target hit
python tr.py watch --test     # simulate the target alert
```

Daily target = `(hours_per_week / days_per_week) * 60` minutes (40/6 → 400).
Regular time fills up to the target; the rest is overtime. Alert fires once per day.
Timer state and sessions live under `private/` and are never committed.

Notifications use the terminal bell plus a message. Toast delivery and estimate auto-adjust are later work.

## Tests
```
C:\Users\user\AppData\Local\Programs\Python\Python314\python.exe -m pytest tests -q
```
