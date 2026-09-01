"""One LLM entry point for every provider the app can use.

Resolution order (``LLM_PROVIDER=auto``):

1. **Groq**  - ``GROQ_API_KEY`` set (free, OpenAI-compatible)
2. **OpenAI / compatible** - ``OPENAI_API_KEY`` or ``OPENAI_BASE_URL`` set
3. **Anthropic** - ``ANTHROPIC_API_KEY`` or an ``ant auth login`` profile

Nothing configured -> :func:`available` is ``False`` and callers fall back to
their deterministic path.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

from .. import config


@lru_cache(maxsize=1)
def resolve() -> tuple[str, str] | None:
    """Return (provider, model) or None."""
    want = config.LLM_PROVIDER
    if want == "off" or not config.LLM_ENABLED:
        return None

    def model_for(p: str) -> str:
        return config.LLM_MODEL or config._PROVIDER_DEFAULT_MODEL[p]

    if want in ("auto", "groq") and config.GROQ_API_KEY:
        return "groq", model_for("groq")
    if want in ("auto", "openai") and (os.environ.get("OPENAI_API_KEY") or config.OPENAI_BASE_URL):
        return "openai", model_for("openai")
    if want in ("auto", "anthropic") and _anthropic_creds():
        return "anthropic", model_for("anthropic")
    return None


def _anthropic_creds() -> bool:
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return True
    cfg = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return (cfg / "anthropic").exists()


def available() -> bool:
    return resolve() is not None


def provider_name() -> str:
    r = resolve()
    return f"{r[0]} ({r[1]})" if r else "none"


# --------------------------------------------------------------------------- #
def _openai_client(provider: str):
    from openai import OpenAI

    if provider == "groq":
        return OpenAI(api_key=config.GROQ_API_KEY, base_url=config.GROQ_BASE_URL)
    return OpenAI(base_url=config.OPENAI_BASE_URL or None)  # OPENAI_API_KEY from env


def chat_json(system: str, user: str, *, max_tokens: int = 4000) -> dict:
    """Send one prompt, parse the reply as a JSON object. Raises on failure."""
    r = resolve()
    if r is None:
        raise RuntimeError("no LLM provider configured")
    provider, model = r

    if provider in ("groq", "openai"):
        client = _openai_client(provider)
        resp = client.chat.completions.create(
            model=model,
            temperature=0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = resp.choices[0].message.content or "{}"
    else:  # anthropic
        import anthropic

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system + "\n\nRespond with a single JSON object and nothing else.",
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

    text = text.strip()
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return json.loads(text)


def reset_cache() -> None:
    resolve.cache_clear()
