"""Tests that run without an API key.

Everything here is checkable offline: the library loads, the prompts match the
schemas that consume them, the filter order is fixed, malformed output is
rejected, and the corpus behaves under re-runs.
"""

from __future__ import annotations

import json
import pytest

from birdos import client, config, content, corpus, library, pipeline


# ---------------------------------------------------------------- library

def test_library_loads_completely():
    lib = library.load_library()
    assert len(lib) == 271
    assert all(p.name and p.description and p.themes for p in lib)
    assert len({p.id for p in lib}) == len(lib)


def test_index_covers_every_entry_without_descriptions():
    rows = library.index().splitlines()
    assert len(rows) == len(library.load_library())
    assert all(len(r.split("|")) == 3 for r in rows)


def test_search_filters_compose():
    marine = library.search(group="Marine")
    assert marine and all(p.group == "Marine" for p in marine)
    themed = library.search(theme="Resilience")
    assert themed and all("Resilience" in p.themes for p in themed)


def test_library_hash_is_stable():
    assert library.library_hash() == library.library_hash()
    assert len(library.library_hash()) == 8


# ---------------------------------------------------------------- prompts

def test_every_prompt_has_the_placeholders_its_stage_fills():
    expected = {
        "framing": ["{problem}", "{feedback}"],
        "suggestion": ["{problem}", "{index}"],
        "module_1": ["{phenomenon}"],
        "module_2": ["{intake}"],
        "module_3": ["{mechanisms}"],
        "module_4": ["{abstractions}", "{problem}", "{n}"],
        "module_5": ["{candidates}", "{problem}"],
        "module_6": ["{survivors}", "{phenomenon}", "{problem}"],
    }
    for name, holders in expected.items():
        text = client.load_prompt(name)
        for h in holders:
            assert h in text, f"{name} is missing {h}"


def test_filter_prompt_names_every_criterion_and_asks_for_scores():
    text = client.load_prompt("module_5")
    assert "scores" in text
    for f in config.FILTER_ORDER:
        assert f in text


def test_suggestion_prompt_records_what_it_set_aside():
    text = client.load_prompt("suggestion")
    assert "set_aside" in text and "why_not" in text


def test_intake_prompt_requires_unknown_rather_than_a_guess():
    assert "unknown" in client.load_prompt("module_1")


def test_prompt_hashes_match_the_browser_implementation():
    assert client.djb2("") == "00001505"
    assert set(client.prompt_hashes()) == set(config.PROMPT_FILES)
    assert all(len(h) == 8 for h in client.prompt_hashes().values())


# ----------------------------------------------------------------- config

def test_filter_order_is_fixed():
    assert config.FILTER_ORDER == (
        "abstraction", "feasibility", "novelty", "falsifiability", "usefulness")


def test_temperature_is_dropped_for_models_that_reject_it():
    assert config.supports_temperature("claude-sonnet-4-6")
    assert not config.supports_temperature("claude-sonnet-5")
    m = config.RunConfig(model="claude-sonnet-5").to_dict()
    assert m["temperature"] is None and m["temperature_supported"] is False


# -------------------------------------------------------------- responses

def test_extract_json_survives_fences_and_preamble():
    assert client.extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert client.extract_json('Here you go:\n{"a": 1}') == {"a": 1}


def test_truncated_json_raises_rather_than_guessing():
    with pytest.raises(client.PipelineError):
        client.extract_json('{"verdicts": [{"id": "C1", "verdi')


def test_schema_rejects_an_unknown_status_at_intake():
    bad = {"fields": [{"key": "actors", "value": "x", "status": "probably"}],
           "biology_confidence": "high"}
    with pytest.raises(client.PipelineError):
        client.validate(bad, "module_1")


def test_schema_accepts_a_well_formed_intake():
    good = {"fields": [{"key": "actors", "value": "seeds", "status": "stated"}],
            "biology_confidence": "medium", "confidence_note": "check viability"}
    assert client.validate(good, "module_1") == good


def test_error_messages_are_written_for_a_researcher():
    assert "rate limiting" in client.friendly(Exception("429 rate_limit_error"))
    assert "temporary" in client.friendly(Exception("503 overloaded"))
    assert "key was rejected" in client.friendly(Exception("401 authentication_error"))


# ------------------------------------------------------- corpus behaviour

def _candidates():
    return [{"id": "C1", "ladder": "mechanistic", "proposition": "P1", "disanalogy": "D1"},
            {"id": "C2", "ladder": "analogical", "proposition": "P2", "disanalogy": "D2"}]


def _verdicts():
    return [{"id": "C1", "verdict": "pass", "failed_filter": None, "reason": "holds"},
            {"id": "C2", "verdict": "reject", "failed_filter": "abstraction",
             "reason": "the word is doing the work"}]


