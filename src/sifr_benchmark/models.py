"""
Model API integrations.
"""

import os
from typing import Optional

SUPPORTED_MODELS = {
    # OpenAI
    "gpt-4o": {"provider": "openai", "model": "gpt-4o"},
    "gpt-4o-mini": {"provider": "openai", "model": "gpt-4o-mini"},
    "gpt-4-turbo": {"provider": "openai", "model": "gpt-4-turbo"},
    # Anthropic
    "claude-sonnet": {"provider": "anthropic", "model": "claude-sonnet-4-20250514"},
    "claude-haiku": {"provider": "anthropic", "model": "claude-haiku-4-5-20251001"},
    "claude-opus": {"provider": "anthropic", "model": "claude-opus-4-20250514"},
}


def query_openai(model_id: str, prompt: str) -> dict:
    """Query OpenAI API."""
    try:
        from openai import OpenAI
    except ImportError:
        return {"error": "openai package not installed", "response": None, "tokens": 0}
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set", "response": None, "tokens": 0}
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=500,
        )
        
        return {
            "response": response.choices[0].message.content,
            "tokens": response.usage.total_tokens,
            "error": None,
        }
    except Exception as e:
        return {"error": str(e), "response": None, "tokens": 0}


def query_anthropic(model_id: str, prompt: str) -> dict:
    """Query Anthropic API."""
    try:
        from anthropic import Anthropic
    except ImportError:
        return {"error": "anthropic package not installed", "response": None, "tokens": 0}
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set", "response": None, "tokens": 0}
    
    try:
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model=model_id,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        
        total_tokens = response.usage.input_tokens + response.usage.output_tokens
        
        return {
            "response": response.content[0].text,
            "tokens": total_tokens,
            "error": None,
        }
    except Exception as e:
        return {"error": str(e), "response": None, "tokens": 0}


def query_model(model_key: str, prompt: str) -> dict:
    """
    Query a model by key.
    
    Args:
        model_key: Key from SUPPORTED_MODELS (e.g., "gpt-4o-mini")
        prompt: The prompt to send
        
    Returns:
        dict with keys: response, tokens, error
    """
    if model_key not in SUPPORTED_MODELS:
        return {
            "error": f"Unknown model: {model_key}",
            "response": None,
            "tokens": 0,
        }
    
    config = SUPPORTED_MODELS[model_key]
    provider = config["provider"]
    model_id = config["model"]
    
    if provider == "openai":
        return query_openai(model_id, prompt)
    elif provider == "anthropic":
        return query_anthropic(model_id, prompt)
    else:
        return {
            "error": f"Unknown provider: {provider}",
            "response": None,
            "tokens": 0,
        }
