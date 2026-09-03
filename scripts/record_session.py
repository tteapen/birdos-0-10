#!/usr/bin/env python3
"""Record complete runs from the command line.

The app is interactive by design. This script is for building the durable
corpus systematically, where the researcher's choices can be stated up front.

    export ANTHROPIC_API_KEY=sk-ant-...
    python scripts/record_session.py --problem "Why do firms keep unused capabilities?" \
        --phenomenon 40
    python scripts/record_session.py --problem "..." --batch 40 162 3 114
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from birdos import corpus, library, pipeline                      # noqa: E402
from birdos.client import Client, PipelineError                   # noqa: E402
from birdos.config import RunConfig                               # noqa: E402


def one_run(client: Client, config: RunConfig, problem: str, phen, framing: dict,
            rounds: int, from_suggestions: bool) -> dict:
    run_id = pipeline.new_run_id()
    started = pipeline.now()
    print(f"  {phen.name}", flush=True)

    m1 = pipeline.module_1(client, phen)
    m2 = pipeline.module_2(client, m1)
    # Unattended, carry every account that is not flagged as a near duplicate.
    mechs = [m for m in m2["mechanisms"] if not m.get("near_duplicate_of")]
    m3 = pipeline.module_3(client, mechs)
    abstractions = [{"id": a["id"], "statement": a["statement"],
                     "boundary": a.get("boundary"), "edited": False}
                    for a in m3["abstractions"] if a.get("specificity") == "sufficient"]
    if not abstractions:
        # Nothing survived abstraction. That is a result; record it and stop.
        print("    no abstraction retained sufficient specificity", file=sys.stderr)
        abstractions = [{"id": a["id"], "statement": a["statement"],
                         "boundary": a.get("boundary"), "edited": False}
                        for a in m3["abstractions"]]
    m4 = pipeline.module_4(client, abstractions, framing["statement"], config)
    m5 = pipeline.module_5(client, m4["candidates"], framing["statement"])

    rejections = pipeline.filtering_rejections(m4["candidates"], m5, phen,
                                               framing["statement"], run_id)
    survivors = [c for c in m4["candidates"]
                 if next((v for v in m5 if v["id"] == c["id"]), {}).get("verdict") == "pass"]
    m6 = pipeline.module_6(client, survivors, phen, framing["statement"]) if survivors else None

    manifest = pipeline.build_manifest(
        config, run_id, started, problem, framing, rounds, phen, from_suggestions, m1,
        len(m2["mechanisms"]), [m["id"] for m in mechs],
        [a["id"] for a in abstractions], [], m4["candidates"], m5, [],
        len(rejections), client.usage)

    session = {"manifest": manifest, "problem_as_typed": problem, "framing_chosen": framing,
               "phenomenon": phen.to_dict(), "module_1": m1, "module_2": m2,
               "mechanisms_selected": [m["id"] for m in mechs], "module_3": m3,
               "abstractions": abstractions, "module_4": m4, "module_5": m5,
               "module_6": m6, "corpus": rejections}
    path = pipeline.save_session(session)
    n = corpus.append(rejections)
    c = manifest["counts"]
    print(f"    {c['passed']} passed, {c['rejected']} rejected -> {path.name} (+{n} corpus)")
    return session


def main() -> int:
    ap = argparse.ArgumentParser(description="Record BIRDOS runs.")
    ap.add_argument("--problem", required=True, help="the organizational problem, in a sentence")
    ap.add_argument("--phenomenon", type=int, help="library id to use")
    ap.add_argument("--batch", nargs="+", type=int, metavar="ID",
                    help="library ids to run against the same problem, unattended")
    ap.add_argument("--framing", type=int, default=0,
                    help="which of the three framings to take, 0 based (default 0)")
    ap.add_argument("--model", default=None, help="override the pinned model")
    args = ap.parse_args()

    config = RunConfig(model=args.model) if args.model else RunConfig()
    try:
        client = Client(config)
    except PipelineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"model {config.model} · library {library.library_hash()} "
          f"· {len(library.load_library())} phenomena")

    try:
        framed = pipeline.frame(client, args.problem)
        options = framed["options"]
        for o in options:
            print(f"  [{o['id']}] {o['statement']}")
        framing = options[min(args.framing, len(options) - 1)]
        print(f"using framing {framing['id']}")

        ids = args.batch or ([args.phenomenon] if args.phenomenon else [])
        from_suggestions = False
        if not ids:
            hits, aside, _ = pipeline.suggest(client, framing["statement"])
            for h in hits:
                print(f"  suggested {h['phenomenon'].id:>3} {h['phenomenon'].name} "
                      f"[{h['prior_use']}]")
            corpus.append(pipeline.suggestion_rejections(aside, framing["statement"],
                                                         pipeline.new_run_id()))
            ids = [hits[0]["phenomenon"].id]
            from_suggestions = True

        failed = []
        for pid in ids:
            phen = library.get(pid)
            if not phen:
                failed.append((pid, "no such library id"))
                continue
            try:
                one_run(client, config, args.problem, phen, framing, 1, from_suggestions)
            except PipelineError as e:
                # One bad run must not abandon the batch.
                failed.append((pid, str(e)))
                print(f"    failed: {e}", file=sys.stderr)
        if failed:
            print(f"\n{len(failed)} of {len(ids)} runs failed:", file=sys.stderr)
            for pid, why in failed:
                print(f"  {pid}: {why}", file=sys.stderr)
    except PipelineError as e:
        print(f"pipeline error: {e}", file=sys.stderr)
        return 1

    u = client.usage
    print(f"\ndone. {u['calls']} calls · {u['input_tokens']} in / {u['output_tokens']} out tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
