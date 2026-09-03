"""BIRDOS - Streamlit application.

One path: state a problem, choose a framing, choose a phenomenon, then run the
six modules one at a time. Two decisions are always the researcher's and are
recorded as such.

Run locally:  streamlit run app.py
"""

from __future__ import annotations

import json
from datetime import datetime

import streamlit as st

from birdos import config as cfg
from birdos import content as content_mod
from birdos import corpus as corpus_mod
from birdos import library as lib
from birdos import pipeline as pipe
from birdos.client import Client, PipelineError, load_prompt, prompt_details

st.set_page_config(page_title="BIRDOS", page_icon="🐦", layout="centered",
                   initial_sidebar_state="collapsed")

FILTERS = cfg.FILTER_ORDER
TESTS = cfg.FILTER_TESTS

# --------------------------------------------------------------------- css

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Roboto:wght@300;400;500&family=Roboto+Mono&family=Space+Grotesk:wght@700&display=swap');
html, body, [class*="css"], .stApp { font-family: Roboto, arial, sans-serif; }
.stApp { background: #fff; }
.block-container { padding-top: 2rem; max-width: 820px; }
h1, h2, h3 { color: #202124; font-weight: 400; }
.bd-brand { display: flex; align-items: center; gap: 13px; margin-bottom: 2px; }
.bd-mark { font-family: 'Space Grotesk', Roboto, sans-serif; font-weight: 700;
           font-size: 34px; letter-spacing: -1px; color: #202124; line-height: 1; }
.bd-sub { font-size: 14px; color: #5f6368; font-weight: 300; letter-spacing: .02em; }
.bd-ver { font-size: 12px; color: #70757a; margin-top: 2px; }
.bd-lock { border: 1px solid #dadce0; border-radius: 8px; background: #fafafa;
           padding: 12px 15px; margin: 6px 0 18px; font-size: 13px; }
.bd-lock .lb { font-family: 'Roboto Mono', monospace; font-size: 11px; color: #70757a; }
.bd-pill { display: inline-block; font-size: 11px; background: #e6f4ea; color: #188038;
           border-radius: 3px; padding: 1px 7px; margin-left: 7px; }
.bd-plain { font-size: 13px; color: #4d5156; background: #f1f3f4; border-radius: 6px;
            padding: 9px 12px; margin-bottom: 12px; }
.bd-sig { border-left: 3px solid #188038; background: #f4faf6; padding: 12px 15px;
          margin-bottom: 12px; font-size: 14.5px; color: #202124; }
.bd-crumb { font-size: 12px; color: #70757a; }
.bd-name { font-size: 17px; color: #1a0dab; }
.bd-gl { font-size: 13.5px; color: #4d5156; margin: 2px 0 0; }
.bd-tag { display: inline-block; font-size: 11.5px; color: #5f6368; background: #f1f3f4;
          border-radius: 10px; padding: 2px 9px; margin: 6px 5px 0 0; }
.bd-badge { font-size: 11px; border-radius: 3px; padding: 1px 6px; margin-left: 8px; }
.bd-badge.rare { color: #188038; background: #e6f4ea; }
.bd-badge.moderate { color: #e37400; background: #fef7e0; }
.bd-badge.heavy { color: #d93025; background: #fce8e6; }
.bd-status { font-size: 11px; border-radius: 3px; padding: 1px 6px; margin-left: 7px; }
.bd-status.stated { background: #e6f4ea; color: #188038; }
.bd-status.inferred { background: #fef7e0; color: #e37400; }
.bd-status.unknown { background: #f1f3f4; color: #5f6368; }
.bd-flag { font-size: 11px; border-radius: 3px; padding: 1px 6px; margin-left: 7px; }
.bd-flag.thin { background: #fce8e6; color: #d93025; }
.bd-flag.sufficient { background: #e6f4ea; color: #188038; }
.bd-flag.dup { background: #fef7e0; color: #e37400; }
.bd-cand { border: 1px solid #dadce0; border-left-width: 4px; border-radius: 8px;
           padding: 14px 16px; margin-bottom: 12px; }
.bd-cand.keep { border-left-color: #188038; }
.bd-cand.cut { border-left-color: #d93025; background: #fcfcfc; }
.bd-cand.wait { border-left-color: #dadce0; }
.bd-cmeta { font-size: 11.5px; color: #5f6368; margin-bottom: 6px; }
.bd-lad { border: 1px solid #dadce0; border-radius: 3px; padding: 1px 7px; margin-left: 6px; }
.bd-lad.mechanistic { color: #188038; background: #e6f4ea; border-color: #ceead6; }
.bd-lad.relational { color: #e37400; background: #fef7e0; border-color: #feefc3; }
.bd-prop { font-size: 15px; color: #202124; margin: 0; }
.bd-cand.cut .bd-prop { color: #5f6368; text-decoration: line-through;
                        text-decoration-color: #f3b8b4; }
.bd-sub2 { font-size: 13px; color: #4d5156; margin: 8px 0 0; }
.bd-gates { display: flex; gap: 4px; margin-top: 10px; }
.bd-gate { flex: 1; height: 6px; border-radius: 2px; background: #f1f3f4; }
.bd-gate.ok { background: #188038; }
.bd-gate.no { background: #d93025; }
.bd-glab { display: flex; gap: 4px; margin-top: 4px; font-size: 10.5px; color: #5f6368; }
.bd-glab div { flex: 1; }
.bd-vd { font-size: 13px; margin-top: 8px; }
.bd-vd.keep { color: #188038; }
.bd-vd.cut { color: #d93025; }
div.stButton > button { border-radius: 4px; border: 1px solid #dadce0; color: #1a73e8;
                        background: #fff; font-size: 13px; }
div.stButton > button:hover { background: #f8fbff; border-color: #c6dafc; color: #1a73e8; }
div.stButton > button[kind="primary"] { background: #1a73e8; color: #fff; border: none;
                                        font-weight: 500; }
.stTextArea textarea, .stTextInput input { border-radius: 8px; border-color: #dadce0; }
</style>
""", unsafe_allow_html=True)

LOGO = """<svg width="34" height="31" viewBox="0 0 50 46" xmlns="http://www.w3.org/2000/svg">
<g fill="#202124"><circle cx="19" cy="23" r="14"/><path d="M30 18 L47 7 L31 27 Z"/>
<path d="M6 19 L-1 23 L6 27 Z"/></g><circle cx="13.5" cy="18" r="2.1" fill="#fff"/></svg>"""

# ------------------------------------------------------------------- state

DEFAULTS = {
    "screen": "run", "problem": "", "framings": None, "framing_note": "",
    "chosen_framing": None, "suggested_for": None, "rounds": 0,
    "suggestions": None, "set_aside": [], "phenomenon": None, "from_suggestions": True,
    "locked": False, "stage": 0, "run_id": None, "started": None,
    "m1": None, "m2": None, "m3": None, "m4": None, "m5": None, "m6": None,
    "picks": [], "abstractions": [], "overrides": {},
    "corpus": [], "calls": 0, "usage": {"input_tokens": 0, "output_tokens": 0, "calls": 0},
    "error": None, "browse": False,
}
for k, v in DEFAULTS.items():
    st.session_state.setdefault(k, v)

LIBRARY = lib.load_library()
CONF = cfg.RunConfig()
calls_left = CONF.max_calls_per_session - st.session_state.calls


def reset_run(keep_problem: bool = True) -> None:
    problem = st.session_state.problem if keep_problem else ""
    for k, v in DEFAULTS.items():
        if k in ("corpus", "calls", "usage", "screen"):
            continue
        st.session_state[k] = v() if callable(v) else v
    st.session_state.problem = problem


def client() -> Client | None:
    try:
        return Client(CONF)
    except PipelineError as e:
        st.session_state.error = str(e)
        return None


def spend(fn, *args, **kwargs):
    """Run one pipeline stage, recording usage and surfacing failures plainly."""
    if calls_left <= 0:
        st.session_state.error = (f"This session is capped at {CONF.max_calls_per_session} "
                                  "model calls. Reload to start a new session.")
        return None
    c = client()
    if c is None:
        return None
    try:
        result = fn(c, *args, **kwargs)
        st.session_state.error = None
    except PipelineError as e:
        st.session_state.error = str(e)
        result = None
    st.session_state.calls += c.usage["calls"]
    for k in ("input_tokens", "output_tokens", "calls"):
        st.session_state.usage[k] += c.usage[k]
    return result


# ------------------------------------------------------------------ header

head_l, head_r = st.columns([3, 1])
with head_l:
    st.markdown(f'<div class="bd-brand">{LOGO}<span class="bd-mark">BIRDOS</span></div>'
                f'<div class="bd-sub">Bioinspired Research Design for Organization Science</div>'
                f'<div class="bd-ver">Version {cfg.APP_VERSION} &nbsp;|&nbsp; '
                f'Schema {cfg.SCHEMA_VERSION}</div>', unsafe_allow_html=True)
with head_r:
    tokens = st.session_state.usage["input_tokens"] + st.session_state.usage["output_tokens"]
    st.caption(f"{calls_left} calls left" + (f"  \n{tokens:,} tokens" if tokens else ""))

screen = st.radio("Screen", ["Run", "Phenomena Library", "Worked examples", "Documentation"],
                  horizontal=True, label_visibility="collapsed",
                  index=["run", "library", "examples", "docs"].index(st.session_state.screen))
st.session_state.screen = {"Run": "run", "Phenomena Library": "library",
                           "Worked examples": "examples", "Documentation": "docs"}[screen]
st.divider()

if st.session_state.error:
    st.error(st.session_state.error)

# --------------------------------------------------------------- documentation

if st.session_state.screen == "docs":
    st.markdown(content_mod.documentation())
    with st.expander("Technical record: parameters and prompts"):
        st.table({
            "setting": ["model", "temperature", "schema", "library", "candidates per run",
                        "session cap"],
            "value": [CONF.model,
                      str(CONF.temperature) if CONF.temperature_applied else "not applied",
                      cfg.SCHEMA_VERSION,
                      f"{len(LIBRARY)} entries, hash {lib.library_hash()}",
                      str(CONF.n_candidates), f"{CONF.max_calls_per_session} calls"],
        })
        for key, meta in prompt_details().items():
            st.caption(f"{meta['file']} · djb2 {meta['djb2']} · sha256 {meta['sha256']}")
            st.code(load_prompt(key), language="text")
    st.stop()

# ------------------------------------------------------------------- library

if st.session_state.screen == "library":
    st.subheader("Phenomena Library")
    st.caption(
        "Browsing here is for reference. A phenomenon is chosen after the problem has been "
        "framed, so that the choice is made against a stated puzzle rather than in the abstract."
    )
    q = st.text_input("Search", placeholder=f"Search {len(LIBRARY)} phenomena",
                      label_visibility="collapsed")
    c1, c2 = st.columns(2)
    g = c1.selectbox("Group", ["All groups"] + lib.groups(), label_visibility="collapsed")
    t = c2.selectbox("Theme", ["Any theme"] + lib.themes(), label_visibility="collapsed")
    hits = lib.search(q, None if g == "All groups" else g, None if t == "Any theme" else t)
    st.caption(f"{len(hits)} of {len(LIBRARY)} shown")
    for p in hits[:60]:
        st.markdown(
            f'<div class="bd-crumb">birdos.library › {p.group.lower()} › entry {p.id}</div>'
            f'<div class="bd-name" style="color:#202124">{p.name}</div>'
            f'<p class="bd-gl">{p.description}</p>'
            + "".join(f'<span class="bd-tag">{x}</span>' for x in p.themes),
            unsafe_allow_html=True)
        st.write("")
    if len(hits) > 60:
        st.caption("Showing the first 60. Narrow the search to see the rest.")
    st.stop()

# ------------------------------------------------------------ worked examples

if st.session_state.screen == "examples":
    examples = content_mod.worked_examples()
    labels = [f"Example {w['n']}: {w['title']}" for w in examples]
    pick = st.radio("Example", labels, label_visibility="collapsed")
    w = examples[labels.index(pick)]
    st.markdown(f"### {w['title']}")
    st.markdown(f'<div class="bd-sig">{w["question"]}</div>', unsafe_allow_html=True)
    st.caption(
        "This worked example follows one problem through all six modules, from an ordinary "
        "statement of the difficulty to a proposition with a falsification test. It was "
        "composed by the authors to make the reasoning at each stage visible. It should be "
        "read as an illustration of the method and not as a record of any particular run.")
    st.write(w["reading"])

    st.markdown("**The framing chosen**")
    st.markdown(f'<div class="bd-sig">{w["signature"]}</div>', unsafe_allow_html=True)
    st.write(w["signatureNote"])

    st.markdown("**The phenomenon chosen**")
    st.table({"Entry": [c[1] for c in w["candidates"]],
              "Why it is a candidate": [c[2] for c in w["candidates"]],
              "Prior use": [c[3] for c in w["candidates"]],
              "": [c[4] for c in w["candidates"]]})
    st.write(w["chosenWhy"])

    st.markdown("**Module 1 · intake**")
    st.table({"Field": [r[0] for r in w["intake"]], "Content": [r[1] for r in w["intake"]],
              "Status": [r[2] for r in w["intake"]]})
    st.write(w["unknownNote"])

    st.markdown("**Module 2 · mechanisms**")
    st.table({"Id": [m[0] for m in w["mechanisms"]], "Causal account": [m[1] for m in w["mechanisms"]],
              "Carried": [m[2] for m in w["mechanisms"]]})

    st.markdown("**Module 3 · abstraction**")
    st.table({"Id": [a[0] for a in w["abstractions"]],
              "Stated without the biology": [a[1] for a in w["abstractions"]],
              "Verdict": [a[2] for a in w["abstractions"]]})

    st.markdown("**Module 4 · mapping**")
    st.table({"": [m[0] for m in w["mapping"]], " ": [m[1] for m in w["mapping"]]})
    st.table({"Id": [p[0] for p in w["props"]], "Candidate proposition": [p[2] for p in w["props"]],
              "Rung": [p[1] for p in w["props"]]})

    st.markdown("**Module 5 · filtering and scoring**")
    st.table({"Id": [v[0] for v in w["verdicts"]],
              "Outcome": [("survives" if v[1] == "pass" else f"rejected · {v[2]}")
                          for v in w["verdicts"]],
              "Reason": [v[3] for v in w["verdicts"]]})
    st.info(f"**Where the mapping breaks.** {w['disanalogy']}")

    st.markdown("**Module 6 · output and provenance**")
    survivor = next(p for p in w["props"] if p[0] == w["survivor"])
    st.table({"": ["proposition", "falsification", "design needs", "verify"],
              " ": [survivor[2], w["falsification"], w["design"], w["verify"]]})

    if st.button("Use this problem", type="primary"):
        reset_run(keep_problem=False)
        st.session_state.problem = w["question"]
        st.session_state.screen = "run"
        st.rerun()
    st.stop()

# ----------------------------------------------------------------- the run

if st.session_state.locked and st.session_state.phenomenon:
    p = st.session_state.phenomenon
    st.markdown(
        f'<div class="bd-lock"><div class="lb">LOCKED FOR THIS RUN · {st.session_state.run_id}</div>'
        f'<p style="margin:3px 0 0"><b>Problem.</b> {st.session_state.chosen_framing["statement"]}</p>'
        f'<p style="margin:3px 0 0"><b>Phenomenon.</b> {p.name}'
        f'<span class="bd-pill">{"suggested" if st.session_state.from_suggestions else "browsed"}'
        f' · chosen by you</span></p></div>', unsafe_allow_html=True)

done = st.session_state.stage
labels = [f"{'✓' if i < done else '●' if i == done else '○'} {name}"
          for i, (_, name) in enumerate(cfg.STAGES)]
st.caption("  ·  ".join(labels))

# ---- A: the problem ----
with st.expander("A · State the problem", expanded=not st.session_state.framings):
    st.caption("Write the puzzle as you would say it to a colleague. A causal situation "
               "carries further than a topic.")
    st.session_state.problem = st.text_area(
        "Problem", value=st.session_state.problem, height=90, label_visibility="collapsed",
        placeholder="What organizational problem do you want to study?")
    samples = content_mod.sample_problems()
    cols = st.columns(len(samples))
    for i, sample in enumerate(samples):
        if cols[i].button(f"Sample {i + 1}", key=f"s{i}", help=sample):
            st.session_state.problem = sample
            st.rerun()
    if st.button("Frame this problem", type="primary",
                 disabled=len(st.session_state.problem.strip()) < 15 or st.session_state.locked):
        with st.spinner("Rewriting the problem three ways"):
            res = spend(pipe.frame, st.session_state.problem)
        if res:
            st.session_state.framings = res.get("options", [])
            st.session_state.framing_note = res.get("note", "")
            st.session_state.chosen_framing = None
            st.session_state.rounds += 1
        st.rerun()

# ---- B: the framing ----
if st.session_state.framings:
    chosen = st.session_state.chosen_framing
    with st.expander("B · Choose a framing", expanded=not st.session_state.suggestions):
        st.markdown('<div class="bd-plain">A theoretical problem names what is puzzling, not '
                    'just what is happening. Choose the framing you want to work in, or say '
                    'what is wrong with all three and ask again. Prefer a statement that '
                    'could be false.</div>', unsafe_allow_html=True)
        opts = [f"{o['id']} · {o['statement']}" for o in st.session_state.framings]
        idx = st.radio("Framing", opts, label_visibility="collapsed",
                       index=opts.index(f"{chosen['id']} · {chosen['statement']}") if chosen else 0)
        sel = st.session_state.framings[opts.index(idx)]
        st.caption(f"Unit of analysis: {sel.get('level', '-')}. "
                   f"Commits you to: {sel.get('commits_to', '-')}")
        if st.session_state.framing_note:
            st.caption(f"What separates them: {st.session_state.framing_note}")

        feedback = st.text_area("None of these? Say what is wrong and try again.", height=68,
                                key="fb", disabled=st.session_state.locked)
        c1, c2, c3 = st.columns([2, 2, 3])
        if c1.button("Use this framing", type="primary", disabled=st.session_state.locked):
            st.session_state.chosen_framing = sel
            stale = st.session_state.suggested_for != sel["statement"]
            if stale:
                # Suggestions belong to a specific framing. A different framing
                # invalidates them.
                st.session_state.suggestions = None
                st.session_state.set_aside = []
                st.session_state.phenomenon = None
            if st.session_state.suggestions is None:
                with st.spinner(f"Reading all {len(LIBRARY)} library entries"):
                    res = spend(pipe.suggest, sel["statement"])
                if res:
                    hits, aside, invalid = res
                    st.session_state.suggestions = hits
                    st.session_state.set_aside = aside
                    st.session_state.suggested_for = sel["statement"]
                    st.session_state.run_id = st.session_state.run_id or pipe.new_run_id()
                    st.session_state.corpus = pipe.merge_rejections(
                        st.session_state.corpus, st.session_state.run_id, "suggestion",
                        pipe.suggestion_rejections(aside, sel["statement"],
                                                   st.session_state.run_id))
                    if invalid:
                        st.warning(f"{invalid} suggested id(s) were not in the library "
                                   "and were discarded.")
                    st.session_state.stage = 1
            st.rerun()
        if c2.button("Try three more", disabled=not feedback.strip() or st.session_state.locked):
            with st.spinner("Rewriting the problem three ways"):
                res = spend(pipe.frame, st.session_state.problem, feedback)
            if res:
                st.session_state.framings = res.get("options", [])
                st.session_state.framing_note = res.get("note", "")
                st.session_state.chosen_framing = None
                st.session_state.rounds += 1
            st.rerun()
        c3.caption(f"Round {st.session_state.rounds}")

# ---- C: the phenomenon ----
if st.session_state.suggestions:
    with st.expander("C · Choose a phenomenon", expanded=not st.session_state.locked):
        st.markdown('<div class="bd-plain">These are suggestions, not a selection. Take one, '
                    'or browse the whole library and pick something else. Prefer rarely used '
                    'sources: a familiar one lets a reader supply the mechanism from memory.'
                    '</div>', unsafe_allow_html=True)
        names, mapping = [], {}
        for s in st.session_state.suggestions:
            label = f"{s['phenomenon'].name}  ({s['prior_use']} prior use)"
            names.append(label)
            mapping[label] = (s["phenomenon"], True, s["why"])
        if st.checkbox("Browse the whole library instead", value=st.session_state.browse,
                       disabled=st.session_state.locked):
            st.session_state.browse = True
            q = st.text_input("Find", placeholder=f"Search {len(LIBRARY)} phenomena")
            for p in lib.search(q)[:40]:
                label = f"{p.name}  (library entry {p.id})"
                if label not in mapping:
                    names.append(label)
                    mapping[label] = (p, False, p.description)
        else:
            st.session_state.browse = False

        choice = st.radio("Phenomenon", names, label_visibility="collapsed",
                          disabled=st.session_state.locked)
        phen, from_sugg, why = mapping[choice]
        st.markdown(f'<p class="bd-gl">{why}</p><p class="bd-gl" style="color:#5f6368">'
                    f'{phen.description}</p>', unsafe_allow_html=True)

        if st.session_state.set_aside:
            with st.popover(f"{len(st.session_state.set_aside)} set aside, with reasons"):
                for a in st.session_state.set_aside:
                    st.markdown(f"**{a['phenomenon'].name}** — {a['why_not']}")

        if st.button("Lock in and begin", type="primary", disabled=st.session_state.locked):
            st.session_state.phenomenon = phen
            st.session_state.from_suggestions = from_sugg
            st.session_state.locked = True
            st.session_state.run_id = st.session_state.run_id or pipe.new_run_id()
            st.session_state.started = pipe.now()
            st.session_state.stage = 2
            with st.spinner("Structuring the phenomenon"):
                st.session_state.m1 = spend(pipe.module_1, phen)
            st.rerun()

# ---- modules ----
if st.session_state.locked:
    m1 = st.session_state.m1
    with st.expander("1 · Phenomenon intake", expanded=st.session_state.m2 is None):
        if m1:
            st.markdown('<div class="bd-plain">Fields marked <b>unknown</b> are not failures. '
                        'Every later module treats these as given, so a guess here reaches the '
                        'final proposition unchallenged.</div>', unsafe_allow_html=True)
            by_key = {f["key"]: f for f in m1.get("fields", [])}
            for key, hint in cfg.INTAKE_FIELDS:
                f = by_key.get(key, {"status": "unknown", "value": ""})
                st.markdown(
                    f"**{key}** <span class='bd-status {f['status']}'>{f['status']}</span>  \n"
                    f"{f.get('value') or '_not established_'}  \n"
                    f"<span class='bd-crumb'>{hint}</span>", unsafe_allow_html=True)
            st.caption(f"Biology confidence: {m1.get('biology_confidence')}. "
                       f"{m1.get('confidence_note', '')}")
        c1, c2 = st.columns([2, 5])
        if c1.button("Extract mechanisms" if m1 else "Run module 1", type="primary"):
            if not m1:
                with st.spinner("Structuring the phenomenon"):
                    st.session_state.m1 = spend(pipe.module_1, st.session_state.phenomenon)
            else:
                st.session_state.stage = 3
                with st.spinner("Generating alternative causal accounts"):
                    res = spend(pipe.module_2, m1)
                if res:
                    st.session_state.m2 = res
                    st.session_state.picks = [m["id"] for m in res.get("mechanisms", [])
                                              if not m.get("near_duplicate_of")]
                    st.session_state.m3 = st.session_state.m4 = None
                    st.session_state.m5 = st.session_state.m6 = None
            st.rerun()
        if m1 and c2.button("Re-run module 1"):
            with st.spinner("Structuring the phenomenon"):
                st.session_state.m1 = spend(pipe.module_1, st.session_state.phenomenon)
            st.rerun()

if st.session_state.m2:
    with st.expander("2 · Mechanism extraction", expanded=st.session_state.m3 is None):
        st.markdown('<div class="bd-plain">Choose which accounts proceed. Near-duplicates are '
                    'flagged and unticked by default; carrying both inflates the candidate '
                    'count without adding variety.</div>', unsafe_allow_html=True)
        picks = []
        for m in st.session_state.m2.get("mechanisms", []):
            dup = m.get("near_duplicate_of")
            label = f"**{m['id']}** {m['account']}"
            if st.checkbox(label, value=m["id"] in st.session_state.picks, key=f"mech{m['id']}"):
                picks.append(m["id"])
            bits = [f"Distinct because: {m.get('distinct_because', '-')}"]
            if dup:
                bits.append(f"near-duplicate of {dup}")
            if m.get("rests_on"):
                bits.append(f"rests on the {m['rests_on']} field")
            st.caption(" · ".join(bits))
        st.session_state.picks = picks
        if st.button("Abstract these", type="primary", disabled=not picks):
            st.session_state.stage = 4
            chosen = [m for m in st.session_state.m2["mechanisms"] if m["id"] in picks]
            with st.spinner("Removing the biology"):
                res = spend(pipe.module_3, chosen)
            if res:
                st.session_state.m3 = res
                st.session_state.abstractions = [
                    {"id": a["id"], "on": a.get("specificity") == "sufficient",
                     "statement": a["statement"], "original": a["statement"],
                     "boundary": a.get("boundary", "")}
                    for a in res.get("abstractions", [])]
                st.session_state.m4 = st.session_state.m5 = st.session_state.m6 = None
            st.rerun()

if st.session_state.m3:
    with st.expander("3 · Abstraction", expanded=st.session_state.m4 is None):
        st.markdown('<div class="bd-plain">Anything marked <b>thin</b> became vacuous once the '
                    'biology was removed. You may carry it forward anyway, and you may edit any '
                    'abstraction. Edits are marked in the prompt and recorded.</div>',
                    unsafe_allow_html=True)
        by_id = {a["id"]: a for a in st.session_state.m3.get("abstractions", [])}
        for a in st.session_state.abstractions:
            src = by_id.get(a["id"], {})
            spec = src.get("specificity", "sufficient")
            a["on"] = st.checkbox(f"**{a['id']}** carry forward "
                                  f"({spec})", value=a["on"], key=f"abs{a['id']}")
            a["statement"] = st.text_area(f"Abstraction {a['id']}", value=a["statement"],
                                          key=f"txt{a['id']}", height=76,
                                          label_visibility="collapsed")
            note = src.get("note", "")
            edited = a["statement"].strip() != a["original"].strip()
            st.caption(f"{note} · Fails when: {a.get('boundary', '-')}"
                       + ("  ·  edited by hand, recorded in the manifest" if edited else ""))
        if st.button("Map to organizations", type="primary",
                     disabled=not any(a["on"] for a in st.session_state.abstractions)):
            st.session_state.stage = 5
            chosen = [{"id": a["id"], "statement": a["statement"], "boundary": a.get("boundary"),
                       "edited": a["statement"].strip() != a["original"].strip()}
                      for a in st.session_state.abstractions if a["on"]]
            with st.spinner("Asking what would have to be true in an organization"):
                res = spend(pipe.module_4, chosen, st.session_state.chosen_framing["statement"],
                            CONF)
            if res:
                st.session_state.m4 = res
                st.session_state.m5 = st.session_state.m6 = None
                st.session_state.overrides = {}
            st.rerun()

if st.session_state.m4:
    with st.expander("4 · Organizational mapping", expanded=st.session_state.m5 is None):
        st.markdown('<div class="bd-plain">Candidates are deliberately uneven; module 5 does the '
                    'filtering. Read the disanalogy on each, which says where the biology stops '
                    'applying.</div>', unsafe_allow_html=True)
        for c in st.session_state.m4.get("candidates", []):
            st.markdown(
                f'<div class="bd-cand wait"><div class="bd-cmeta">{c["id"]}'
                f'<span class="bd-lad {c["ladder"]}">{c["ladder"]}</span> '
                f'from {c.get("source_mechanism", "-")} · conditions satisfiable: '
                f'{c.get("conditions_satisfiable", "-")}</div>'
                f'<p class="bd-prop">{c["proposition"]}</p>'
                f'<p class="bd-sub2"><b>Settings:</b> {c.get("settings", "-")} · '
                f'<b>Antecedents:</b> {c.get("antecedents", "-")}</p>'
                f'<p class="bd-sub2"><b>Outcomes:</b> {c.get("outcomes", "-")} · '
                f'<b>Boundary:</b> {c.get("boundary", "-")}</p>'
                f'<p class="bd-sub2"><b>Where it breaks:</b> {c.get("disanalogy", "-")}</p></div>',
                unsafe_allow_html=True)
        if st.button("Apply the filters", type="primary"):
            st.session_state.stage = 6
            with st.spinner("Applying the criteria in order"):
                res = spend(pipe.module_5, st.session_state.m4["candidates"],
                            st.session_state.chosen_framing["statement"])
            if res:
                st.session_state.m5 = res
                st.session_state.m6 = None
                st.session_state.overrides = {}
                st.session_state.corpus = pipe.merge_rejections(
                    st.session_state.corpus, st.session_state.run_id, "module_5",
                    pipe.filtering_rejections(st.session_state.m4["candidates"], res,
                                              st.session_state.phenomenon,
                                              st.session_state.chosen_framing["statement"],
                                              st.session_state.run_id))
            st.rerun()

if st.session_state.m5:
    with st.expander("5 · Filtering and scoring", expanded=st.session_state.m6 is None):
        st.caption("Green passed · red is the criterion that rejected it · grey was never "
                   "applied. Numbers are 1 to 5 scores for criteria that were applied.")
        verdicts = {v["id"]: v for v in st.session_state.m5}
        for c in st.session_state.m4["candidates"]:
            v = verdicts.get(c["id"])
            if not v:
                continue
            keep = v["verdict"] == "pass"
            fi = FILTERS.index(v["failed_filter"]) if v.get("failed_filter") in FILTERS else -1
            gates = "".join(
                f'<div class="bd-gate {"ok" if keep or (0 <= i < fi) else "no" if i == fi else ""}"></div>'
                for i in range(len(FILTERS)))
            scores = v.get("scores") or {}
            glab = "".join(f"<div>{f[:3]} {scores.get(f) or ''}</div>" for f in FILTERS)
            lit = v.get("literature_overlap") or {}
            verdict_text = ("Survives all five criteria. " if keep
                            else f"Rejected at {v.get('failed_filter')}. ") + v["reason"]
            st.markdown(
                f'<div class="bd-cand {"keep" if keep else "cut"}">'
                f'<div class="bd-cmeta">{c["id"]}<span class="bd-lad {c["ladder"]}">'
                f'{c["ladder"]}</span>'
                + (f' · literature: {lit.get("assessment")}' if lit else "") + '</div>'
                f'<p class="bd-prop">{c["proposition"]}</p>'
                f'<div class="bd-gates">{gates}</div><div class="bd-glab">{glab}</div>'
                f'<p class="bd-vd {"keep" if keep else "cut"}">'
                f'{verdict_text}</p>'
                + (f'<p class="bd-sub2"><b>Nearest established idea:</b> {lit.get("nearest")} '
                   f'— check this yourself.</p>' if lit.get("nearest") else "")
                + '</div>', unsafe_allow_html=True)

            existing = st.session_state.overrides.get(c["id"])
            if existing:
                st.caption(f"Second opinion recorded: should {existing['verdict']}. "
                           f"{existing['reason']}")
            else:
                with st.popover(f"Disagree with {c['id']}"):
                    reason = st.text_area(
                        f"Why should {c['id']} have been "
                        f"{'rejected' if keep else 'kept'}?", key=f"ov{c['id']}", height=90)
                    if st.button("Record disagreement", key=f"ovb{c['id']}",
                                 disabled=len(reason.strip()) < 10):
                        op = {"by": "researcher", "at": pipe.now(),
                              "verdict": "reject" if keep else "pass",
                              "reason": reason.strip()}
                        st.session_state.overrides[c["id"]] = op
                        for e in st.session_state.corpus:
                            if (e.get("candidate_id") == c["id"]
                                    and e.get("run_id") == st.session_state.run_id):
                                e["second_opinion"] = op
                        st.rerun()

        if st.button("Assemble output", type="primary"):
            st.session_state.stage = 7
            survivors = [c for c in st.session_state.m4["candidates"]
                         if verdicts.get(c["id"], {}).get("verdict") == "pass"]
            with st.spinner("Writing falsification tests"):
                st.session_state.m6 = spend(pipe.module_6, survivors,
                                            st.session_state.phenomenon,
                                            st.session_state.chosen_framing["statement"])
            st.rerun()

if st.session_state.m6:
    st.subheader("6 · Output and provenance")
    verdicts = {v["id"]: v for v in st.session_state.m5}
    by_id = {c["id"]: c for c in st.session_state.m4["candidates"]}
    for o in st.session_state.m6.get("outputs", []):
        c = by_id.get(o["id"], {})
        st.markdown(
            f'<div class="bd-cand keep"><div class="bd-cmeta">{o["id"]} · '
            f'{st.session_state.phenomenon.name} → {c.get("source_mechanism", "-")} → {o["id"]}'
            f'</div><p class="bd-prop">{c.get("proposition", "")}</p>'
            f'<p class="bd-sub2"><b>Falsification test:</b> {o["falsification_test"]}</p>'
            f'<p class="bd-sub2"><b>Design:</b> {o.get("design_note", "-")}</p>'
            f'<p class="bd-sub2"><b>Boundary:</b> {c.get("boundary", "-")}</p>'
            f'<p class="bd-sub2" style="color:#e37400"><b>Verify with a biologist:</b> '
            f'{o.get("verify_with_biologist", "-")}</p></div>', unsafe_allow_html=True)

    manifest = pipe.build_manifest(
        CONF, st.session_state.run_id, st.session_state.started, st.session_state.problem,
        st.session_state.chosen_framing, st.session_state.rounds, st.session_state.phenomenon,
        st.session_state.from_suggestions, st.session_state.m1,
        len(st.session_state.m2.get("mechanisms", [])), st.session_state.picks,
        [a["id"] for a in st.session_state.abstractions if a["on"]],
        [a["id"] for a in st.session_state.abstractions
         if a["statement"].strip() != a["original"].strip()],
        st.session_state.m4["candidates"], st.session_state.m5,
        list(st.session_state.overrides), len(st.session_state.corpus), st.session_state.usage)

    st.caption("The manifest records which decisions were yours: the framing you chose and how "
               "many rounds it took, whether the phenomenon was suggested or browsed, which "
               "mechanisms and abstractions you selected or edited, and which verdicts you "
               "disputed.")
    with st.expander("Run manifest"):
        st.json(manifest)

    session = {
        "manifest": manifest,
        "problem_as_typed": st.session_state.problem,
        "framings_offered": st.session_state.framings,
        "framing_chosen": st.session_state.chosen_framing,
        "suggestions": [{"id": s["phenomenon"].id, "why": s["why"],
                         "prior_use": s["prior_use"]} for s in (st.session_state.suggestions or [])],
        "set_aside": [{"id": a["phenomenon"].id, "why_not": a["why_not"]}
                      for a in st.session_state.set_aside],
        "phenomenon": st.session_state.phenomenon.to_dict(),
        "module_1": st.session_state.m1, "module_2": st.session_state.m2,
        "mechanisms_selected": st.session_state.picks,
        "module_3": st.session_state.m3, "abstractions": st.session_state.abstractions,
        "module_4": st.session_state.m4, "module_5": st.session_state.m5,
        "second_opinions": st.session_state.overrides, "module_6": st.session_state.m6,
        "corpus": st.session_state.corpus,
    }
    c1, c2 = st.columns(2)
    c1.download_button("Download the full run", json.dumps(session, indent=2, ensure_ascii=False),
                       file_name=f"{st.session_state.run_id}.json", mime="application/json",
                       type="primary")
    if c2.button("Start a new problem"):
        reset_run(keep_problem=False)
        st.rerun()

# ---- corpus ----
if st.session_state.corpus:
    st.divider()
    entries = st.session_state.corpus
    s = corpus_mod.stats(entries)
    st.subheader(f"Rejection corpus — {s['total']} this session")
    st.caption("Phenomena the suggestion step set aside, and candidates a criterion rejected. "
               "Session only; the durable corpus is recorded deliberately in the repository "
               "with scripts/record_session.py.")
    chart = {"suggestion": s["suggestion_rejections"], **s["by_filter"]}
    st.bar_chart(chart, height=200)
    with st.expander("Entries"):
        for e in entries[::-1]:
            st.markdown(f"`{e.get('failed_filter') or 'second opinion'}` · {e['phenomenon']}  \n"
                        f"{e.get('proposition') or e.get('reason')}")
            if e.get("second_opinion"):
                st.caption(f"You disagreed: {e['second_opinion']['reason']}")
    st.download_button("Download corpus (JSONL)",
                       "\n".join(json.dumps(e, ensure_ascii=False) for e in entries),
                       file_name=f"{st.session_state.run_id or 'birdos'}-rejections.jsonl",
                       mime="application/x-ndjson")

st.divider()
st.caption(f"A demonstration of the pipeline. Model {CONF.model}. Propositions are candidates "
           "for a researcher to develop or discard, not findings.")
