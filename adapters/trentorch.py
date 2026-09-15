import json
from pathlib import Path
import subprocess


def read_progress(clone):
    p = Path(clone) / "user_data" / "progress.json"
    if not p.exists():
        return set(), set()
    raw = p.read_text()
    try:
        d = json.loads(raw)
    except Exception:
        raise ValueError(f"corrupt progress.json at {p}: {raw[:80]}")
    return set(d.get("completed_modules", [])), set(d.get("started_modules", []))


def read_modules(clone):
    out = []
    src = Path(clone) / "data" / "src"
    for d in sorted(src.iterdir()):
        if not d.is_dir():
            continue
        mod_id = d.name.split("_")[0]
        title = mod_id
        y = d / "module.yaml"
        if y.exists():
            try:
                text = y.read_text()
                for line in text.splitlines():
                    if line.strip().startswith("title:"):
                        title = line.split(":", 1)[1].strip()
                        break
            except Exception:
                pass
        out.append({"id": mod_id, "title": title})
    return out


def read_upstream_commit(clone):
    try:
        r = subprocess.run(["git", "-C", clone, "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return "unknown"
        return r.stdout.strip()
    except Exception:
        return "unknown"
