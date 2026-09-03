"""The rejection corpus.

A structured record of theory-generation pathways that were rejected, each with
the stage that rejected it and the reason. Append-only and line-delimited so it
merges cleanly across contributors and can be diffed in a pull request.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .config import CORPUS_PATH, FILTER_ORDER


def append(entries: list[dict], path: Path | None = None) -> int:
    if not entries:
        return 0
    p = Path(path) if path else CORPUS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    return len(entries)


def load(path: Path | None = None) -> list[dict]:
    p = Path(path) if path else CORPUS_PATH
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def stats(entries: list[dict]) -> dict:
    """Where the pipeline rejects, and whether the two stages behave alike.

    Kept in the package rather than a notebook so the number in a paper and the
    number in the repository cannot drift apart.
    """
    by_filter = Counter(e.get("failed_filter") for e in entries)
    by_stage = Counter(e.get("stage") for e in entries)
    versions = Counter(e.get("schema_version", "unstamped") for e in entries)
    return {
        "total": len(entries),
        "by_stage": dict(by_stage),
        "by_filter": {f: by_filter.get(f, 0) for f in FILTER_ORDER},
        "suggestion_rejections": by_stage.get("suggestion", 0),
        "disputed": sum(1 for e in entries if e.get("second_opinion")),
        "phenomena_touched": len({e.get("phenomenon_id") for e in entries}),
        "schema_versions": dict(versions),
        "mixed_versions": len(versions) > 1,
    }
