"""LLM adapter for summarization."""

import os
from typing import Optional
from tenacity import retry, stop_after_attempt, wait_exponential
from loguru import logger

class LLMAdapter:
    """Adapter for LLM providers (Anthropic/OpenAI)."""
    
    def __init__(self, provider: str = "anthropic", model: Optional[str] = None):
        self.provider = provider.lower()
        
        if self.provider == "anthropic":
            self._init_anthropic(model)
        elif self.provider == "openai":
            self._init_openai(model)
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def _init_anthropic(self, model: Optional[str]):
        """Initialize Anthropic client."""
        try:
            from anthropic import Anthropic
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            
            self.client = Anthropic(api_key=api_key)
            self.model = model or "claude-3-5-sonnet-latest"
            logger.info(f"Initialized Anthropic with model: {self.model}")
        except ImportError:
            raise ImportError("anthropic package not installed")
    
    def _init_openai(self, model: Optional[str]):
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise ValueError("OPENAI_API_KEY not set")
            
            self.client = OpenAI(api_key=api_key)
            self.model = model or "gpt-4o-mini"
            logger.info(f"Initialized OpenAI with model: {self.model}")
        except ImportError:
            raise ImportError("openai package not installed")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30)
    )
    def generate(
        self,
        prompt: str,
        max_tokens: int = 600,
        temperature: float = 0.3
    ) -> str:
        """Generate text using LLM."""
        try:
            if self.provider == "anthropic":
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            
            elif self.provider == "openai":
                response = self.client.chat.completions.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise
    
    def summarize(
        self,
        prompt_template: str,
        **kwargs
    ) -> str:
        """Generate summary using template."""
        prompt = prompt_template.format(**kwargs)
        return self.generate(prompt, max_tokens=600)
    
    def generate_action_guide(
        self,
        prompt_template: str,
        **kwargs
    ) -> str:
        """Generate action guide using template."""
        prompt = prompt_template.format(**kwargs)
        return self.generate(prompt, max_tokens=400)