"""The BIRDOS pipeline.

    A  the researcher states a problem
    B  three theoretical framings are offered; the researcher chooses one
    C  phenomena are suggested; the researcher chooses one
    .  problem and phenomenon lock
    1..6  the six modules, run one at a time and re-runnable

Two decisions are never the model's: the framing and the phenomenon. Inside
the modules the researcher selects what proceeds, may edit an abstraction and
may dispute a verdict. Each intervention is recorded.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .client import Client, PipelineError, load_prompt, prompt_hashes
from .config import FILTER_ORDER, SCHEMA_VERSION, SESSION_DIR, RunConfig
from .library import Phenomenon, get, index, library_hash, load_library


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_run_id() -> str:
    return f"BIRDOS-{int(datetime.now(timezone.utc).timestamp() * 1000):X}"


# ------------------------------------------------------------------ setup

def frame(client: Client, problem: str, feedback: str = "") -> dict:
    """Three theoretical restatements of the researcher's problem."""
    if len(problem.strip()) < 15:
        raise PipelineError("State the problem in a sentence rather than a keyword.")
    fb = ""
    if feedback.strip():
        fb = ("\nTHE RESEARCHER REJECTED THE PREVIOUS THREE AND SAID:\n"
              f"{feedback.strip()}\n")
    prompt = load_prompt("framing").replace("{problem}", problem.strip()).replace("{feedback}", fb)
    return client.complete(prompt, "framing")


def suggest(client: Client, framing: str) -> tuple[list[dict], list[dict], int]:
    """Suggested phenomena, those set aside, and the count of unusable ids.

    The researcher makes the final choice. This step narrows the field.
    """
    prompt = load_prompt("suggestion").replace("{problem}", framing).replace("{index}", index())
    data = client.complete(prompt, "suggestion")

    hits, invalid = [], 0
    for s in data.get("suggestions", []):
        phen = get(int(s["id"]))
        if phen is None:
            invalid += 1  # a hallucinated id is a real failure mode; count it
            continue
        hits.append({"phenomenon": phen, "why": s["why"], "prior_use": s["prior_use"]})
    if not hits:
        raise PipelineError(
            "No usable library entries came back. State the problem more concretely, "
            "then search again."
        )

    aside = []
    for s in data.get("set_aside", []):
        phen = get(int(s["id"]))
        if phen is not None:
            aside.append({"phenomenon": phen, "why_not": s["why_not"]})
    return hits, aside, invalid


def suggestion_rejections(aside: list[dict], framing: str, run_id: str) -> list[dict]:
    """Corpus entries for phenomena the suggestion step set aside.

    Suggestion discards most of the library on every run. Recording only the
    filtering step's rejections would apply the project's central principle at
    one stage and abandon it at another.
    """
    at = now()
    return [{
        "schema_version": SCHEMA_VERSION,
        "stage": "suggestion",
        "run_id": run_id,
        "at": at,
        "phenomenon_id": a["phenomenon"].id,
        "phenomenon": a["phenomenon"].name,
        "problem": framing[:110],
        "failed_filter": "not suggested",
        "reason": a["why_not"],
        "second_opinion": None,
    } for a in aside]


# ----------------------------------------------------------------- modules

def module_1(client: Client, phenomenon: Phenomenon) -> dict:
    """Structured fields, with anything the source does not support marked unknown."""
    return client.complete(load_prompt("module_1").replace("{phenomenon}", phenomenon.text),
                           "module_1")


def module_2(client: Client, intake: dict) -> dict:
    """Alternative causal accounts, with near-duplicates identified."""
    text = "\n".join(f"{f['key']} [{f['status']}]: {f.get('value') or '-'}"
                     for f in intake.get("fields", []))
    return client.complete(load_prompt("module_2").replace("{intake}", text), "module_2")


def module_3(client: Client, mechanisms: list[dict]) -> dict:
    """The biology removed, and a judgment on whether a real claim survives."""
    if not mechanisms:
        raise PipelineError("Select at least one mechanism to carry forward.")
    text = "\n".join(f"{m['id']}: {m['account']}" for m in mechanisms)
    return client.complete(load_prompt("module_3").replace("{mechanisms}", text), "module_3")


def module_4(client: Client, abstractions: list[dict], framing: str,
             config: RunConfig | None = None) -> dict:
    """What would have to be true in an organization for the mechanism to hold.

    `abstractions` carry an `edited` flag so that hand-revised wording is
    marked in the prompt and recorded in the manifest.
    """
    config = config or RunConfig()
    if not abstractions:
        raise PipelineError("Select at least one abstraction to carry forward.")
    lines = []
    for a in abstractions:
        mark = " [EDITED]" if a.get("edited") else ""
        lines.append(f"{a['id']}{mark}: {a['statement']} "
                     f"[fails when: {a.get('boundary') or 'unstated'}]")
    n = min(config.n_candidates, max(3, len(abstractions) * 2))
    prompt = (load_prompt("module_4")
              .replace("{abstractions}", "\n".join(lines))
              .replace("{problem}", framing)
              .replace("{n}", str(n)))
    return client.complete(prompt, "module_4")


