# ✅ Claude Code 向けプロンプト（Markdown版／コピペ用）

あなたはエンジニアです。以下の仕様で**Pythonプロジェクト一式を新規作成**し、指定の**ファイル内容をそのまま**書き込み、ローカルで実行できる状態にしてください。  
目的：**FXニュースを収集→簡易分析→（将来は自社LLM要約）→Discordに配信**するMVPの実装。  
私はDockerを別担当で進めるため、あなたは**ローカル実行が通るところまで**を担当してください。

---

## 成果物（要件）

- ルート名：`fx_company_ai/`
- Python 3.10+ / 仮想環境はユーザー側で後から作成
- `src/` のコードは **相対インポート**（`python -m src.main` 実行前提）
- デフォルトは **Webhook配信**（会話Botは同梱だが任意）
- `.env` で切替：`USE_LLM=false`（最初はルール要約）→ `true` で自社LLM APIに切替
- 指定された**全ファイルを作成＆上書き**。不足があれば最小限補ってOK

---

## 1) ディレクトリ構成を作成

```
fx_company_ai/
├─ .env.example
├─ requirements.txt
├─ README.md
├─ .gitignore
│
├─ data/
│  ├─ train.jsonl
│  ├─ val.jsonl
│  └─ seen_urls.sqlite   # 実行後に自動生成
│
├─ config/
│  └─ rules.yml
│
├─ src/
│  ├─ __init__.py
│  ├─ ingest.py
│  ├─ classify.py
│  ├─ scoring.py
│  ├─ template.py
│  ├─ llm_client.py
│  ├─ summarizer.py
│  ├─ publish.py
│  └─ main.py
│
├─ model/
│  ├─ __init__.py
│  ├─ train_lora.py
│  ├─ merge_lora.py
│  └─ serve_vllm.sh
│
└─ bot/
   ├─ __init__.py
   └─ discord_bot.py
```

---

## 2) 各ファイルの**内容をそのまま**書き込み

### `.gitignore`
```gitignore
# Python
__pycache__/
*.pyc
.venv/
.env
.out/
logs/
out/
data/seen_urls.sqlite

# OS
.DS_Store
```

### `.env.example`
```env
# Discord
DISCORD_WEBHOOK_URL=
DISCORD_BOT_TOKEN=

# LLM endpoint（OpenAI互換API: vLLM / TGI）
LLM_BASE_URL=http://localhost:8000/v1
LLM_MODEL=Qwen/Qwen2.5-7B-Instruct
USE_LLM=false

# ジョブ
TIMEZONE=Asia/Tokyo
ALERT_IMPACT_THRESHOLD=3.0
DIGEST_MAX_ITEMS=10

# 実行モード（alerts or digest）
MODE=alerts
```

### `requirements.txt`
```txt
feedparser
requests
beautifulsoup4
python-dotenv
langdetect
tqdm
pydantic
pyyaml
aiohttp
discord.py

# 学習/推論（学習マシンのみ必要）
torch
transformers
datasets
peft
accelerate
trl
```

### `README.md`
```md
# FX Company AI (MVP)

FXニュースを収集 → 簡易分析（ルール） → Discordへ配信。将来は自社LLM（vLLM等）で要約に切替。

## セットアップ
```bash
cp .env.example .env
# .env を編集（DISCORD_WEBHOOK_URL を設定 / 最初は USE_LLM=false 推奨）

python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## 実行
```bash
# 速報（アラート）
python -m src.main

# 朝ダイジェスト（JST 6:00はUTC 21:00）
MODE=digest python -m src.main
```

## cron 例
```cron
*/5 * * * * cd /path/fx_company_ai && /usr/bin/python3 -m src.main
0 21 * * * cd /path/fx_company_ai && MODE=digest /usr/bin/python3 -m src.main
```

## LLMを使う（任意）
- vLLMで Qwen/Qwen2.5-7B-Instruct を起動（model/serve_vllm.sh）
- `.env` で `USE_LLM=true`, `LLM_BASE_URL` を設定

## 注意
本配信は投資助言ではありません。情報の正確性は保証されません。
```
```

