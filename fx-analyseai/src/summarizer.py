import os
from .template import render
from .llm_client import summarize_with_llm

USE_LLM = os.getenv("USE_LLM","false").lower() == "true"

def make_summary(item, ccys, pairs, labels, senti, impact):
    text = f"{item['title']} {item['summary']}"
    if USE_LLM:
        j = summarize_with_llm(text)
        return (
            f"【要約】{j['summary_ja']}\n"
            f"- バイアス: {j['bias']} / 影響ペア: {', '.join(j.get('pairs',[]))}\n"
            f"- If-Then: {j['if_then']}\n"
            f"- 確度: {j.get('confidence',0):.2f}\n"
            f"出典: {item['source']} | {item['link']}\n"
            f"※投資助言ではありません。"
        )
    else:
        return render(item, ccys, pairs, labels, senti, impact)