"""The phenomenon library.

A CSV rather than a database, so a reader can open it, diff it and cite a row.
The theme tags are a coarse retrieval index applied when the library was built.
They are not the basis on which the suggestion step selects, and the prompt
says so.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, asdict
from functools import lru_cache
from pathlib import Path

from .config import LIBRARY_CSV


@dataclass(frozen=True)
class Phenomenon:
    id: int
    name: str
    group: str
    description: str
    themes: tuple[str, ...]
    source: str = ""

    @property
    def text(self) -> str:
        """What module 1 receives."""
        return f"{self.name}. {self.description}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["themes"] = list(self.themes)
        return d


@lru_cache(maxsize=1)
def load_library(path: Path | None = None) -> tuple[Phenomenon, ...]:
    path = Path(path) if path else LIBRARY_CSV
    out = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            out.append(Phenomenon(
                id=int(row["id"]),
                name=row["name"].strip(),
                group=row["group"].strip(),
                description=row["description"].strip(),
                themes=tuple(t.strip() for t in row["themes"].split(";") if t.strip()),
                source=row.get("source", "").strip(),
            ))
    if not out:
        raise ValueError(f"Library at {path} is empty")
    return tuple(out)


@lru_cache(maxsize=1)
def library_hash(path: Path | None = None) -> str:
    """djb2 over the library rows, matching the browser build's hash so the two
    can be compared without a byte-level diff."""
    rows = "\n".join(
        f"{p.name}|{p.group}|{p.description}|{'; '.join(p.themes)}" for p in load_library(path)
    )
    h = 5381
    for ch in rows:
        h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF
    return format(h, "08x")


def groups() -> list[str]:
    seen: list[str] = []
    for p in load_library():
        if p.group not in seen:
            seen.append(p.group)
    return seen


def themes() -> list[str]:
    return sorted({t for p in load_library() for t in p.themes})


def get(pid: int) -> Phenomenon | None:
    return next((p for p in load_library() if p.id == pid), None)


def search(query: str = "", group: str | None = None, theme: str | None = None):
    """Client-side filtering for the browse view, not the suggestion step."""
    q = (query or "").strip().lower()
    hits = []
    for p in load_library():
        if group and p.group != group:
            continue
        if theme and theme not in p.themes:
            continue
        if q and not (q in p.name.lower() or q in p.description.lower()
                      or q in " ".join(p.themes).lower()):
            continue
        hits.append(p)
    return hits


def index() -> str:
    """Compact index handed to the suggestion step: names and tags, no
    descriptions. Sending 271 descriptions would cost more and invite
    selection on prose fluency rather than on structure."""
    return "\n".join(f"{p.id}|{p.name} [{p.group}]|{', '.join(p.themes)}" for p in load_library())