### `config/rules.yml`
```yaml
event_rules:
  policy: "(rate|hike|cut|QE|QT|policy|利上げ|利下げ|金融政策|声明|minutes|議事要旨|指針)"
  inflation: "(CPI|PPI|インフレ|消費者物価|物価指数)"
  jobs: "(NFP|雇用統計|失業率|非農業)"
  growth: "(GDP|成長率)"
  speech: "(speech|remarks|発言|講演)"
  risk: "(geopolit|地政学|リスク|停戦|軍事|制裁)"

hawkish_words:
  - "hike"
  - "higher for longer"
  - "タカ派"
  - "利上げ"
  - "インフレ高止まり"
  - "物価リスク上振れ"

dovish_words:
  - "cut"
  - "緩和"
  - "ハト派"
  - "利下げ"
  - "景気減速"
  - "ディスインフレ"

pair_map:
  USD: [USDJPY, EURUSD, GBPUSD, AUDUSD, NZDUSD, USDCAD, USDCHF, USDCNH]
  JPY: [USDJPY, EURJPY, GBPJPY, AUDJPY, NZDJPY, CADJPY, CHFJPY]
  EUR: [EURUSD, EURJPY, EURGBP, EURAUD, EURNZD, EURCHF, EURCAD]
  GBP: [GBPUSD, GBPJPY, EURGBP, GBPAUD, GBPNZD, GBPCHF, GBPCAD]
  AUD: [AUDUSD, AUDJPY, EURAUD, GBPAUD]
  NZD: [NZDUSD, NZDJPY, EURNZD, GBPNZD]
  CAD: [USDCAD, CADJPY, EURCAD, GBPCAD]
  CHF: [USDCHF, CHFJPY, EURCHF, GBPCHF]
```

### `src/__init__.py`
```python
# package marker
```

### `src/ingest.py`
```python
import feedparser, hashlib, time, sqlite3, os
from urllib.parse import urlparse
from typing import List, Dict

FEEDS = [
  "https://www.boj.or.jp/en/rss/whatsnew.xml",
  "https://www.federalreserve.gov/feeds/press_all.xml",
  "https://www.ecb.europa.eu/rss/press.html",
  "https://www.fxstreet.com/rss/news",
  "https://www.dailyforex.com/rss",
]

DB_PATH = "data/seen_urls.sqlite"

def _db():
    os.makedirs("data", exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE IF NOT EXISTS seen(id TEXT PRIMARY KEY, ts INTEGER)")
    return con

def _fp(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()

def pull_latest(max_items=100) -> List[Dict]:
    items = []
    for f in FEEDS:
        d = feedparser.parse(f)
        for e in d.entries[:max_items]:
            link = getattr(e, "link", "") or ""
            title = getattr(e, "title", "") or ""
            summ  = getattr(e, "summary", "") or ""
            published = getattr(e, "published", "") or ""
            items.append({
                "id": _fp(link or title),
                "source": urlparse(f).netloc,
                "title": title,
                "summary": summ,
                "link": link,
                "published": published
            })
    con = _db()
    fresh = []
    with con:
        for it in items:
            try:
                con.execute("INSERT INTO seen(id, ts) VALUES(?,?)", (it["id"], int(time.time())))
                fresh.append(it)
            except sqlite3.IntegrityError:
                pass
    return fresh
```

### `src/classify.py`
```python
import re, yaml
from typing import List

with open("config/rules.yml", "r", encoding="utf-8") as f:
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
```

### `src/scoring.py`
```python
import yaml
with open("config/rules.yml","r",encoding="utf-8") as f:
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
```

### `src/template.py`
```python
def render(item, ccys, pairs, labels, senti, impact):
    bias = "強気" if senti>0 else "弱気" if senti<0 else "中立"
    lab = ", ".join(labels)
    return f"""【超要約（仮）】{item['title']}
- 種別: {lab} / 想定バイアス: {bias} / 重要度: {impact:.1f}
- 対象通貨: {', '.join(ccys) or '（特定不可）'} / 影響ペア: {', '.join(pairs) or '（推定なし）'}
- 概要: {item['summary'][:220]}...

【If-Then】
- もし市場が「{bias}」継続 → {('通貨買い寄り' if senti>0 else '通貨売り寄り' if senti<0 else 'レンジ/次材料待ち')}
- 逆転条件：初動と逆方向＋出来高増ならフェイク注意

出典: {item['source']} | リンク: {item['link']}
※投資助言ではありません。"""
```

### `src/llm_client.py`
```python
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
```

### `src/summarizer.py`
```python
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
```

### `src/publish.py`
```python
import os, requests

WEBHOOK = os.getenv("DISCORD_WEBHOOK_URL")

def post_webhook(text: str):
    if not WEBHOOK: return
    requests.post(WEBHOOK, json={"content": text[:1900]}, timeout=15)
```

### `src/main.py`
```python
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
```

### `model/__init__.py`
```python
# package marker
```

