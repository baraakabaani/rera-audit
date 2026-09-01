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
import re
import time
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


_RETRYABLE = ("rate limit", "429", "too many requests", "overloaded", "503", "502", "timeout")


def _retry_after(err: Exception) -> float:
    m = re.search(r"try again in ([\d.]+)s", str(err)) or re.search(r"retry.after[\"':\s]+([\d.]+)", str(err), re.I)
    return min(float(m.group(1)) + 0.5, 30.0) if m else 0.0


def chat_json(
    system: str,
    user: str,
    *,
    max_tokens: int = 4000,
    model: str | None = None,
    retries: int = 4,
) -> dict:
    """Send one prompt, parse the reply as a JSON object.

    Retries rate-limit / transient errors with the server-suggested delay
    (Groq free tier throttles aggressively). Raises after ``retries``.
    """
    r = resolve()
    if r is None:
        raise RuntimeError("no LLM provider configured")
    provider, default_model = r
    use_model = model or default_model

    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            if provider in ("groq", "openai"):
                client = _openai_client(provider)
                resp = client.chat.completions.create(
                    model=use_model,
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
                    model=use_model,
                    max_tokens=max_tokens,
                    system=system + "\n\nRespond with a single JSON object and nothing else.",
                    messages=[{"role": "user", "content": user}],
                )
                text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")

            text = text.strip()
            s, e = text.find("{"), text.rfind("}")
            if s != -1 and e != -1:
                text = text[s : e + 1]
            return json.loads(text)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            msg = str(exc).lower()
            if attempt < retries and any(k in msg for k in _RETRYABLE):
                time.sleep(_retry_after(exc) or (2.0 * (attempt + 1)))
                continue
            raise
    raise last_err  # pragma: no cover


def reset_cache() -> None:
    resolve.cache_clear()
