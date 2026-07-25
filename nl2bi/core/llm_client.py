"""
Provider-agnostic LLM call: send a system/user prompt pair, get back parsed JSON.
"""

from typing import Any, Dict, Optional
import json
from openai import OpenAI

_JSON_ONLY_SUFFIX = "\n\nRespond with ONLY a JSON object, no other text."

DEFAULT_MODELS = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-haiku-latest",
    "local": "llama3.1",
}


def default_model_for(provider: str) -> str:
    """Sensible default model name for a given provider."""
    return DEFAULT_MODELS.get(provider, DEFAULT_MODELS["openai"])


def get_json_completion(
    provider: str,
    api_key: Optional[str],
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> Dict[str, Any]:
    """
    Send a system/user prompt pair to the given provider and parse a JSON response.

    Args:
        provider: One of "openai", "anthropic", "local" (Ollama)
        api_key: API key for the provider (unused for "local")
        model: Model name to use
        system_prompt: System prompt (should already ask for JSON-only output)
        user_prompt: User prompt

    Returns:
        Parsed JSON response as a dict
    """
    if provider == "openai":
        return _openai_json_completion(api_key, model, system_prompt, user_prompt)
    if provider == "anthropic":
        return _anthropic_json_completion(api_key, model, system_prompt, user_prompt)
    if provider == "local":
        return _ollama_json_completion(model, system_prompt, user_prompt)
    raise ValueError(f"Unsupported provider: {provider!r}")


def _openai_json_completion(api_key, model, system_prompt, user_prompt) -> Dict[str, Any]:
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return json.loads(response.choices[0].message.content)


def _anthropic_json_completion(api_key, model, system_prompt, user_prompt) -> Dict[str, Any]:
    try:
        import anthropic
    except ImportError as e:
        raise ImportError(
            "anthropic is required for llm='anthropic' - install with: pip install nl2bi[llm]"
        ) from e

    client = anthropic.Anthropic(api_key=api_key)
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt + _JSON_ONLY_SUFFIX,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return json.loads(response.content[0].text)


def _ollama_json_completion(model, system_prompt, user_prompt) -> Dict[str, Any]:
    # ponytail: Ollama exposes an OpenAI-compatible endpoint, so no new SDK needed
    client = OpenAI(api_key="ollama", base_url="http://localhost:11434/v1")
    response = client.chat.completions.create(
        model=model,
        max_tokens=1024,
        messages=[
            {"role": "system", "content": system_prompt + _JSON_ONLY_SUFFIX},
            {"role": "user", "content": user_prompt},
        ],
    )
    return json.loads(response.choices[0].message.content)
