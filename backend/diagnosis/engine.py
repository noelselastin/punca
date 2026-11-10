"""Adaptive diagnosis with 5–10 foundational probes and Certainty-Based Marking (CBM).

The LLM does not decide the diagnosis. Probes come from the curated bank, multiple-choice answers are graded
by comparing indices, mastery is updated with confidence-weighted BKT, and the root cause is picked by plain code:

1. Seed the queue with the target concept, required foundations extracted from the student's brief/document,
   and their prerequisite chain so at least MIN_PROBES (5) and up to MAX_PROBES (10) questions are asked.
2. Weight BKT updates by student confidence ("low" = guessing, "medium" = somewhat sure, "high" = confident):
   - A correct answer with "low" confidence uses a high guess factor (p_guess=0.58) so a single lucky guess
     from prior 0.50 stays shaky (< SOLID) and triggers prerequisite checks.
   - An incorrect answer with "high" confidence flags a high-confidence misconception (p_slip=0.03).
3. Whenever a probed concept looks weak or shaky (pKnown < SOLID), queue its prerequisites (breadth-first).
4. Stop once at least MIN_PROBES have been answered and either the queue is resolved or MAX_PROBES is reached.
5. Root cause = a weak concept whose own prerequisites all look solid (the frontier of weakness).
"""
from __future__ import annotations

from dataclasses import dataclass

import config
from diagnosis import bkt
from diagnosis.graph import ConceptGraph

CONFIDENCE_LEVELS = ("low", "medium", "high")