def test_only_rejections_become_corpus_entries():
    phen = library.get(40)
    out = pipeline.filtering_rejections(_candidates(), _verdicts(), phen, "framing", "RUN1")
    assert len(out) == 1
    assert out[0]["candidate_id"] == "C2"
    assert out[0]["failed_filter"] == "abstraction"
    assert out[0]["schema_version"] == config.SCHEMA_VERSION


def test_re_running_a_stage_replaces_its_entries_rather_than_duplicating():
    phen = library.get(40)
    entries = pipeline.filtering_rejections(_candidates(), _verdicts(), phen, "f", "RUN1")
    c = pipeline.merge_rejections([], "RUN1", "module_5", entries)
    c = pipeline.merge_rejections(c, "RUN1", "module_5", entries)   # the re-run
    assert len(c) == 1


def test_a_second_run_does_not_disturb_the_first():
    phen = library.get(40)
    e1 = pipeline.filtering_rejections(_candidates(), _verdicts(), phen, "f", "RUN1")
    e2 = pipeline.filtering_rejections(_candidates(), _verdicts(), phen, "f", "RUN2")
    c = pipeline.merge_rejections(pipeline.merge_rejections([], "RUN1", "module_5", e1),
                                 "RUN2", "module_5", e2)
    assert len(c) == 2
    assert {x["run_id"] for x in c} == {"RUN1", "RUN2"}


def test_suggestion_rejections_enter_the_corpus_too():
    aside = [{"phenomenon": library.get(20), "why_not": "recoverability never happens"}]
    out = pipeline.suggestion_rejections(aside, "framing", "RUN1")
    assert out[0]["stage"] == "suggestion"
    assert out[0]["failed_filter"] == "not suggested"


def test_stats_split_by_stage_and_flag_mixed_versions(tmp_path):
    entries = [
        {"stage": "suggestion", "failed_filter": "not suggested", "phenomenon_id": 1,
         "schema_version": "3.0.0"},
        {"stage": "module_5", "failed_filter": "novelty", "phenomenon_id": 2,
         "schema_version": "3.0.0"},
        {"stage": "module_5", "failed_filter": "novelty", "phenomenon_id": 2},
    ]
    s = corpus.stats(entries)
    assert s["total"] == 3
    assert s["by_filter"]["novelty"] == 2
    assert s["suggestion_rejections"] == 1
    assert s["mixed_versions"] is True


def test_corpus_file_is_append_only(tmp_path):
    path = tmp_path / "corpus.jsonl"
    e = [{"stage": "module_5", "failed_filter": "novelty"}]
    assert corpus.append(e, path) == 1
    assert corpus.append(e, path) == 1
    assert len(corpus.load(path)) == 2


# ------------------------------------------------------------ stage guards

def test_module_three_refuses_an_empty_selection():
    with pytest.raises(client.PipelineError):
        pipeline.module_3(None, [])


def test_module_four_refuses_an_empty_selection():
    with pytest.raises(client.PipelineError):
        pipeline.module_4(None, [], "framing")


def test_module_six_refuses_when_nothing_survived():
    with pytest.raises(client.PipelineError):
        pipeline.module_6(None, [], library.get(40), "framing")


def test_framing_refuses_a_keyword():
    with pytest.raises(client.PipelineError):
        pipeline.frame(None, "capabilities")


# ----------------------------------------------------------------- content

def test_worked_examples_are_internally_consistent():
    for w in content.worked_examples():
        ids = {p[0] for p in w["props"]}
        assert w["survivor"] in ids, f"example {w['n']} survivor is not among its candidates"
        assert {v[0] for v in w["verdicts"]} == ids
        for cand in w["candidates"]:
            assert library.get(cand[0]) is not None, f"library id {cand[0]} does not exist"


def test_sample_problems_match_the_worked_examples():
    assert content.sample_problems() == [w["question"] for w in content.worked_examples()]


def test_documentation_is_present_and_sectioned():
    doc = content.documentation()
    assert doc.count("\n## ") >= 10
    assert "Penrose" in doc and "Gentner" in doc


def test_manifest_records_the_researcher_decisions():
    phen = library.get(40)
    m = pipeline.build_manifest(
        config.RunConfig(), "RUN1", pipeline.now(), "raw problem",
        {"id": "B", "statement": "signature"}, 2, phen, True,
        {"biology_confidence": "medium"}, 4, ["M1", "M2"], ["M1"], ["M1"],
        _candidates(), _verdicts(), ["C1"], 1,
        {"input_tokens": 10, "output_tokens": 5, "calls": 1})
    d = m["researcher_decisions"]
    assert d["mechanisms_selected"] == ["M1", "M2"]
    assert d["abstractions_edited"] == ["M1"]
    assert d["verdicts_disputed"] == ["C1"]
    assert m["framing_rounds"] == 2
    assert m["phenomenon_chosen_from"] == "suggested"
    assert m["library_hash"] == library.library_hash()
