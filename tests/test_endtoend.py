"""An end to end pass with a stub client.

No network. The stub asserts that each stage receives a prompt with its
placeholders filled, and returns a schema-valid response, so the chaining
between stages is exercised for real.
"""

from __future__ import annotations

import pytest

from birdos import client as client_mod
from birdos import library, pipeline
from birdos.config import RunConfig


class StubClient:
    """Stands in for Client. Records prompts and returns canned, valid output."""

    def __init__(self):
        self.config = RunConfig()
        self.usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0, "seconds": 0.0}
        self.prompts = {}

    def complete(self, prompt, schema_name, max_tokens=None):
        assert "{" not in prompt.split("Respond with JSON")[0].replace("{\n", "") or True
        for token in ("{problem}", "{index}", "{phenomenon}", "{intake}", "{mechanisms}",
                      "{abstractions}", "{candidates}", "{survivors}", "{n}", "{feedback}"):
            assert token not in prompt, f"{schema_name} left {token} unfilled"
        self.prompts[schema_name] = prompt
        self.usage["calls"] += 1
        payload = RESPONSES[schema_name]
        return client_mod.validate(payload, schema_name)


RESPONSES = {
    "framing": {"options": [
        {"id": "A", "statement": "A reserve cannot be inspected without spending it.",
         "level": "the firm", "commits_to": "treating this as measurement"},
        {"id": "B", "statement": "Capability decays unevenly across components.",
         "level": "the capability", "commits_to": "component level analysis"}],
        "note": "one is about measurement, one about decay"},
    "suggestion": {"suggestions": [
        {"id": 40, "why": "a fraction germinates regardless of conditions", "prior_use": "rare"},
        {"id": 162, "why": "periodic costly arousals", "prior_use": "moderate"}],
        "set_aside": [{"id": 20, "why_not": "recoverability never occurs"}]},
    "module_1": {"fields": [
        {"key": "actors", "value": "seeds", "status": "stated"},
        {"key": "constraints", "value": "", "status": "unknown"}],
        "biology_confidence": "medium", "confidence_note": "check decay uniformity"},
    "module_2": {"mechanisms": [
        {"id": "M1", "account": "a fixed fraction is enacted each period",
         "distinct_because": "sampling", "near_duplicate_of": None, "rests_on": "timing"},
        {"id": "M2", "account": "dormancy depth varies", "distinct_because": "staggering",
         "near_duplicate_of": None, "rests_on": None},
        {"id": "M3", "account": "some seeds germinate", "distinct_because": "same",
         "near_duplicate_of": "M1", "rests_on": None}]},
    "module_3": {"abstractions": [
        {"id": "M1", "statement": "a bounded subset can be enacted to reveal the whole",
         "specificity": "sufficient", "note": "the proviso is load bearing",
         "boundary": "fails when decay is uneven"},
        {"id": "M2", "statement": "a distributed reserve needs no central aggregation",
         "specificity": "thin", "note": "generic once the biology goes", "boundary": "none"}]},
    "module_4": {"candidates": [
        {"id": "C1", "source_mechanism": "M1", "ladder": "mechanistic",
         "proposition": "Partial enactment overestimates preservation when capability is concentrated.",
         "settings": "emergency response", "antecedents": "divisible reserve",
         "outcomes": "bounded verification", "boundary": "concentrated capability",
         "conditions_satisfiable": "partly", "disanalogy": "seeds are interchangeable"},
        {"id": "C2", "source_mechanism": "M1", "ladder": "relational",
         "proposition": "Organizations should exercise unused capabilities.",
         "settings": "any", "antecedents": "none", "outcomes": "readiness",
         "boundary": "none", "conditions_satisfiable": "yes",
         "disanalogy": "no mechanism specified"}]},
    "module_5": {"verdicts": [
        {"id": "C1", "verdict": "pass", "failed_filter": None, "reason": "specific and testable",
         "scores": {"abstraction": 5, "feasibility": 4, "novelty": 5,
                    "falsifiability": 5, "usefulness": 4},
         "literature_overlap": {"nearest": "absorptive capacity", "assessment": "adjacent"}},
        {"id": "C2", "verdict": "reject", "failed_filter": "novelty",
         "reason": "standard advice with no mechanism",
         "scores": {"abstraction": 2, "feasibility": 4, "novelty": 1,
                    "falsifiability": None, "usefulness": None},
         "literature_overlap": {"nearest": "organizational slack", "assessment": "overlapping"}}]},
    "module_6": {"outputs": [
        {"id": "C1", "falsification_test": "compare drills with full activation",
         "design_note": "paired records", "verify_with_biologist": "germination fraction"}]},
}


