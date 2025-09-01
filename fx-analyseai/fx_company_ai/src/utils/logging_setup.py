# src/utils/logging_setup.py
import json
import logging
import sys

class JsonFormatter(logging.Formatter):
    """Custom formatter to output logs as JSON"""
    def format(self, record):
        base = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            base["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(base, ensure_ascii=False)

def setup_logging(level: str = "INFO"):
    """Setup structured JSON logging"""
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(h)