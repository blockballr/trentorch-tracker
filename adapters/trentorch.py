import json
from pathlib import Path
import subprocess

DEFAULT_TITLES = {
    "M1": "1958 Perceptron",
    "M2": "1969 XOR",
    "M3": "1986 MLP",
    "M4": "1998 CNN",
    "M5": "2017 Transformer",
    "M6": "2018 MLPerf",
}


def read_progress(clone, profile_path=None):
    """Completed, started sets. Falls back to ~/.trentorch/profile.json when progress.json is missing."""
    p = Path(clone) / "user_data" / "progress.json"
    if p.exists():
        raw = p.read_text(encoding="utf-8")
        try:
            d = json.loads(raw)
        except Exception:
            raise ValueError(f"corrupt progress.json at {p}: {raw[:80]}")
        return set(d.get("completed_modules", [])), set(d.get("started_modules", []))
    prof = Path(profile_path) if profile_path else Path.home() / ".trentorch" / "profile.json"
    if prof.exists():
        try:
            d = json.loads(prof.read_text(encoding="utf-8"))
            completed = set(str(x) for x in d.get("modules_completed", []))
            started = set(completed)
            return completed, started
        except Exception:
            pass
    return set(), set()


def read_modules(clone):
    out = []
    src = Path(clone) / "data" / "src"
    if not src.exists():
        return out
    for d in sorted(src.iterdir()):
        if not d.is_dir():
            continue
        mod_id = d.name.split("_")[0]
        title = mod_id
        y = d / "module.yaml"
        if y.exists():
            try:
                text = y.read_text(encoding="utf-8")
                for line in text.splitlines():
                    if line.strip().startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip('"')
                        break
            except Exception:
                pass
        out.append({"id": mod_id, "title": title, "kind": "module"})
    return out


def read_milestones(clone):
    """Milestones from clone data/milestones when present; ids M1..M6 by directory order."""
    root = Path(clone) / "data" / "milestones"
    out = []
    if not root.exists():
        return out
    dirs = sorted([d for d in root.iterdir() if d.is_dir() and d.name[:2].isdigit()], key=lambda p: p.name)
    for i, d in enumerate(dirs, start=1):
        mid = f"M{i}"
        title = DEFAULT_TITLES.get(mid, d.name.split("_", 1)[-1].replace("_", " ").title())
        y = d / "module.yaml"
        readme = d / "README.md"
        if y.exists():
            try:
                for line in y.read_text(encoding="utf-8").splitlines():
                    if line.strip().startswith("title:"):
                        title = line.split(":", 1)[1].strip().strip('"')
                        break
            except Exception:
                pass
        elif readme.exists():
            try:
                first = readme.read_text(encoding="utf-8").splitlines()
                for line in first:
                    if line.startswith("# "):
                        title = line[2:].strip()
                        break
            except Exception:
                pass
        out.append({"id": mid, "title": title, "kind": "milestone"})
    return out


def read_upstream_commit(clone):
    try:
        r = subprocess.run(
            ["git", "-C", clone, "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return "unknown"
        return r.stdout.strip()
    except Exception:
        return "unknown"