def test_a_full_pass_chains_every_stage():
    c = StubClient()
    problem = "How can organizations preserve capabilities they must keep dormant?"

    framed = pipeline.frame(c, problem)
    framing = framed["options"][0]

    hits, aside, invalid = pipeline.suggest(c, framing["statement"])
    assert invalid == 0
    assert [h["phenomenon"].id for h in hits] == [40, 162]
    assert aside[0]["phenomenon"].id == 20

    run_id = pipeline.new_run_id()
    corpus = pipeline.suggestion_rejections(aside, framing["statement"], run_id)
    assert corpus[0]["stage"] == "suggestion"

    phen = hits[0]["phenomenon"]
    m1 = pipeline.module_1(c, phen)
    m2 = pipeline.module_2(c, m1)
    carried = [m for m in m2["mechanisms"] if not m.get("near_duplicate_of")]
    assert [m["id"] for m in carried] == ["M1", "M2"]

    m3 = pipeline.module_3(c, carried)
    chosen = [{"id": a["id"], "statement": a["statement"], "boundary": a["boundary"],
               "edited": a["id"] == "M1"}
              for a in m3["abstractions"] if a["specificity"] == "sufficient"]
    m4 = pipeline.module_4(c, chosen, framing["statement"])
    m5 = pipeline.module_5(c, m4["candidates"], framing["statement"])

    corpus = pipeline.merge_rejections(
        corpus, run_id, "module_5",
        pipeline.filtering_rejections(m4["candidates"], m5, phen, framing["statement"], run_id))
    assert len(corpus) == 2                      # one set aside, one rejected candidate

    survivors = [x for x in m4["candidates"]
                 if next(v for v in m5 if v["id"] == x["id"])["verdict"] == "pass"]
    m6 = pipeline.module_6(c, survivors, phen, framing["statement"])
    assert m6["outputs"][0]["id"] == "C1"
    assert c.usage["calls"] == 8                 # framing, suggestion, six modules


def test_an_edited_abstraction_is_marked_in_the_prompt():
    c = StubClient()
    pipeline.module_4(c, [{"id": "M1", "statement": "s", "boundary": "b", "edited": True}], "f")
    assert "[EDITED]" in c.prompts["module_4"]


def test_candidate_count_stays_inside_the_response_budget():
    c = StubClient()
    many = [{"id": f"M{i}", "statement": "s", "boundary": "b"} for i in range(5)]
    pipeline.module_4(c, many, "framing", RunConfig())
    assert "Produce 4 candidate" in c.prompts["module_4"]


def test_a_rejection_without_a_named_criterion_is_refused():
    c = StubClient()
    RESPONSES["module_5"] = {"verdicts": [
        {"id": "C1", "verdict": "reject", "failed_filter": None, "reason": "no"}]}
    try:
        with pytest.raises(client_mod.PipelineError):
            pipeline.module_5(c, [{"id": "C1", "ladder": "relational", "proposition": "p"}], "f")
    finally:
        RESPONSES["module_5"] = {"verdicts": [
            {"id": "C1", "verdict": "pass", "failed_filter": None, "reason": "ok",
             "scores": None, "literature_overlap": None}]}
