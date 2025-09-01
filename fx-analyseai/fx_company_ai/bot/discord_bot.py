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