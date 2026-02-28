"""
Groq Client - Fast LLM Inference

Uses Groq's free tier for ultra-fast inference.
Rate-limit aware: retries with exponential backoff on 429 errors.
"""

from typing import Optional, AsyncGenerator
import asyncio
import os
import time

from groq import Groq, AsyncGroq

from ..core.config import settings
from ..observability.logging import get_logger

logger = get_logger(__name__)

# Retry settings for Groq rate limits
_MAX_RETRIES = 3
_BASE_DELAY_S = 2.0   # Start with 2s delay
_MAX_DELAY_S = 30.0   # Cap at 30s


class GroqClient:
    """
    Client for Groq LLM API.
    
    Provides both sync and async interfaces with streaming support.
    Includes automatic retry with exponential backoff for rate limiting.
    """
    
    def __init__(self):
        api_key = settings.groq_api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not set")
        
        self.client = Groq(api_key=api_key)
        self.async_client = AsyncGroq(api_key=api_key)
    
    def generate(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generate a response synchronously with rate-limit retry.
        
        Args:
            prompt: User prompt
            model: Model to use (default from settings)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            system_prompt: Optional system prompt
            
        Returns:
            Generated text
        """
        model = model or settings.default_llm_model
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        for attempt in range(_MAX_RETRIES + 1):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                return response.choices[0].message.content
            except Exception as exc:
                if _is_rate_limit_error(exc) and attempt < _MAX_RETRIES:
                    delay = _get_retry_delay(exc, attempt)
                    logger.warning(
                        "groq.rate_limited",
                        attempt=attempt + 1,
                        delay_s=delay,
                        model=model,
                    )
                    time.sleep(delay)
                else:
                    raise
    
    async def agenerate(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        system_prompt: Optional[str] = None,
        response_format: Optional[dict] = None
    ) -> str:
        """Generate a response asynchronously with rate-limit retry."""
        model = model or settings.default_llm_model
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        for attempt in range(_MAX_RETRIES + 1):
            try:
                kwargs = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
                if response_format:
                    kwargs["response_format"] = response_format
                    
                response = await self.async_client.chat.completions.create(**kwargs)
                return response.choices[0].message.content
            except Exception as exc:
                if _is_rate_limit_error(exc) and attempt < _MAX_RETRIES:
                    delay = _get_retry_delay(exc, attempt)
                    logger.warning(
                        "groq.rate_limited",
                        attempt=attempt + 1,
                        delay_s=delay,
                        model=model,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
    
    async def astream(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        system_prompt: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Stream response tokens asynchronously.
        
        Yields individual tokens as they're generated.
        """
        model = model or settings.default_llm_model
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        stream = await self.async_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
    
    def health_check(self) -> bool:
        """Check if Groq API is available"""
        try:
            response = self.generate(
                "Say 'ok' in one word",
                model="llama-3.1-8b-instant",
                max_tokens=5
            )
            return len(response) > 0
        except Exception:
            return False


def _is_rate_limit_error(exc: Exception) -> bool:
    """Check if an exception is a Groq rate-limit error (HTTP 429)."""
    exc_str = str(exc).lower()
    return (
        "429" in exc_str
        or "rate_limit" in exc_str
        or "rate limit" in exc_str
        or hasattr(exc, "status_code") and getattr(exc, "status_code") == 429
    )


def _get_retry_delay(exc: Exception, attempt: int) -> float:
    """Calculate retry delay with exponential backoff, respecting Retry-After."""
    # Try to parse Retry-After header from the error
    retry_after = None
    if hasattr(exc, "headers"):
        retry_after = exc.headers.get("retry-after")  # type: ignore[union-attr]
    if hasattr(exc, "response") and hasattr(exc.response, "headers"):
        retry_after = exc.response.headers.get("retry-after")

    if retry_after:
        try:
            return min(float(retry_after), _MAX_DELAY_S)
        except (ValueError, TypeError):
            pass

    # Exponential backoff: 2s, 4s, 8s, capped at 30s
    return min(_BASE_DELAY_S * (2 ** attempt), _MAX_DELAY_S)

