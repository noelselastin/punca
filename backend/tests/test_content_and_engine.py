from collections import Counter
import pytest

import config
from diagnosis import bkt
from diagnosis.bkt import MasteryBook
from diagnosis.engine import DiagnosisEngine, DiagnosisError
from diagnosis.graph import ConceptGraph, GraphError
from scheduling.circles import propose_circle


# ---- Root Cause Concept Graph validation -------------------------------------------------------
def test_root_cause_graph_exact_counts_and_coverage(catalog):
    assert len(catalog.modules) == 6
    assert [m["id"] for m in catalog.modules] == ["FND-MATH", "FND-COMP", "CM", "PY", "JAVA", "DB"]
    assert len(catalog.topics) == 28
    assert len(catalog.concepts) == 138
    assert len(catalog.graph.edges()) == 211
    assert len(catalog.graph.soft_edges()) == 16

    per_mod = Counter(c["moduleId"] for c in catalog.concepts.values())
    assert dict(per_mod) == {
        "FND-MATH": 8,
        "FND-COMP": 12,
        "CM": 41,
        "PY": 26,
        "JAVA": 25,
        "DB": 26,
    }

    for cid, c in catalog.concepts.items():
        assert c["level"] in ("foundation", "core", "extension")
        assert isinstance(c["optional"], bool)
        assert isinstance(c["depth"], int)
        assert len(catalog.probes_by_concept.get(cid, [])) >= 2, f"{cid} needs at least 2 probes"
        assert catalog.notes_by_concept.get(cid), f"{cid} has no course note"


def test_soft_edges_never_affect_root_cause_tracing(catalog):
    # PY-RECUR has hard prerequisites [PY-PARAM, PY-IF] and soft related [CM-RECUR, CM-INDUCT]
    assert set(catalog.graph.prereqs("PY-RECUR")) == {"PY-PARAM", "PY-IF"}
    assert set(catalog.graph.related("PY-RECUR")) == {"CM-RECUR", "CM-INDUCT"}
    assert "CM-RECUR" not in catalog.graph.ancestors("PY-RECUR")
    assert "CM-INDUCT" not in catalog.graph.ancestors("PY-RECUR")


def test_probes_are_well_formed(catalog):
    correct_positions = Counter()
    for p in catalog.probes.values():
        assert len(p["options"]) == 4
        assert len(set(p["options"])) == 4, f"duplicate options in {p['id']}"
        assert 0 <= p["correctIndex"] < 4
        assert len(p.get("originalOptions") or []) == 4
        assert p["options"][p["correctIndex"]] == p["originalOptions"][0]
        assert p["explanation"]
        correct_positions[p["correctIndex"]] += 1
    assert set(correct_positions.keys()) == {0, 1, 2, 3}
    assert all(count >= 40 for count in correct_positions.values())


def test_graph_rejects_cycles():
    with pytest.raises(GraphError):
        ConceptGraph([{"id": "a", "prerequisites": ["b"]}, {"id": "b", "prerequisites": ["a"]}])


def test_graph_path_runs_root_to_target(catalog):
    assert catalog.graph.path("CM-GRADDESC", "CM-CHAIN") == ["CM-CHAIN", "CM-PARTIAL", "CM-GRADDESC"]
    assert catalog.graph.path("CM-CHAIN", "CM-CHAIN") == ["CM-CHAIN"]
    assert "CM-CHAIN" in catalog.graph.ancestors("CM-GRADDESC")


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


# ---- 5-10 question confidence-weighted engine --------------------------------------------------
def run(catalog, target, gap, confidence="high"):
    eng = DiagnosisEngine(catalog.graph, catalog.probes, catalog.probes_by_concept)
    book = MasteryBook()
    st = eng.start(eng.new_state(target), book)
    while st["status"] == "in_progress":
        pend = st["pending"]
        probe = catalog.probes[pend["probeId"]]
        c = pend["conceptId"]
        knows = not (c == gap or gap in catalog.graph.ancestors(c))
        eng.answer(
            st,
            probe["id"],
            probe["correctIndex"] if knows else (probe["correctIndex"] + 1) % 4,
            book,
            confidence=confidence,
        )
    return st


def test_graddesc_gap_is_chain_rule_with_5_to_10_probes(catalog):
    st = run(catalog, "CM-GRADDESC", "CM-CHAIN")
    r = st["result"]
    assert r["rootCauseConceptId"] == "CM-CHAIN"
    assert r["remediationPath"] == ["CM-CHAIN", "CM-PARTIAL", "CM-GRADDESC"]
    assert config.MIN_PROBES <= r["probesUsed"] <= config.MAX_PROBES
    assert r["evidence"][0]["misconception"]


def test_target_itself_can_be_the_root(catalog):
    st = run(catalog, "CM-MATMUL", "CM-MATMUL")
    assert st["result"]["rootCauseConceptId"] == "CM-MATMUL"
    assert config.MIN_PROBES <= st["result"]["probesUsed"] <= config.MAX_PROBES


def test_no_gap_when_everything_is_known_asks_at_least_min_probes(catalog):
    st = run(catalog, "DB-JOIN", "__none__", confidence="high")
    assert st["result"]["rootCauseConceptId"] is None
    assert config.MIN_PROBES <= st["result"]["probesUsed"] <= config.MAX_PROBES
    assert st["result"]["confidenceAssessment"]["level"] == "confident"


def test_low_confidence_guess_does_not_mark_solid(catalog):
    eng = DiagnosisEngine(catalog.graph, catalog.probes, catalog.probes_by_concept)
    book = MasteryBook()
    st = eng.start(eng.new_state("CM-CHAIN"), book)
    pend = st["pending"]
    probe = catalog.probes[pend["probeId"]]
    fb = eng.answer(st, probe["id"], probe["correctIndex"], book, confidence="low")
    assert fb["luckyGuess"] is True
    assert fb["pKnown"] < config.SOLID


def test_answer_must_match_pending_probe(catalog):
    eng = DiagnosisEngine(catalog.graph, catalog.probes, catalog.probes_by_concept)
    book = MasteryBook()
    st = eng.start(eng.new_state("CM-CHAIN"), book)
    with pytest.raises(DiagnosisError):
        eng.answer(st, "FM-ARITH-1", 0, book)


# ---- peer study circle scheduling --------------------------------------------------------------
def test_peer_circle_picks_common_slot():
    avail = {"a": ["Tue-14", "Mon-9"], "b": ["Tue-14", "Mon-9"], "c": ["Tue-14", "Mon-9"]}
    prop = propose_circle("CM-CHAIN", avail, 3, 6)
    assert prop["proposedSlot"] == "Mon-9" and prop["mode"] == "peer"


def test_circle_needs_min_group_size():
    avail = {"a": ["Tue-14"], "b": ["Wed-10"]}
    assert propose_circle("CM-CHAIN", avail, 3, 6) is None
