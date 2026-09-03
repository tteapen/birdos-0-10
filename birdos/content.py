"""Static content shared with the browser build: worked examples and reference data."""

from __future__ import annotations

import json
from functools import lru_cache

from .config import CONTENT_DIR


@lru_cache(maxsize=1)
def worked_examples() -> list[dict]:
    return json.loads((CONTENT_DIR / "worked_examples.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def reference() -> dict:
    return json.loads((CONTENT_DIR / "reference.json").read_text(encoding="utf-8"))


def sample_problems() -> list[str]:
    return reference()["examples"]


@lru_cache(maxsize=1)
def documentation() -> str:
    return (CONTENT_DIR / "documentation.md").read_text(encoding="utf-8")
