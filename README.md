# BIRDOS

**Bioinspired Research Design for Organization Science.** A protocol for generating
candidate theoretical propositions by transferring causal mechanisms from biology to
organizational settings, and for keeping a record of the pathways that were rejected
along the way.

This repository holds the reference implementation: a Streamlit application, the
phenomenon library, the prompts as files, the schemas every response is validated
against, and the tests.

---

## The workflow

    A  the researcher states an organizational problem
    B  three theoretical framings are offered; the researcher chooses one
    C  phenomena are suggested; the researcher chooses one
    .  problem and phenomenon lock
    1  phenomenon intake          structured fields, unknowns marked
    2  mechanism extraction       alternative causal accounts, near-duplicates flagged
    3  abstraction                the biology removed, specificity judged
    4  organizational mapping     what would have to be true in an organization
    5  filtering and scoring      five criteria in a fixed order
    6  output and provenance      falsification tests, derivation, and the record

Two decisions are never the tool's: which framing to adopt and which phenomenon to
use. Inside the modules the researcher selects which mechanisms proceed, may edit an
abstraction before it is mapped, and may dispute any verdict. Every intervention is
recorded in the run manifest, so a later reader can separate the researcher's judgment
from the tool's suggestions.

**Rejections are recorded at two stages.** The suggestion step discards most of the
library on every run, and those discards enter the corpus alongside the candidates a
criterion rejects later. Applying the principle at one stage and not the other would
undercut the argument the corpus is meant to support.

---

## Quickstart

```bash
git clone <your-repo-url> && cd birdos
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

export ANTHROPIC_API_KEY=sk-ant-...                    # Windows: set ANTHROPIC_API_KEY=...
streamlit run app.py
```

The tests need no API key:

```bash
pip install pytest jsonschema
python -m pytest tests/ -q
```

---

## Deploying to Streamlit Community Cloud

**1. Check `.gitignore` before the first commit.** It excludes `.env` and
`.streamlit/secrets.toml`. Confirm with `git status` that neither appears. A key
committed once stays in the history; if it happens, revoke the key in the Anthropic
Console rather than only deleting the line.

**2. Push to a public GitHub repository.** Public is a requirement of the artifact
criterion, not a preference.

**3. Deploy.** Sign in at [share.streamlit.io](https://share.streamlit.io), choose the
repository, set the main file to `app.py`, deploy. Most first-deploy failures are a
missing or wrong `requirements.txt`; this one is correct.

**4. Add secrets.** In the app dashboard, open Settings then Secrets and paste the
contents of `.streamlit/secrets.toml.example` with real values.

**5. Note the free tier.** Community Cloud sleeps inactive apps, so a first visitor
sees a brief waking screen.

### Spending controls

Four layers, weakest to strongest: a conservative `max_tokens`; a per-session call cap
in `RunConfig.max_calls_per_session`; a password in Secrets if you gate the deployment;
and a prepaid credit ceiling with auto-reload disabled in the Anthropic Console. Only
the last is a real cap. A full pass is eight calls, and the suggestion step sends the
whole library index, so it costs more than the others.

---

## Why this model

`birdos/config.py` pins `claude-sonnet-4-6`. Newer models reject non-default sampling
parameters and return an error if temperature is set, and holding the sampling
parameter fixed at 0 matters more to this artifact than model recency.

If you migrate, `supports_temperature()` detects the constraint, omits the parameter,
and records `"temperature_supported": false` in the manifest rather than claiming a
setting that was never applied. Never pin a floating alias such as `latest`: it changes
the instrument between runs without any record that it did.

**What reproducibility means here.** Temperature 0 reduces but does not eliminate run
to run variation, and the API exposes no seed. Reproduction means re-running a recorded
manifest against the same pinned model and prompt hashes and obtaining results a reader
would recognise as the same, not identical text. The manifest says so in its own note.

---

## Repository map

```
app.py                      the Streamlit application
birdos/
  config.py                 pinned model, filter order, run parameters, paths
  library.py                the phenomenon library, search, retrieval index
  client.py                 API access, prompt loading, schema validation
  pipeline.py               framing, suggestion, the six modules, manifests
  corpus.py                 the rejection corpus and its statistics
  content.py                worked examples, sample problems, documentation
prompts/                    the eight prompts, verbatim, one file per stage
schemas/                    the schema every stage output is validated against
content/                    documentation and the three worked examples
data/phenomena/library.csv  the library: open it, diff it, cite a row
sessions/                   recorded runs and rejection_corpus.jsonl
scripts/record_session.py   command line runs, including unattended batches
tests/                      offline tests; no API key required
```

The prompts here are byte-identical to those in the browser build, and both hash them
with the same function, so a reader can confirm the two run the same instructions
without a manual diff.

---

## Building the corpus systematically

The application is interactive by design. For corpus construction, where the
researcher's choices can be stated up front, use the script:

```bash
python scripts/record_session.py --problem "Why do firms keep unused capabilities?" \
    --phenomenon 40
python scripts/record_session.py --problem "..." --batch 40 162 3 114
```

A batch continues past a failed run and reports the failures at the end. Session
records and corpus entries are written to `sessions/`.

**Do not hand-write session files.** They are the evidence that the pipeline does
something, and a fabricated record is a fabricated result.

---

## What the tool does not do

It does not establish that a proposition is true; passing five criteria is a screen
against common defects, not evidence. It does not verify the biology, which is why
intake reports its confidence and module 6 lists what an expert should check. It does
not conduct a literature review; the overlap assessment is a prompt for the researcher
to check a specific idea, and it can be wrong. It does not choose the research question
or the phenomenon.

Responsibility for any claim that leaves the workflow rests with the researcher who
publishes it. The run record exists so the reasoning can be inspected by others, which
supports accountability rather than replacing it.

---

## Licence

MIT. See `LICENSE`.
