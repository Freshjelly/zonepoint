FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY . .

# Health check using import test
HEALTHCHECK --interval=60s --timeout=10s --retries=3 --start-period=30s \
    CMD python -c "import importlib; importlib.import_module('src.main')"

# Default command
CMD ["python", "-m", "src.main"]