@dataclass
class Params:
    max_probes: int = config.MAX_PROBES
    min_probes: int = config.MIN_PROBES
    solid: float = config.SOLID
    p_guess: float = config.P_GUESS
    p_slip: float = config.P_SLIP
    p_learn: float = config.P_LEARN

    def __post_init__(self) -> None:
        if self.min_probes > self.max_probes:
            self.min_probes = self.max_probes


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
    def new_state(
        self,
        target: str,
        used_probe_ids: list[str] | None = None,
        focus_concepts: list[str] | None = None,
    ) -> dict:
        if target not in self.graph.ids:
            raise DiagnosisError(f"unknown concept {target}")
        focus = [c for c in (focus_concepts or []) if c in self.graph.ids and c != target]
        initial_queue: list[str] = [target]
        for c in focus:
            if c not in initial_queue:
                initial_queue.append(c)
        for pre in self.graph.prereqs(target):
            if pre not in initial_queue:
                initial_queue.append(pre)
        return {
            "targetConceptId": target,
            "focusConcepts": focus,
            "queue": initial_queue,
            "asked": [],
            "skippedSolid": [],
            "pending": None,
            "status": "in_progress",
            "usedProbeIds": list(used_probe_ids or []),
            "minProbes": self.params.min_probes,
            "maxProbes": self.params.max_probes,
            "result": None,
        }

    def start(self, state: dict, book) -> dict:
        self._advance(state, book)
        return state

    def pick_probe(self, concept_id: str, used: set[str], asked_this_session: set[str] | None = None) -> dict | None:
        bank = self.by_concept.get(concept_id, [])
        asked_now = asked_this_session or set()
        for p in bank:
            if p["id"] not in used and p["id"] not in asked_now:
                return p
        for p in bank:
            if p["id"] not in asked_now:
                return p
        return None

    def _tested(self, state: dict) -> list[str]:
        seen: list[str] = []
        for a in state["asked"]:
            if a["conceptId"] not in seen:
                seen.append(a["conceptId"])
        return seen

    def _foundation_pool(self, state: dict) -> list[str]:
        """Ordered pool of relevant foundational concepts to ensure 5–10 questions can be asked."""
        target = state["targetConceptId"]
        pool: list[str] = [target]
        for fc in state.get("focusConcepts") or []:
            if fc not in pool:
                pool.append(fc)
        # Breadth-first ancestors of target and focus concepts
        bfs = list(pool)
        visited = set(bfs)
        while bfs:
            cur = bfs.pop(0)
            for pre in self.graph.prereqs(cur):
                if pre not in visited:
                    visited.add(pre)
                    pool.append(pre)
                    bfs.append(pre)
        # If target has very few ancestors (e.g. a leaf foundation concept), include direct dependents
        # and same-area concepts so we still have at least min_probes relevant foundation checks.
        if len(pool) < state.get("minProbes", self.params.min_probes):
            for dep in self.graph.dependents(target):
                if dep not in pool:
                    pool.append(dep)
            target_area = self.graph.concepts[target].get("area")
            for cid, c in self.graph.concepts.items():
                if c.get("area") == target_area and cid not in pool:
                    pool.append(cid)
        return pool

    def _advance(self, state: dict, book) -> None:
        max_probes = state.get("maxProbes", self.params.max_probes)
        min_probes = min(state.get("minProbes", self.params.min_probes), max_probes)
        asked_probe_ids = {a["probeId"] for a in state["asked"]}
        tested = set(self._tested(state))

        # 1. Process explicit queue (target, focus foundations, and queued prerequisites of weak concepts)
        while state["queue"] and len(state["asked"]) < max_probes:
            c = state["queue"].pop(0)
            p, ev = book.get(c)
            # Only skip previously-solid prerequisites once we have already asked at least min_probes questions
            if (
                c != state["targetConceptId"]
                and c not in (state.get("focusConcepts") or [])
                and len(state["asked"]) >= min_probes
                and ev > 0
                and p >= self.params.solid
            ):
                if c not in state["skippedSolid"]:
                    state["skippedSolid"].append(c)
                continue
            # Avoid testing the same concept twice from the primary queue unless it's a low-confidence re-verify
            if c in tested:
                continue
            probe = self.pick_probe(c, set(state["usedProbeIds"]), asked_probe_ids)
            if probe is None:
                continue
            state["pending"] = {"probeId": probe["id"], "conceptId": c}
            return

        # 2. If we have not yet reached min_probes (5), continue probing relevant foundations
        if len(state["asked"]) < min_probes and len(state["asked"]) < max_probes:
            pool = self._foundation_pool(state)
            # First pass: untested concepts in the foundation pool
            for c in pool:
                if c in tested:
                    continue
                probe = self.pick_probe(c, set(state["usedProbeIds"]), asked_probe_ids)
                if probe is not None:
                    state["pending"] = {"probeId": probe["id"], "conceptId": c}
                    return
            # Second pass: second verification probe on weak/shaky or core pool concepts
            priority = sorted(
                pool,
                key=lambda cid: (book.get(cid)[0] >= self.params.solid, book.get(cid)[0]),
            )
            for c in priority:
                probe = self.pick_probe(c, set(state["usedProbeIds"]), asked_probe_ids)
                if probe is not None:
                    state["pending"] = {"probeId": probe["id"], "conceptId": c}
                    return

        state["pending"] = None
        state["status"] = "done"
        state["result"] = self.finalize(state, book)

    def _bkt_params_for_confidence(self, confidence: str, correct: bool) -> tuple[float, float]:
        """Adjust BKT guess/slip parameters based on the student's self-reported confidence."""
        conf = confidence if confidence in CONFIDENCE_LEVELS else "medium"
        if conf == "low":
            # Student admits guessing: high p_guess means a lucky right answer doesn't jump to SOLID
            return (0.58 if correct else self.params.p_guess), self.params.p_slip
        if conf == "high":
            # Student is confident: lower guess on right answer, lower slip on wrong answer (stronger penalty)
            return (0.12 if correct else self.params.p_guess), (0.03 if not correct else self.params.p_slip)
        return self.params.p_guess, self.params.p_slip

    def answer(
        self,
        state: dict,
        probe_id: str,
        choice_index: int,
        book,
        confidence: str = "medium",
    ) -> dict:
        if state["status"] != "in_progress":
            raise DiagnosisError("this diagnosis is already finished")
        pending = state.get("pending")
        if not pending or pending["probeId"] != probe_id:
            raise DiagnosisError("that probe is not the one waiting for an answer")
        probe = self.probes[probe_id]
        if not isinstance(choice_index, int) or not 0 <= choice_index < len(probe["options"]):
            raise DiagnosisError("choiceIndex out of range")
        conf = (confidence or "medium").strip().lower()
        if conf not in CONFIDENCE_LEVELS:
            conf = "medium"

        c = pending["conceptId"]
        correct = choice_index == probe["correctIndex"]
        p_before, ev = book.get(c)
        p_guess, p_slip = self._bkt_params_for_confidence(conf, correct)
        p_after = bkt.update(p_before, correct, p_guess, p_slip, self.params.p_learn)
        book.set(c, p_after, ev + 1)
        misconception = None if correct else probe.get("misconceptions", {}).get(str(choice_index))
        high_conf_gap = (not correct) and (conf == "high")
        lucky_guess = correct and (conf == "low")

        state["asked"].append({
            "probeId": probe_id,
            "conceptId": c,
            "choiceIndex": choice_index,
            "choiceText": probe["options"][choice_index],
            "correct": correct,
            "confidence": conf,
            "highConfidenceGap": high_conf_gap,
            "luckyGuess": lucky_guess,
            "misconception": misconception,
            "pBefore": round(p_before, 4),
            "pAfter": round(p_after, 4),
        })
        state["usedProbeIds"].append(probe_id)
        if p_after < self.params.solid or lucky_guess:
            tested = set(self._tested(state))
            for pre in self.graph.prereqs(c):
                if pre not in tested and pre not in state["queue"]:
                    state["queue"].append(pre)
        state["pending"] = None
        self._advance(state, book)
        return {
            "conceptId": c,
            "correct": correct,
            "confidence": conf,
            "highConfidenceGap": high_conf_gap,
            "luckyGuess": lucky_guess,
            "correctIndex": probe["correctIndex"],
            "explanation": probe.get("explanation", ""),
            "misconception": misconception,
            "pKnown": round(p_after, 4),
        }

    # ---- result ----------------------------------------------------------------------------
    def _confidence_summary(self, asked: list[dict]) -> dict:
        if not asked:
            return {
                "level": "untested",
                "label": "No questions answered",
                "score": 0.0,
                "highConfidenceCorrect": 0,
                "highConfidenceWrong": 0,
                "lowConfidenceCorrect": 0,
                "total": 0,
            }
        weights = {"low": 0.35, "medium": 0.7, "high": 1.0}
        total = len(asked)
        high_right = sum(1 for a in asked if a.get("correct") and a.get("confidence") == "high")
        high_wrong = sum(1 for a in asked if not a.get("correct") and a.get("confidence") == "high")
        low_right = sum(1 for a in asked if a.get("correct") and a.get("confidence") == "low")
        # Calibrated confidence score: rewards confident accuracy, discounts guesses, penalizes confident misconceptions
        raw = 0.0
        for a in asked:
            w = weights.get(a.get("confidence", "medium"), 0.7)
            if a.get("correct"):
                raw += w
            else:
                raw -= 0.4 * w
        score = round(max(0.0, min(1.0, raw / total)), 2)
        if score >= 0.72 and high_wrong == 0:
            level, label = "confident", "Confident & well-calibrated across foundations"
        elif score >= 0.45:
            level, label = "moderate", "Partial confidence — some foundational hesitation or slips"
        else:
            level, label = "uncertain", "Low foundational confidence — needs targeted review"
        return {
            "level": level,
            "label": label,
            "score": score,
            "highConfidenceCorrect": high_right,
            "highConfidenceWrong": high_wrong,
            "lowConfidenceCorrect": low_right,
            "total": total,
        }

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

        evidence = [
            {
                "probeId": a["probeId"],
                "conceptId": a["conceptId"],
                "correct": a["correct"],
                "confidence": a.get("confidence", "medium"),
                "highConfidenceGap": a.get("highConfidenceGap", False),
                "luckyGuess": a.get("luckyGuess", False),
                "misconception": a["misconception"],
            }
            for a in state["asked"]
        ]
        conf_summary = self._confidence_summary(state["asked"])
        weak = [c for c in self._tested(state) if is_weak(c)]
        base = {
            "targetConceptId": target,
            "evidence": evidence,
            "probesUsed": len(state["asked"]),
            "skippedSolid": list(state["skippedSolid"]),
            "confidenceAssessment": conf_summary,
        }
        if not weak:
            return {
                **base,
                "rootCauseConceptId": None,
                "confidence": conf_summary["score"],
                "remediationPath": [],
                "otherGaps": [],
                "untestedPrerequisites": [],
                "message": "No foundational gap found: you answered the 5–10 foundation checks with solid mastery.",
            }

        candidates = []
        for c in weak:
            prs = self.graph.prereqs(c)
            if any(is_weak(p) for p in prs):
                continue  # a weaker prerequisite sits underneath, so c is not the frontier
            solid_n = sum(1 for p in prs if is_solid(p))
            frac = solid_n / len(prs) if prs else 1.0
            candidates.append({
                "conceptId": c,
                "confirmed": frac == 1.0,
                "depth": depth.get(c, 0),
                "pKnown": book.get(c)[0],
                "testedFraction": frac,
                "untested": [p for p in prs if not is_solid(p) and not is_weak(p)],
            })
        if not candidates:
            # Fallback if a cycle or isolated weak concept occurs
            c = weak[0]
            candidates = [{
                "conceptId": c,
                "confirmed": True,
                "depth": depth.get(c, 0),
                "pKnown": book.get(c)[0],
                "testedFraction": 1.0,
                "untested": [],
            }]
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
