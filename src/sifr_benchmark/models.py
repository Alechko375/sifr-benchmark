"""
Model API integrations with vision support.
"""
import os
import base64
from typing import Optional

SUPPORTED_MODELS = {
    # OpenAI
    "gpt-4o": {"provider": "openai", "model": "gpt-4o", "vision": True},
    "gpt-4o-mini": {"provider": "openai", "model": "gpt-4o-mini", "vision": True},
    "gpt-4-turbo": {"provider": "openai", "model": "gpt-4-turbo", "vision": True},
    # Anthropic
    "claude-sonnet": {"provider": "anthropic", "model": "claude-sonnet-4-20250514", "vision": True},
    "claude-haiku": {"provider": "anthropic", "model": "claude-haiku-4-5-20251001", "vision": True},
    "claude-opus": {"provider": "anthropic", "model": "claude-opus-4-20250514", "vision": True},
}

# Models that support vision input
VISION_MODELS = {k for k, v in SUPPORTED_MODELS.items() if v.get("vision")}


def query_openai(model_id: str, prompt: str, image: Optional[bytes] = None) -> dict:
    """Query OpenAI API with optional vision."""
    try:
        from openai import OpenAI
    except ImportError:
        return {"error": "openai package not installed", "response": None, "tokens": 0}
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set", "response": None, "tokens": 0}
    
    try:
        client = OpenAI(api_key=api_key)
        
        # Build message content
        if image:
            b64_image = base64.b64encode(image).decode("utf-8")
            content = [
                {"type": "text", "text": prompt},
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{b64_image}",
                        "detail": "high"
                    }
                }
            ]
        else:
            content = prompt
        
        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": content}],
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


def query_anthropic(model_id: str, prompt: str, image: Optional[bytes] = None) -> dict:
    """Query Anthropic API with optional vision."""
    try:
        from anthropic import Anthropic
    except ImportError:
        return {"error": "anthropic package not installed", "response": None, "tokens": 0}
    
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return {"error": "ANTHROPIC_API_KEY not set", "response": None, "tokens": 0}
    
    try:
        client = Anthropic(api_key=api_key)
        
        # Build message content
        if image:
            b64_image = base64.b64encode(image).decode("utf-8")
            content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64_image
                    }
                },
                {"type": "text", "text": prompt}
            ]
        else:
            content = prompt
        
        response = client.messages.create(
            model=model_id,
            max_tokens=500,
            messages=[{"role": "user", "content": content}],
        )
        
        total_tokens = response.usage.input_tokens + response.usage.output_tokens
        
        return {
            "response": response.content[0].text,
            "tokens": total_tokens,
            "error": None,
        }
    except Exception as e:
        return {"error": str(e), "response": None, "tokens": 0}


def query_model(model_key: str, prompt: str, image: Optional[bytes] = None) -> dict:
    """
    Query a model by key.
    
    Args:
        model_key: Key from SUPPORTED_MODELS (e.g., "gpt-4o-mini")
        prompt: The prompt to send
        image: Optional image bytes (PNG) for vision models
        
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
    
    # Check if vision is requested but not supported
    if image and not config.get("vision"):
        return {
            "error": f"Model {model_key} doesn't support vision",
            "response": None,
            "tokens": 0,
        }
    
    if provider == "openai":
        return query_openai(model_id, prompt, image)
    elif provider == "anthropic":
        return query_anthropic(model_id, prompt, image)
    else:
        return {
            "error": f"Unknown provider: {provider}",
            "response": None,
            "tokens": 0,
        }


def supports_vision(model_key: str) -> bool:
    """Check if a model supports vision input."""
    if model_key not in SUPPORTED_MODELS:
        return False
    return SUPPORTED_MODELS[model_key].get("vision", False)
