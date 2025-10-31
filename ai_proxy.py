"""AI proxy service for forwarding requests to various AI providers."""

import httpx
from typing import Dict, Any, Optional
import json


class AIProxyService:
    """Proxy service for AI API requests."""
    
    def __init__(self):
        self.timeout = 60.0  # 60 seconds for AI responses
    
    async def chat_completion(
        self,
        provider_type: str,
        api_key: str,
        messages: list,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Send chat completion request to AI provider.
        
        Supports:
        - OpenAI (gpt-4, gpt-3.5-turbo, etc.)
        - Anthropic (claude-3, claude-2, etc.)
        - Google AI (gemini-pro, etc.)
        - DeepSeek (deepseek-chat, deepseek-reasoner)
        - Custom endpoints
        """
        provider_type = provider_type.lower()
        
        if provider_type == 'openai':
            return await self._openai_chat(api_key, messages, model, base_url, **kwargs)
        elif provider_type == 'anthropic':
            return await self._anthropic_chat(api_key, messages, model, **kwargs)
        elif provider_type == 'google':
            return await self._google_chat(api_key, messages, model, **kwargs)
        elif provider_type == 'deepseek':
            return await self._deepseek_chat(api_key, messages, model, **kwargs)
        elif provider_type == 'custom':
            return await self._custom_chat(api_key, messages, model, base_url, **kwargs)
        else:
            raise ValueError(f"Unsupported provider type: {provider_type}")
    
    async def _openai_chat(
        self,
        api_key: str,
        messages: list,
        model: Optional[str],
        base_url: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """OpenAI-compatible chat completion."""
        url = base_url or "https://api.openai.com/v1/chat/completions"
        model = model or "gpt-3.5-turbo"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    
    async def _anthropic_chat(
        self,
        api_key: str,
        messages: list,
        model: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Anthropic Claude chat completion."""
        url = "https://api.anthropic.com/v1/messages"
        model = model or "claude-3-sonnet-20240229"
        
        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 1024),
            **{k: v for k, v in kwargs.items() if k != "max_tokens"}
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    
    async def _google_chat(
        self,
        api_key: str,
        messages: list,
        model: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """Google AI (Gemini) chat completion."""
        model = model or "gemini-pro"
        url = f"https://generativelanguage.googleapis.com/v1/models/{model}:generateContent?key={api_key}"
        
        # Convert messages to Google format
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })
        
        payload = {
            "contents": contents,
            **kwargs
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    
    async def _deepseek_chat(
        self,
        api_key: str,
        messages: list,
        model: Optional[str],
        **kwargs
    ) -> Dict[str, Any]:
        """DeepSeek chat completion (OpenAI-compatible)."""
        url = "https://api.deepseek.com/chat/completions"
        model = model or "deepseek-chat"
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": messages,
            **kwargs
        }
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
    
    async def _custom_chat(
        self,
        api_key: str,
        messages: list,
        model: Optional[str],
        base_url: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Custom OpenAI-compatible endpoint."""
        if not base_url:
            raise ValueError("base_url required for custom provider")
        
        return await self._openai_chat(api_key, messages, model, base_url, **kwargs)
