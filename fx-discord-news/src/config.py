"""Configuration management module."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field, HttpUrl, validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv
from loguru import logger

# Load environment variables
load_dotenv()

class LLMConfig(BaseModel):
    """LLM configuration."""
    provider: str = Field(default="anthropic")
    model: Dict[str, str] = Field(default_factory=dict)
    max_tokens_summary: int = Field(default=600)
    max_tokens_action: int = Field(default=400)
    temperature: float = Field(default=0.3)

class ScheduleConfig(BaseModel):
    """Schedule configuration."""
    morning_digest_jst: str = Field(default="06:00")
    night_digest_jst: str = Field(default="22:00")
    breaking_check_interval_minutes: int = Field(default=5)

class ThresholdConfig(BaseModel):
    """Threshold configuration."""
    breaking: int = Field(default=60, ge=0, le=100)
    digest: int = Field(default=40, ge=0, le=100)

class CacheConfig(BaseModel):
    """Cache configuration."""
    ttl_hours: int = Field(default=24)
    max_entries: int = Field(default=1000)

class RetryConfig(BaseModel):
    """Retry configuration."""
    max_attempts: int = Field(default=3)
    wait_exponential_multiplier: int = Field(default=2)
    wait_exponential_max: int = Field(default=30)

class LanguageConfig(BaseModel):
    """Language configuration."""
    preferred: str = Field(default="ja")
    translate_threshold: float = Field(default=0.7)

class Config(BaseModel):
    """Main configuration."""
    pairs_allowlist: List[str] = Field(default_factory=list)
    impact_thresholds: ThresholdConfig = Field(default_factory=ThresholdConfig)
    pair_score_threshold: int = Field(default=50)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    feeds: List[str] = Field(default_factory=list)
    disclaimer: str = Field(default="本投稿は教育目的であり、投資助言ではありません。")
    cache: CacheConfig = Field(default_factory=CacheConfig)
    language: LanguageConfig = Field(default_factory=LanguageConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)

    @validator("llm", pre=True)
    def expand_llm_provider(cls, v):
        """Expand environment variable in LLM provider."""
        if isinstance(v, dict) and "provider" in v:
            provider = v["provider"]
            if provider.startswith("${") and provider.endswith("}"):
                env_var = provider[2:-1]
                v["provider"] = os.getenv(env_var, "anthropic")
        return v

class Settings(BaseSettings):
    """Environment settings."""
    discord_webhook_beginner: str = Field(default="")
    discord_webhook_pro: str = Field(default="")
    provider: str = Field(default="anthropic")
    anthropic_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)
    tz: str = Field(default="Asia/Tokyo")
    log_level: str = Field(default="INFO")

    class Config:
        env_file = ".env"
        case_sensitive = False

def load_config(config_path: Path = Path("config.yaml")) -> Config:
    """Load configuration from YAML file."""
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return Config(**data)
    except FileNotFoundError:
        logger.warning(f"Config file not found: {config_path}. Using defaults.")
        return Config()
    except Exception as e:
        logger.error(f"Failed to load config: {e}")
        return Config()

def get_settings() -> Settings:
    """Get environment settings."""
    return Settings()

# Global instances
config = load_config()
settings = get_settings()

# Configure logging
logger.remove()
logger.add(
    "logs/fx-news.log",
    rotation="1 day",
    retention="7 days",
    level=settings.log_level,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}"
)
logger.add(
    lambda msg: print(msg, end=""),
    level=settings.log_level,
    format="{time:HH:mm:ss} | {level} | {message}"
)