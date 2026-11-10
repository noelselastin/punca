"""Peer Study Circle grouping and common-hour matching.

Availability is a list of one-hour slots written "Tue-14" (Tuesday 14:00-15:00).
"""
from __future__ import annotations

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
HOURS = list(range(9, 18))  # 09:00 .. 17:00 starts
ALL_SLOTS = [f"{d}-{h}" for d in DAYS for h in HOURS]
SLOT_ORDER = {s: i for i, s in enumerate(ALL_SLOTS)}


def valid_slot(s: str) -> bool:
    return s in SLOT_ORDER


def slot_label(s: str) -> str:
    d, h = s.split("-")
    return f"{d} {int(h):02d}:00-{int(h) + 1:02d}:00"


def best_common_slot(availability: dict[str, list[str]], must_include: str | None = None) -> tuple[str | None, list[str]]:
    """The slot most members share (earliest wins ties). Returns (slot, uids available then)."""
    best: tuple[str | None, list[str]] = (None, [])
    for s in ALL_SLOTS:
        if must_include and s not in availability.get(must_include, []):
            continue
        uids = [u for u, slots in availability.items() if s in slots]
        if len(uids) > len(best[1]):
            best = (s, uids)
    return best


def propose_circle(
    concept_id: str,
    availability: dict[str, list[str]],
    min_size: int,
    max_size: int,
    must_include: str | None = None,
) -> dict | None:
    """Pick a time and members for one concept peer study circle.

    availability: uid -> slots for every opted-in student whose root cause is concept_id.
    Returns None when fewer than min_size students share any hour.
    """
    best = None
    for s in ALL_SLOTS:
        if must_include and s not in availability.get(must_include, []):
            continue
        uids = sorted(u for u, slots in availability.items() if s in slots)
        if must_include:
            uids = [must_include] + [u for u in uids if u != must_include]
        group = uids[:max_size]
        if len(group) < min_size:
            continue
        score = (len(group), -SLOT_ORDER[s])
        if best is None or score > best[0]:
            best = (score, s, group)
    if best is None:
        return None
    _, s, group = best
    return {"conceptId": concept_id, "memberUids": group, "proposedSlot": s, "mode": "peer"}
