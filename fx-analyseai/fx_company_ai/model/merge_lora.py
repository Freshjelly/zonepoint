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