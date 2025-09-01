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