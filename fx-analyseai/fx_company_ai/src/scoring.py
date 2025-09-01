import os, yaml
from pathlib import Path

def _find_rules() -> Path:
    env = os.getenv("CONFIG_PATH")
    if env and Path(env).exists():
        return Path(env)
    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / "config" / "rules.yml",
        here.parents[1] / "config" / "rules.yml",
        here.parents[2] / "config" / "rules.yml",
    ]
    for p in list(candidates) + [p / "config" / "rules.yml" for p in here.parents]:
        if p.exists():
            return p
    raise FileNotFoundError("config/rules.yml not found. Set CONFIG_PATH env var or place the file under project_root/config/")

RULES_PATH = _find_rules()
with open(RULES_PATH,"r",encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

PAIR_MAP = CFG["pair_map"]
HAWK = [w.lower() for w in CFG["hawkish_words"]]
DOVE = [w.lower() for w in CFG["dovish_words"]]

def pairs_from_ccy(ccys):
    pairs = set()
    for c in ccys:
        for p in PAIR_MAP.get(c, []):
            pairs.add(p)
    return sorted(list(pairs))

def sentiment_score(text: str) -> int:
    t = text.lower()
    s = 0
    s += sum(1 for w in HAWK if w in t)
    s -= sum(1 for w in DOVE if w in t)
    return max(-3, min(3, s))

def impact_score(event_labels) -> float:
    w = 0
    if "policy" in event_labels: w += 3
    if "inflation" in event_labels or "jobs" in event_labels: w += 2
    if "speech" in event_labels: w += 1
    if "risk" in event_labels: w += 2
    return float(w or 1.0)
