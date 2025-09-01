import os, json, requests

BASE = os.getenv("LLM_BASE_URL","http://localhost:8000/v1")
MODEL = os.getenv("LLM_MODEL","Qwen/Qwen2.5-7B-Instruct")

SYS_PROMPT = (
  "あなたはFXニュースを初心者にも分かる日本語で要約するアナリストです。"
  "出力は必ずJSONで、keys=['summary_ja','bias','pairs','if_then','confidence']"
)

def summarize_with_llm(text: str) -> dict:
    payload = {
      "model": MODEL,
      "messages": [
        {"role":"system","content":SYS_PROMPT},
        {"role":"user","content":text}
      ],
      "temperature": 0.2,
      "max_tokens": 600
    }
    r = requests.post(f"{BASE}/chat/completions", json=payload, timeout=60)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    try:
        return json.loads(content.replace("'", '"'))
    except Exception:
        return {"summary_ja": content[:500], "bias":"中立", "pairs":[], "if_then":"様子見", "confidence":0.5}