import pytest

import config
from diagnosis import bkt
from diagnosis.bkt import MasteryBook
from diagnosis.engine import DiagnosisEngine, DiagnosisError
from diagnosis.graph import ConceptGraph, GraphError
from scheduling.circles import propose_circle


# ---- content -----------------------------------------------------------------------------------
def test_catalog_size_and_coverage(catalog):
    assert 30 <= len(catalog.concepts) <= 50
    for cid in catalog.concepts:
        assert len(catalog.probes_by_concept.get(cid, [])) >= 2, f"{cid} needs at least 2 probes"
        assert catalog.notes_by_concept.get(cid), f"{cid} has no course note"


def test_probes_are_well_formed(catalog):
    for p in catalog.probes.values():
        assert len(p["options"]) == 4
        assert len(set(p["options"])) == 4, f"duplicate options in {p['id']}"
        assert 0 <= p["correctIndex"] < 4
        assert p["explanation"]


def test_graph_rejects_cycles():
    with pytest.raises(GraphError):
        ConceptGraph([{"id": "a", "prerequisites": ["b"]}, {"id": "b", "prerequisites": ["a"]}])


def test_graph_path_runs_root_to_target(catalog):
    assert catalog.graph.path("backpropagation", "chain-rule") == ["chain-rule", "backpropagation"]
    assert catalog.graph.path("chain-rule", "chain-rule") == ["chain-rule"]
    assert "chain-rule" in catalog.graph.ancestors("backpropagation")


# ---- BKT ---------------------------------------------------------------------------------------
def test_bkt_matches_readme_formula():
    p = 0.5
    post = p * 0.9 / (p * 0.9 + (1 - p) * 0.25)
    assert bkt.update(p, True) == pytest.approx(post + (1 - post) * config.P_LEARN)
    assert bkt.update(p, False) < p < bkt.update(p, True)


def test_two_correct_rechecks_turn_a_gap_solid():
    p = bkt.update(config.P_INIT, False)
    assert bkt.status(p, 1) == "gap"
    p = bkt.update(p, True)
    assert bkt.status(p, 2) == "shaky"
    p = bkt.update(p, True)
    assert bkt.status(p, 3) == "solid"


# ---- engine ------------------------------------------------------------------------------------
def run(catalog, target, gap):
    eng = DiagnosisEngine(catalog.graph, catalog.probes, catalog.probes_by_concept)
    book = MasteryBook()
    st = eng.start(eng.new_state(target), book)
    while st["status"] == "in_progress":
        pend = st["pending"]
        probe = catalog.probes[pend["probeId"]]
        c = pend["conceptId"]
        knows = not (c == gap or gap in catalog.graph.ancestors(c))
        eng.answer(st, probe["id"], probe["correctIndex"] if knows else (probe["correctIndex"] + 1) % 4, book)
    return st


def test_readme_demo_backprop_gap_is_chain_rule(catalog):
    st = run(catalog, "backpropagation", "chain-rule")
    r = st["result"]
    assert r["rootCauseConceptId"] == "chain-rule"
    assert r["remediationPath"] == ["chain-rule", "backpropagation"]
    assert r["probesUsed"] <= config.MAX_PROBES
    assert r["evidence"][0]["misconception"]  # the wrong backprop answer carries a tag


def test_target_itself_can_be_the_root(catalog):
    st = run(catalog, "matrix-multiplication", "matrix-multiplication")
    assert st["result"]["rootCauseConceptId"] == "matrix-multiplication"
    assert st["result"]["untestedPrerequisites"] == []


def test_no_gap_when_everything_is_known(catalog):
    st = run(catalog, "softmax", "__none__")
    assert st["result"]["rootCauseConceptId"] is None
    assert st["result"]["probesUsed"] == 1


def test_answer_must_match_pending_probe(catalog):
    eng = DiagnosisEngine(catalog.graph, catalog.probes, catalog.probes_by_concept)
    book = MasteryBook()
    st = eng.start(eng.new_state("chain-rule"), book)
    with pytest.raises(DiagnosisError):
        eng.answer(st, "sigmoid-1", 0, book)


# ---- scheduling --------------------------------------------------------------------------------
def test_circle_prefers_lecturer_slot():
    avail = {"a": ["Tue-14", "Mon-9"], "b": ["Tue-14", "Mon-9"], "c": ["Tue-14", "Mon-9"]}
    slots = [{"id": "s1", "day": "Tue", "start": 14, "end": 15, "capacity": 5, "linkedConceptIds": ["chain-rule"]}]
    prop = propose_circle("chain-rule", avail, slots, {}, 3, 6)
    assert prop["proposedSlot"] == "Tue-14" and prop["lecturerSlotId"] == "s1"


def test_circle_needs_min_group_size():
    avail = {"a": ["Tue-14"], "b": ["Wed-10"]}
    assert propose_circle("chain-rule", avail, [], {}, 3, 6) is None
