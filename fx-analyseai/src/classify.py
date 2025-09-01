# /home/hyuga/zonepoint/fx-analyseai/src/classify.py
import os, re, yaml
from pathlib import Path
from typing import List

def _find_rules() -> Path:
    # 1) 環境変数で明示指定が最優先
    env = os.getenv("CONFIG_PATH")
    if env and Path(env).exists():
        return Path(env)
    # 2) 代表的な候補
    here = Path(__file__).resolve()
    candidates = [
        Path.cwd() / "config" / "rules.yml",        # 実行中の作業ディレクトリ
        here.parents[1] / "config" / "rules.yml",   # プロジェクトルート/config
        here.parents[2] / "config" / "rules.yml",   # fx_company_ai/config 等
    ]
    # 親を遡って探索（保険）
    for p in list(candidates) + [p / "config" / "rules.yml" for p in here.parents]:
        if p.exists():
            return p
    raise FileNotFoundError("config/rules.yml not found. Set CONFIG_PATH env var or place the file under project_root/config/")

RULES_PATH = _find_rules()
with open(RULES_PATH, "r", encoding="utf-8") as f:
    CFG = yaml.safe_load(f)

EVENT_RULES = [(k, v) for k, v in CFG["event_rules"].items()]
PAIR_MAP = CFG["pair_map"]

def detect_currencies(text: str) -> List[str]:
    hits = set()
    up = text.upper()
    for ccy in PAIR_MAP.keys():
        if re.search(rf"\b{ccy}\b", up):
            hits.add(ccy)
    if re.search(r"\bFOMC|FEDERAL RESERVE|FRB\b", up): hits.add("USD")
    if "日本銀行" in text or "BOJ" in up: hits.add("JPY")
    if "ECB" in up or "欧州中央銀行" in text: hits.add("EUR")
    if "イングランド銀行" in text or "BOE" in up: hits.add("GBP")
    return sorted(list(hits))

def classify_event(text: str) -> List[str]:
    labels = []
    for name, pat in EVENT_RULES:
        if re.search(pat, text, re.IGNORECASE):
            labels.append(name)
    return labels or ["general"]