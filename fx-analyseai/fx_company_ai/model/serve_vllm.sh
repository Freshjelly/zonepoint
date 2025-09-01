#!/usr/bin/env bash
set -e
MODEL="Qwen/Qwen2.5-7B-Instruct"
PORT=8000
pip install "vllm==0.5.*"
python -m vllm.entrypoints.openai.api_server \
  --model $MODEL \
  --port $PORT \
  --gpu-memory-utilization 0.90