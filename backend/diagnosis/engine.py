"""Adaptive diagnosis (README section 8).

The LLM does not decide the diagnosis. Probes come from the curated bank, multiple-choice answers are graded
by comparing indices, mastery is updated with BKT, and the root cause is picked by plain code:

1. Probe the target concept.
2. Whenever a probed concept looks weak (pKnown < SOLID), queue its prerequisites (breadth-first).
3. Stop after MAX_PROBES probes or when the queue is empty.
4. Root cause = a weak concept whose own prerequisites all look solid (the frontier of weakness).
   Ties: concepts whose prerequisites were all confirmed solid beat ones with untested prerequisites,
   then the deeper concept (further from the target) wins, then the lower pKnown.

The state is a plain dict so it can be stored as JSON between HTTP requests.
"""
from __future__ import annotations

from dataclasses import dataclass

import config
from diagnosis import bkt
from diagnosis.graph import ConceptGraph


@dataclass
class Params:
    max_probes: int = config.MAX_PROBES
    solid: float = config.SOLID
    p_guess: float = config.P_GUESS
    p_slip: float = config.P_SLIP
    p_learn: float = config.P_LEARN


class DiagnosisError(ValueError):
    pass


class DiagnosisEngine:
    def __init__(self, graph: ConceptGraph, probes: dict[str, dict],
                 probes_by_concept: dict[str, list[dict]], params: Params | None = None):
        self.graph = graph
        self.probes = probes
        self.by_concept = probes_by_concept
        self.params = params or Params()

    # ---- state -----------------------------------------------------------------------------
    def new_state(self, target: str, used_probe_ids: list[str] | None = None) -> dict:
        if target not in self.graph.ids:
            raise DiagnosisError(f"unknown concept {target}")
        return {
            "targetConceptId": target,
            "queue": [target],
            "asked": [],
            "skippedSolid": [],
            "pending": None,
            "status": "in_progress",
            "usedProbeIds": list(used_probe_ids or []),
            "maxProbes": self.params.max_probes,
            "result": None,
        }

    def start(self, state: dict, book) -> dict:
        self._advance(state, book)
        return state

    def pick_probe(self, concept_id: str, used: set[str]) -> dict | None:
        bank = self.by_concept.get(concept_id, [])
        for p in bank:
            if p["id"] not in used:
                return p
        return bank[0] if bank else None

    def _tested(self, state: dict) -> list[str]:
        seen: list[str] = []
        for a in state["asked"]:
            if a["conceptId"] not in seen:
                seen.append(a["conceptId"])
        return seen

    def _advance(self, state: dict, book) -> None:
        tested = set(self._tested(state))
        while state["queue"] and len(state["asked"]) < self.params.max_probes:
            c = state["queue"].pop(0)
            if c in tested:
                continue
            p, ev = book.get(c)
            # A prerequisite already shown to be solid in earlier sessions does not need re-probing.
            if c != state["targetConceptId"] and ev > 0 and p >= self.params.solid:
                if c not in state["skippedSolid"]:
                    state["skippedSolid"].append(c)
                continue
            probe = self.pick_probe(c, set(state["usedProbeIds"]))
            if probe is None:
                continue
            state["pending"] = {"probeId": probe["id"], "conceptId": c}
            return
        state["pending"] = None
        state["status"] = "done"
        state["result"] = self.finalize(state, book)

    def answer(self, state: dict, probe_id: str, choice_index: int, book) -> dict:
        if state["status"] != "in_progress":
            raise DiagnosisError("this diagnosis is already finished")
        pending = state.get("pending")
        if not pending or pending["probeId"] != probe_id:
            raise DiagnosisError("that probe is not the one waiting for an answer")
        probe = self.probes[probe_id]
        if not isinstance(choice_index, int) or not 0 <= choice_index < len(probe["options"]):
            raise DiagnosisError("choiceIndex out of range")
        c = pending["conceptId"]
        correct = choice_index == probe["correctIndex"]
        p_before, ev = book.get(c)
        p_after = bkt.update(p_before, correct, self.params.p_guess, self.params.p_slip, self.params.p_learn)
        book.set(c, p_after, ev + 1)
        misconception = None if correct else probe.get("misconceptions", {}).get(str(choice_index))
        state["asked"].append({
            "probeId": probe_id, "conceptId": c, "choiceIndex": choice_index, "correct": correct,
            "misconception": misconception, "pBefore": round(p_before, 4), "pAfter": round(p_after, 4),
        })
        state["usedProbeIds"].append(probe_id)
        if p_after < self.params.solid:
            tested = set(self._tested(state))
            for pre in self.graph.prereqs(c):
                if pre not in tested and pre not in state["queue"]:
                    state["queue"].append(pre)
        state["pending"] = None
        self._advance(state, book)
        return {
            "conceptId": c, "correct": correct, "correctIndex": probe["correctIndex"],
            "explanation": probe.get("explanation", ""), "misconception": misconception,
            "pKnown": round(p_after, 4),
        }

    # ---- result ----------------------------------------------------------------------------
    def finalize(self, state: dict, book) -> dict:
        target = state["targetConceptId"]
        solid = self.params.solid
        depth = self.graph.distances_from(target)

        def is_solid(cid: str) -> bool:
            p, ev = book.get(cid)
            return ev > 0 and p >= solid

        def is_weak(cid: str) -> bool:
            p, ev = book.get(cid)
            return ev > 0 and p < solid

        evidence = [{"probeId": a["probeId"], "conceptId": a["conceptId"], "correct": a["correct"],
                     "misconception": a["misconception"]} for a in state["asked"]]
        weak = [c for c in self._tested(state) if is_weak(c)]
        base = {"targetConceptId": target, "evidence": evidence, "probesUsed": len(state["asked"]),
                "skippedSolid": list(state["skippedSolid"])}
        if not weak:
            return {**base, "rootCauseConceptId": None, "confidence": 0.0, "remediationPath": [],
                    "otherGaps": [], "untestedPrerequisites": [],
                    "message": "No gap found: you answered the checks on this concept correctly."}

        candidates = []
        for c in weak:
            prs = self.graph.prereqs(c)
            if any(is_weak(p) for p in prs):
                continue  # a weaker prerequisite sits underneath, so c is not the frontier
            solid_n = sum(1 for p in prs if is_solid(p))
            frac = solid_n / len(prs) if prs else 1.0
            candidates.append({
                "conceptId": c, "confirmed": frac == 1.0, "depth": depth.get(c, 0),
                "pKnown": book.get(c)[0], "testedFraction": frac,
                "untested": [p for p in prs if not is_solid(p) and not is_weak(p)],
            })
        candidates.sort(key=lambda x: (not x["confirmed"], -x["depth"], x["pKnown"]))
        root = candidates[0]
        confidence = round((1 - root["pKnown"]) * (0.6 + 0.4 * root["testedFraction"]), 2)
        return {
            **base,
            "rootCauseConceptId": root["conceptId"],
            "confidence": confidence,
            "remediationPath": self.graph.path(target, root["conceptId"]),
            "otherGaps": [c["conceptId"] for c in candidates[1:]],
            "untestedPrerequisites": root["untested"],
        }
