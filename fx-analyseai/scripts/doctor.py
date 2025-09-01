# /home/hyuga/zonepoint/fx-analyseai/scripts/doctor.py
import os, requests, sys
from dotenv import load_dotenv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

def ok(x): return "\u2705" if x else "\u274C"

def main():
    print("== FX-ANALYSEAI DOCTOR ==")
    load_dotenv(ROOT/".env")
    wh = os.getenv("DISCORD_WEBHOOK_URL")
    mode = os.getenv("MODE", "alerts")
    use_llm = os.getenv("USE_LLM", "false")
    thr = os.getenv("ALERT_IMPACT_THRESHOLD", "3.0")
    cfg_env = os.getenv("CONFIG_PATH")
    print(f"env: WEBHOOK set? {ok(bool(wh))} | MODE={mode} | USE_LLM={use_llm} | THR={thr}")
    print(f"cwd={Path.cwd()}  ROOT={ROOT}")
    print(f"CONFIG_PATH={cfg_env}")

    # rules.yml の探索
    from src.classify import _find_rules
    rules = _find_rules()
    print(f"rules.yml: {rules}  exists? {ok(rules.exists())}")

    # webhook ping
    if wh:
        try:
            r = requests.post(wh, json={"content":"✅ webhook ping from doctor.py"}, timeout=10)
            print(f"webhook: status={r.status_code}")
        except Exception as e:
            print(f"webhook: ERROR {e}")

    # RSS とスコアの健全性
    from src.ingest import pull_latest
    from src.classify import detect_currencies, classify_event
    from src.scoring import pairs_from_ccy, sentiment_score, impact_score

    # 既読DBを温存したまま10件だけ観測
    items = pull_latest(max_items=10)
    print(f"fresh items observed: {len(items)}")
    for it in items[:5]:
        text = f"{it['title']} {it['summary']}"
        cc = detect_currencies(text); lb = classify_event(text)
        im = impact_score(lb); se = sentiment_score(text)
        print(f"- impact={im} senti={se} labels={lb} ccys={cc} | {it['title'][:70]}")

if __name__ == "__main__":
    main()