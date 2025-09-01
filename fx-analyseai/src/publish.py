import os, requests

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

def post_webhook(text: str):
    if not WEBHOOK: return
    requests.post(WEBHOOK, json={"content": text[:1900]}, timeout=15)