def module_5(client: Client, candidates: list[dict], framing: str) -> list[dict]:
    """Five criteria in a fixed order; a candidate is rejected by the first it fails."""
    text = "\n".join(f"{c['id']} [{c['ladder']}]: {c['proposition']}" for c in candidates)
    data = client.complete(
        load_prompt("module_5").replace("{candidates}", text).replace("{problem}", framing),
        "module_5")
    verdicts = data["verdicts"]
    for v in verdicts:
        if v["verdict"] == "reject" and not v.get("failed_filter"):
            raise PipelineError(
                f"{v['id']} was rejected without naming a criterion, so the corpus "
                "entry would be unusable."
            )
        if v.get("failed_filter") and v["failed_filter"] not in FILTER_ORDER:
            raise PipelineError(f"{v['id']} names an unknown criterion {v['failed_filter']!r}.")
    return verdicts


def module_6(client: Client, survivors: list[dict], phenomenon: Phenomenon,
             framing: str) -> dict:
    """Falsification tests and the source claims an expert should verify."""
    if not survivors:
        raise PipelineError(
            "Nothing survived the filters. Run module 4 again for fresh candidates, "
            "or revisit the abstractions."
        )
    text = "\n".join(f"{c['id']}: {c['proposition']}" for c in survivors)
    prompt = (load_prompt("module_6")
              .replace("{survivors}", text)
              .replace("{phenomenon}", phenomenon.text)
              .replace("{problem}", framing))
    return client.complete(prompt, "module_6")


# ------------------------------------------------------------- module six

def filtering_rejections(candidates: list[dict], verdicts: list[dict],
                         phenomenon: Phenomenon, framing: str, run_id: str) -> list[dict]:
    """Corpus entries for candidates a criterion excluded."""
    by_id = {c["id"]: c for c in candidates}
    at = now()
    out = []
    for v in verdicts:
        if v["verdict"] != "reject":
            continue
        c = by_id.get(v["id"], {})
        out.append({
            "schema_version": SCHEMA_VERSION,
            "stage": "module_5",
            "run_id": run_id,
            "at": at,
            "phenomenon_id": phenomenon.id,
            "phenomenon": phenomenon.name,
            "problem": framing[:110],
            "candidate_id": v["id"],
            "source_mechanism": c.get("source_mechanism"),
            "ladder": c.get("ladder"),
            "proposition": c.get("proposition"),
            "disanalogy": c.get("disanalogy"),
            "failed_filter": v["failed_filter"],
            "reason": v["reason"],
            "scores": v.get("scores"),
            "literature_overlap": v.get("literature_overlap"),
            "second_opinion": None,
        })
    return out


def merge_rejections(corpus: list[dict], run_id: str, stage: str,
                     entries: list[dict]) -> list[dict]:
    """Replace this run's entries for a stage rather than appending them.

    Without this, re-running a stage duplicates its rejections and inflates
    every count drawn from the corpus.
    """
    kept = [e for e in corpus if not (e.get("run_id") == run_id and e.get("stage") == stage)]
    return kept + entries


def build_manifest(config: RunConfig, run_id: str, started: str, problem: str,
                   framing: dict, rounds: int, phenomenon: Phenomenon, from_suggestions: bool,
                   intake: dict, mechanisms_offered: int, mechanisms_selected: list[str],
                   abstractions_selected: list[str], abstractions_edited: list[str],
                   candidates: list[dict], verdicts: list[dict], disputed: list[str],
                   corpus_size: int, usage: dict) -> dict:
    passed = sum(1 for v in verdicts if v["verdict"] == "pass")
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "model": config.model,
        "temperature": config.temperature if config.temperature_applied else None,
        "temperature_supported": config.temperature_applied,
        "max_tokens": config.max_tokens,
        "run_started": started,
        "run_completed": now(),
        "problem_as_typed": problem,
        "theoretical_problem": framing["statement"],
        "framing_chosen": framing.get("id"),
        "framing_rounds": rounds,
        "phenomenon_id": phenomenon.id,
        "phenomenon": phenomenon.name,
        "phenomenon_chosen_from": "suggested" if from_suggestions else "browsed",
        "library_size": len(load_library()),
        "library_hash": library_hash(),
        "filter_order": list(FILTER_ORDER),
        "prompt_hashes": prompt_hashes(),
        "researcher_decisions": {
            "mechanisms_offered": mechanisms_offered,
            "mechanisms_selected": mechanisms_selected,
            "abstractions_selected": abstractions_selected,
            "abstractions_edited": abstractions_edited,
            "verdicts_disputed": disputed,
        },
        "counts": {
            "candidates": len(candidates),
            "passed": passed,
            "rejected": len(verdicts) - passed,
            "corpus_entries": corpus_size,
        },
        "biology_confidence": intake.get("biology_confidence"),
        "usage": usage,
        "note": ("temperature 0 reduces but does not eliminate run to run variation, and the "
                 "API exposes no seed. Reproduction means re-running this manifest and "
                 "obtaining results a reader would recognise as the same."),
    }


# ------------------------------------------------------------- session io

def save_session(session: dict, directory: Path | None = None) -> Path:
    directory = Path(directory) if directory else SESSION_DIR
    directory.mkdir(parents=True, exist_ok=True)
    run_id = session["manifest"]["run_id"]
    path = directory / f"session-{run_id}.json"
    path.write_text(json.dumps(session, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def load_sessions(directory: Path | None = None) -> list[dict]:
    directory = Path(directory) if directory else SESSION_DIR
    if not directory.exists():
        return []
    out = []
    for p in sorted(directory.glob("session-*.json"), reverse=True):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except json.JSONDecodeError:
            continue
    return out
