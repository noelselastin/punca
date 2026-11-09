"""Concept mapping and grounded remediation. Each function works with Gemini and falls back to a
deterministic offline answer (keyword search / the course note itself) when the model is unavailable."""
from __future__ import annotations

import logging
import re

from content import Catalog
from llm import prompts
from llm.client import LLMClient
from llm.schemas import MapResult, Remediation

log = logging.getLogger("punca.llm")


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


class LLMService:
    def __init__(self, catalog: Catalog, client: LLMClient):
        self.cat = catalog
        self.client = client

    # ---- concept mapping -------------------------------------------------------------------
    def map_stuck_point(self, stuck_input: str) -> dict:
        shortlist = self.cat.search_concepts(stuck_input, k=5)
        out = {"candidates": shortlist, "source": "keyword-search", "llmError": None}
        if self.client.available:
            try:
                res = self.client.generate_json(
                    prompts.map_prompt(stuck_input, list(self.cat.concepts.values()), [c["conceptId"] for c in shortlist]),
                    MapResult, temperature=0.1)
                if res["conceptId"] in self.cat.concepts:
                    cid = res["conceptId"]
                    if cid not in [c["conceptId"] for c in shortlist]:
                        out["candidates"] = [{"conceptId": cid, "name": self.cat.name(cid), "score": None}] + shortlist[:4]
                    out.update(targetConceptId=cid, justification=res["justification"].strip(),
                               confidence=round(min(max(res["confidence"], 0.0), 1.0), 2), source="gemini")
                    return out
                out["llmError"] = f"model chose an unknown concept id: {res['conceptId']!r}"
            except Exception as exc:
                log.warning("mapping via Gemini failed, using keyword search: %s", exc)
                out["llmError"] = str(exc)[:300]
        if not shortlist:
            out.update(targetConceptId=None, confidence=0.0,
                       justification="No concept matched those words. Pick the closest concept from the list.")
            return out
        top = shortlist[0]
        second = shortlist[1]["score"] if len(shortlist) > 1 else 0.0
        margin = (top["score"] - second) / top["score"] if top["score"] else 0.0
        out.update(targetConceptId=top["conceptId"], confidence=round(0.4 + 0.5 * margin, 2),
                   justification=f"Closest keyword match: {top['name']}.")
        return out

    # ---- remediation -----------------------------------------------------------------------
    def _chunks_for(self, root: str, path: list[str]) -> list[dict]:
        chunks = list(self.cat.notes_by_concept.get(root, []))
        nxt = path[1] if len(path) > 1 else None
        if nxt:
            chunks += self.cat.notes_by_concept.get(nxt, [])[:1]
        for ch in self.cat.search_notes(self.cat.name(root) or root, k=3):
            if ch not in chunks and len(chunks) < 4:
                chunks.append(ch)
        return chunks

    def remediate(self, target: str, root: str, path: list[str], misconceptions: list[str]) -> dict:
        chunks = self._chunks_for(root, path)
        citations = [{"sourceId": ch["sourceId"], "title": ch["title"]} for ch in chunks]
        if not chunks or not self.cat.notes_by_concept.get(root):
            return {"found": False, "source": "course-notes", "explanation": "",
                    "keyPoints": [], "citations": [], "llmError": None,
                    "message": f"Not found in course material: there is no note for {self.cat.name(root)} yet."}
        own = self.cat.notes_by_concept[root][0]
        offline = {"found": True, "source": "course-notes", "explanation": own["text"],
                   "keyPoints": _sentences(own["text"])[:3],
                   "citations": [{"sourceId": own["sourceId"], "title": own["title"]}], "llmError": None}
        if not self.client.available:
            return offline
        try:
            res = self.client.generate_json(
                prompts.remediation_prompt(self.cat.name(target), self.cat.name(root),
                                           [self.cat.name(c) for c in path], misconceptions, chunks),
                Remediation, temperature=0.4)
        except Exception as exc:
            log.warning("remediation via Gemini failed, showing the course note: %s", exc)
            return dict(offline, llmError=str(exc)[:300])
        allowed = {c["sourceId"]: c for c in citations}
        used = [allowed[s] for s in res["sourceIds"] if s in allowed]
        if not res["foundInCourseMaterial"] or not res["explanation"].strip():
            return dict(offline, llmError="model reported the material did not cover this concept")
        if not used:
            used = [{"sourceId": own["sourceId"], "title": own["title"]}]
        return {"found": True, "source": "gemini", "explanation": res["explanation"].strip(),
                "keyPoints": [k.strip() for k in res["keyPoints"]][:3], "citations": used, "llmError": None}
