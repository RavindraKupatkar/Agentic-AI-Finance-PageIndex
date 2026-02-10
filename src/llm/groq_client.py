"""
Groq Client - Fast LLM Inference

Uses Groq's free tier for ultra-fast inference.
"""

from typing import Optional, AsyncGenerator
import os

from groq import Groq, AsyncGroq

from ..core.config import settings


class GroqClient:
    """
    Client for Groq LLM API.
    
    Provides both sync and async interfaces with streaming support.
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
        Generate a response synchronously.
        
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
        
        response = self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return response.choices[0].message.content
    
    async def agenerate(
        self,
        prompt: str,
        model: str = None,
        max_tokens: int = 1024,
        temperature: float = 0.1,
        system_prompt: Optional[str] = None
    ) -> str:
        """Generate a response asynchronously."""
        model = model or settings.default_llm_model
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        response = await self.async_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature
        )
        
        return response.choices[0].message.content
    
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
