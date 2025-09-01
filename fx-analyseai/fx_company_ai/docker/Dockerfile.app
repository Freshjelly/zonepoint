FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Tokyo \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      tzdata ca-certificates curl bash git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 依存インストール（ビルドキャッシュのため requirements を先にコピー）
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
 && pip install -r /app/requirements.txt

# アプリ本体コピー
COPY src /app/src
COPY config /app/config
COPY model /app/model
COPY data /app/data
COPY docker/entry_alerts.sh /app/docker/entry_alerts.sh
RUN chmod +x /app/docker/entry_alerts.sh

# 健康チェック：依存が正しく入っていればOK
HEALTHCHECK --interval=1m --timeout=10s --start-period=30s --retries=3 \
  CMD python -c "import feedparser; import yaml; import requests; print('ok')"

# 既定の実行はヘルプ表示に留める（composeで上書き）
CMD ["python","-c","print('Set entrypoint via docker-compose.yml')"]