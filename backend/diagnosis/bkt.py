"""Bayesian Knowledge Tracing style mastery update (README section 8)."""
from __future__ import annotations

import config


def update(p_known: float, correct: bool, p_guess: float = config.P_GUESS,
           p_slip: float = config.P_SLIP, p_learn: float = config.P_LEARN) -> float:
    """Return the new pKnown after one answer."""
    p = min(max(p_known, 0.0), 1.0)
    if correct:
        num = p * (1 - p_slip)
        den = num + (1 - p) * p_guess
    else:
        num = p * p_slip
        den = num + (1 - p) * (1 - p_guess)
    posterior = num / den if den > 0 else p
    return posterior + (1 - posterior) * p_learn


def status(p_known: float, evidence_count: int) -> str:
    """Colour bucket for the concept map: solid / shaky / gap / untested."""
    if evidence_count <= 0:
        return "untested"
    if p_known >= config.SOLID:
        return "solid"
    if p_known >= config.GAP:
        return "shaky"
    return "gap"


class MasteryBook:
    """In-memory mastery store: conceptId -> (pKnown, evidenceCount). Used by tests and the eval runner."""

    def __init__(self, data: dict | None = None, p_init: float = config.P_INIT):
        self.data = dict(data or {})
        self.p_init = p_init

    def get(self, concept_id: str) -> tuple[float, int]:
        d = self.data.get(concept_id)
        if not d:
            return self.p_init, 0
        return d["pKnown"], d["evidenceCount"]

    def set(self, concept_id: str, p_known: float, evidence_count: int) -> None:
        self.data[concept_id] = {"pKnown": p_known, "evidenceCount": evidence_count}