### `model/train_lora.py`
```python
from datasets import load_dataset
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments
from peft import LoraConfig, get_peft_model
from trl import SFTTrainer
import torch

BASE = "Qwen/Qwen2.5-7B-Instruct"
ds = load_dataset("json", data_files={"train":"data/train.jsonl","eval":"data/val.jsonl"})

tok = AutoTokenizer.from_pretrained(BASE, use_fast=True)
base = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.bfloat16, device_map="auto")

def fmt(ex):
    sys = "あなたはFXニュースを初心者にも分かる日本語で要約するアナリストです。出力はJSON。"
    instr = (f"[入力]\n見出し:{ex['input']['headline']}\n本文:{ex['input']['body']}\n"
             f"数値:{ex['input']['metrics']}\n出力はJSON: ['summary_ja','bias','pairs','if_then','confidence']")
    tgt = ex["output"]
    resp = {
      "summary_ja": tgt["summary_ja"],
      "bias": tgt["bias"],
      "pairs": tgt["pairs"],
      "if_then": tgt["if_then"],
      "confidence": tgt["confidence"]
    }
    return {"text": f"<s>[SYSTEM]{sys}\n[INSTRUCTION]{instr}\n[RESPONSE]{resp}</s>"}

ds = ds.map(fmt)

peft_cfg = LoraConfig(r=8, lora_alpha=16, lora_dropout=0.05,
                      target_modules=["q_proj","k_proj","v_proj","o_proj","gate_proj","up_proj","down_proj"])

model = get_peft_model(base, peft_cfg)

trainer = SFTTrainer(
    model=model, tokenizer=tok,
    train_dataset=ds["train"], eval_dataset=ds["eval"],
    max_seq_length=2048,
    args=TrainingArguments(
        per_device_train_batch_size=2,
        gradient_accumulation_steps=8,
        num_train_epochs=2,
        learning_rate=2e-4,
        logging_steps=50, save_steps=500,
        bf16=True, output_dir="out/qwen-fx-lora"
    )
)
trainer.train()
model.save_pretrained("out/qwen-fx-lora")
tok.save_pretrained("out/qwen-fx-lora")
```

### `model/merge_lora.py`
```python
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

BASE = "Qwen/Qwen2.5-7B-Instruct"
ADAPTER = "out/qwen-fx-lora"
OUT = "out/qwen-fx-merged"

tok = AutoTokenizer.from_pretrained(BASE, use_fast=True)
base = AutoModelForCausalLM.from_pretrained(BASE, torch_dtype=torch.float16, device_map="auto")
peft = PeftModel.from_pretrained(base, ADAPTER)
merged = peft.merge_and_unload()
merged.save_pretrained(OUT)
tok.save_pretrained(OUT)
```

### `model/serve_vllm.sh`
```bash
#!/usr/bin/env bash
set -e
MODEL="Qwen/Qwen2.5-7B-Instruct"
PORT=8000
pip install "vllm==0.5.*"
python -m vllm.entrypoints.openai.api_server \
  --model $MODEL \
  --port $PORT \
  --gpu-memory-utilization 0.90
```

### `bot/__init__.py`
```python
# package marker
```

### `bot/discord_bot.py`
```python
import os, json, aiohttp, discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
BASE = os.getenv("LLM_BASE_URL","http://localhost:8000/v1")
MODEL = os.getenv("LLM_MODEL","Qwen/Qwen2.5-7B-Instruct")
TOKEN = os.getenv("DISCORD_BOT_TOKEN")

SYS = "あなたはFXニュースを初心者にも分かる日本語で要約するアナリストです。出力はJSON。"

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

@bot.command(name="fx")
async def fx(ctx, *, text:str):
    payload = {"model": MODEL, "messages":[
        {"role":"system","content":SYS},
        {"role":"user","content":text}],
        "temperature":0.2, "max_tokens":600}
    async with aiohttp.ClientSession() as s:
        async with s.post(f"{BASE}/chat/completions", json=payload, timeout=60) as r:
            res = await r.json()
    content = res["choices"][0]["message"]["content"]
    try:
        j = json.loads(content.replace("'", '"'))
        msg = (f"**要約**: {j['summary_ja']}\n**バイアス**: {j['bias']}\n"
               f"**ペア**: {', '.join(j.get('pairs',[]))}\n**If-Then**: {j['if_then']}\n"
               f"**確度**: {j.get('confidence',0):.2f}")
    except Exception:
        msg = content
    await ctx.reply(msg[:1900])

if __name__ == "__main__":
    bot.run(TOKEN)
```

### `data/train.jsonl` / `data/val.jsonl`（サンプル1件でOK）
```json
{"input":{"headline":"Sample headline","body":"Sample body","lang":"en","metrics":{"actual":null,"consensus":null,"previous":null},"time_iso":"2025-08-30T18:00:00Z"},"output":{"summary_ja":"サンプル要約","bias":"中立","pairs":["USDJPY"],"if_then":"様子見","confidence":0.5}}
```

---

## 3) 受け入れ条件（Claudeが満たすこと）

- `python -m src.main` 実行で、RSS取得→ルール要約→`DISCORD_WEBHOOK_URL` へ投稿される  
- `.env` の `MODE=digest` でダイジェストまとめて投稿  
- `.env` の `USE_LLM=true` 設定時、`LLM_BASE_URL` に OpenAI互換APIがある前提で要約切替  
- importエラーなし、相対インポートで動作  
- PEP8/最低限の例外処理OK（既存コードはそのまま利用で可）

---

## 4) 実行メモ（人間側）

```bash
cd fx_company_ai
cp .env.example .env     # Webhook URL等を設定
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 速報モード
python -m src.main

# ダイジェスト
MODE=digest python -m src.main
```
