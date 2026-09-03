# Session records

Each `session-BIRDOS-*.json` file is one complete run: the manifest, the framing
chosen, the phenomenon, the output of every module, the researcher's decisions
and the rejected pathways.

`rejection_corpus.jsonl` is append-only, one JSON object per line, so it merges
cleanly across contributors and can be diffed in a pull request.

## Do not hand-write these files

They are the evidence that the pipeline does something. Record them:

    export ANTHROPIC_API_KEY=sk-ant-...
    python scripts/record_session.py --problem "..." --phenomenon 40

Then commit the result.
