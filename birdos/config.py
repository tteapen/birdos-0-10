"""Run configuration for BIRDOS.

Every parameter that could change an output is declared here and written into
each session record. If a reader cannot tell which settings produced a result,
the result is not auditable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROMPT_DIR = ROOT / "prompts"
SCHEMA_DIR = ROOT / "schemas"
CONTENT_DIR = ROOT / "content"
LIBRARY_CSV = ROOT / "data" / "phenomena" / "library.csv"
SESSION_DIR = ROOT / "sessions"
CORPUS_PATH = SESSION_DIR / "rejection_corpus.jsonl"

SCHEMA_VERSION = "3.0.0"
APP_VERSION = "0.1"

# Pin an explicit model string. A floating alias such as "latest" silently
# changes the instrument between runs.
#
# claude-sonnet-4-6 is pinned rather than a newer model because newer models
# reject non-default sampling parameters, and holding temperature fixed at 0
# matters more to this artifact than model recency. See README.
DEFAULT_MODEL = "claude-sonnet-4-6"
NO_SAMPLING_PARAMS = ("claude-sonnet-5", "claude-opus-5", "claude-fable-5", "claude-mythos-5")

FILTER_ORDER = ("abstraction", "feasibility", "novelty", "falsifiability", "usefulness")

FILTER_TESTS = {
    "abstraction": "Is the mapping mechanistic rather than merely verbal?",
    "feasibility": "Could an organizational researcher observe these constructs?",
    "novelty": "Does this depart from what the literature already claims?",
    "falsifiability": "Is there an observation that would count against it?",
    "usefulness": "Would knowing the answer change how scholars theorize?",
}

INTAKE_FIELDS = [
    ("actors", "who or what acts"),
    ("resources", "what is consumed or exchanged"),
    ("triggers", "what sets the process off"),
    ("timing", "over what period, in what sequence"),
    ("costs", "what the process costs the system"),
    ("outcomes", "what it produces"),
    ("constraints", "what limits or bounds it"),
]

PROMPT_FILES = {
    "framing": "framing.txt",
    "suggestion": "suggestion.txt",
    "module_1": "module_1_intake.txt",
    "module_2": "module_2_mechanism.txt",
    "module_3": "module_3_abstraction.txt",
    "module_4": "module_4_mapping.txt",
    "module_5": "module_5_filtering.txt",
    "module_6": "module_6_output.txt",
}

STAGES = [
    ("framing", "Frame the problem"),
    ("suggestion", "Choose a phenomenon"),
    ("module_1", "Phenomenon intake"),
    ("module_2", "Mechanism extraction"),
    ("module_3", "Abstraction"),
    ("module_4", "Organizational mapping"),
    ("module_5", "Filtering and scoring"),
    ("module_6", "Output and provenance"),
]


def supports_temperature(model: str) -> bool:
    """True if the model accepts a non-default temperature."""
    return not any(model.startswith(f) for f in NO_SAMPLING_PARAMS)


@dataclass
class RunConfig:
    model: str = DEFAULT_MODEL
    temperature: float = 0.0
    max_tokens: int = 1600
    # Four candidates is the most that fits the response budget once each
    # carries settings, antecedents, outcomes, boundary and disanalogy.
    n_candidates: int = 4
    n_suggestions: int = 6
    filters: tuple[str, ...] = FILTER_ORDER
    prompt_dir: Path = field(default=PROMPT_DIR)
    max_calls_per_session: int = 24

    @property
    def temperature_applied(self) -> bool:
        return supports_temperature(self.model)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["prompt_dir"] = str(self.prompt_dir)
        d["schema_version"] = SCHEMA_VERSION
        d["temperature_supported"] = self.temperature_applied
        if not self.temperature_applied:
            d["temperature"] = None
        return d


def api_key() -> str | None:
    """Key from the environment, or from Streamlit secrets when deployed.

    Never hard-code a key and never commit one. On Streamlit Community Cloud
    the key belongs in the app's Secrets panel.
    """
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    try:
        import streamlit as st

        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:
        return None
