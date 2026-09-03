"""Model access, prompt loading and response validation.

Three rules, all in service of auditability: prompts are files rather than
string literals, every response is validated against a schema before use, and
token usage is recorded so cost claims are measured rather than estimated.
"""

from __future__ import annotations

import hashlib
import json
import time
from functools import lru_cache

from .config import PROMPT_DIR, PROMPT_FILES, SCHEMA_DIR, RunConfig, api_key, supports_temperature


class PipelineError(RuntimeError):
    """Raised when a stage returns something the pipeline cannot use."""


@lru_cache(maxsize=None)
def load_prompt(name: str) -> str:
    if name not in PROMPT_FILES:
        raise KeyError(f"Unknown prompt {name!r}; expected one of {list(PROMPT_FILES)}")
    return (PROMPT_DIR / PROMPT_FILES[name]).read_text(encoding="utf-8")


def djb2(text: str) -> str:
    """The hash the browser build displays, reimplemented so the two agree."""
    h = 5381
    for ch in text:
        h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF
    return format(h, "08x")


def prompt_hashes() -> dict:
    return {k: djb2(load_prompt(k)) for k in PROMPT_FILES}


def prompt_details() -> dict:
    out = {}
    for k in PROMPT_FILES:
        t = load_prompt(k)
        out[k] = {"file": PROMPT_FILES[k], "djb2": djb2(t),
                  "sha256": hashlib.sha256(t.encode()).hexdigest()[:16]}
    return out


@lru_cache(maxsize=None)
def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def validate(payload: dict, schema_name: str) -> dict:
    """Validate against the stage's schema. jsonschema is required for the
    tests but optional at runtime, so a missing install degrades to a shape
    check rather than crashing a live session."""
    try:
        import jsonschema as js
    except ImportError:
        for key in load_schema(schema_name).get("required", []):
            if key not in payload:
                raise PipelineError(f"{schema_name}: response is missing {key!r}")
        return payload
    try:
        js.validate(payload, load_schema(schema_name))
    except js.ValidationError as e:
        raise PipelineError(f"{schema_name}: {e.message}") from e
    return payload


def extract_json(text: str) -> dict:
    """Pull the JSON object out of a response. Fences are tolerated; anything
    else is an error worth surfacing rather than silently repairing."""
    cleaned = text.replace("```json", "").replace("```", "").strip()
    a, b = cleaned.find("{"), cleaned.rfind("}")
    if a == -1 or b == -1:
        raise PipelineError("The response contained no JSON object.")
    try:
        return json.loads(cleaned[a:b + 1])
    except json.JSONDecodeError as e:
        raise PipelineError(
            f"The response was cut off before it finished ({e.msg}). "
            "Run the stage again, or shorten the input."
        ) from e


class Client:
    """Thin wrapper over the Anthropic Messages API."""

    def __init__(self, config: RunConfig | None = None, key: str | None = None):
        from anthropic import Anthropic

        self.config = config or RunConfig()
        resolved = key or api_key()
        if not resolved:
            raise PipelineError(
                "No API key. Set ANTHROPIC_API_KEY in your environment or in the "
                "Streamlit Secrets panel when deployed."
            )
        self._client = Anthropic(api_key=resolved)
        self.usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "seconds": 0.0}

    def complete(self, prompt: str, schema_name: str, max_tokens: int | None = None) -> dict:
        cfg = self.config
        kwargs = {
            "model": cfg.model,
            "max_tokens": max_tokens or cfg.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if supports_temperature(cfg.model):
            kwargs["temperature"] = cfg.temperature

        started = time.time()
        try:
            message = self._client.messages.create(**kwargs)
        except Exception as e:  # network, auth, rate limit
            raise PipelineError(friendly(e)) from e

        text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
        self.usage["calls"] += 1
        self.usage["input_tokens"] += message.usage.input_tokens
        self.usage["output_tokens"] += message.usage.output_tokens
        self.usage["seconds"] = round(self.usage["seconds"] + time.time() - started, 2)

        if message.stop_reason == "max_tokens":
            raise PipelineError(
                f"{schema_name}: the response hit the {kwargs['max_tokens']} token ceiling "
                "before it finished. Raise max_tokens in RunConfig."
            )
        return validate(extract_json(text), schema_name)


def friendly(e: Exception) -> str:
    """Errors a researcher can act on rather than status codes."""
    s = str(e)
    if "429" in s or "rate_limit" in s:
        return "The API is rate limiting this session. Wait about a minute, then try again."
    if "401" in s or "authentication" in s:
        return "The API key was rejected. Check the key in your environment or Secrets panel."
    if any(c in s for c in ("500", "502", "503", "529", "overloaded")):
        return "The API had a temporary problem. Trying again usually clears it."
    if "connection" in s.lower() or "timeout" in s.lower():
        return "Could not reach the API. Check the connection, then try again."
    return f"The call failed: {s}"
