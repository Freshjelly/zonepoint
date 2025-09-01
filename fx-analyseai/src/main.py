import os
from dotenv import load_dotenv
from .ingest import pull_latest
from .classify import detect_currencies, classify_event
from .scoring import pairs_from_ccy, sentiment_score, impact_score
from .summarizer import make_summary
from .publish import post_webhook

def run(mode="alerts"):
    items = pull_latest(max_items=60)
    th = float(os.getenv("ALERT_IMPACT_THRESHOLD","3.0"))
    digest = []
    for it in items:
        text = f"{it['title']} {it['summary']}"
        ccys = detect_currencies(text)
        labels = classify_event(text)
        pairs = pairs_from_ccy(ccys)
        senti = sentiment_score(text)
        impact = impact_score(labels)
        msg = make_summary(it, ccys, pairs, labels, senti, impact)
        if mode=="alerts":
            if impact >= th:
                post_webhook("【速報】\n" + msg)
        else:
            digest.append(msg)
    if mode=="digest" and digest:
        head = "【朝ダイジェスト】主要トピック"
        body = "\n---\n".join(digest[:int(os.getenv("DIGEST_MAX_ITEMS","10"))])
        post_webhook(head + "\n" + body)

if __name__ == "__main__":
    load_dotenv()
    run(os.getenv("MODE","alerts"))