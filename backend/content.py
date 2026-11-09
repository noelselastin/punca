"""Loads the curated concept graph, probe bank and course notes from data/ and validates them."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

import config
from diagnosis.graph import ConceptGraph
from retrieval.bm25 import BM25, tokenize

NOTE_HEADING = re.compile(r"^##\s+([a-z0-9-]+)\s*\|\s*(.+?)\s*$")


class ContentError(ValueError):
    pass


def parse_notes(notes_dir: Path) -> list[dict]:
    chunks: list[dict] = []
    for md in sorted(notes_dir.glob("*.md")):
        current: tuple[str, str] | None = None
        lines: list[str] = []

        def flush() -> None:
            if current:
                text = " ".join(l.strip() for l in lines if l.strip())
                chunks.append({"sourceId": f"{md.name}#{current[0]}", "conceptId": current[0],
                               "title": current[1], "text": text, "file": md.name})

        for line in md.read_text(encoding="utf-8").splitlines():
            m = NOTE_HEADING.match(line)
            if m:
                flush()
                current, lines = (m.group(1), m.group(2)), []
            elif current is not None:
                lines.append(line)
        flush()
    return chunks


class Catalog:
    def __init__(self, data_dir: Path = config.DATA_DIR):
        raw = json.loads((data_dir / "concepts" / "maths-to-ml.json").read_text(encoding="utf-8"))
        self.course: dict = raw["course"]
        self.labs: list[dict] = raw["labs"]
        concept_list: list[dict] = raw["concepts"]
        self.graph = ConceptGraph(concept_list)
        self.concepts: dict[str, dict] = {c["id"]: dict(c, courseId=self.course["id"]) for c in concept_list}

        probes = json.loads((data_dir / "probes" / "maths-to-ml.json").read_text(encoding="utf-8"))["probes"]
        self.probes: dict[str, dict] = {}
        by_concept: dict[str, list[dict]] = defaultdict(list)
        for p in probes:
            if p["id"] in self.probes:
                raise ContentError(f"duplicate probe id {p['id']}")
            if p["conceptId"] not in self.concepts:
                raise ContentError(f"probe {p['id']} has unknown concept {p['conceptId']}")
            if len(p["options"]) < 2 or not 0 <= p["correctIndex"] < len(p["options"]):
                raise ContentError(f"probe {p['id']} has a bad correctIndex")
            for k in p.get("misconceptions", {}):
                if int(k) == p["correctIndex"] or not 0 <= int(k) < len(p["options"]):
                    raise ContentError(f"probe {p['id']} tags option {k} as a misconception")
            p = dict(p, type="multiple_choice", misconceptionTags=sorted(set(p.get("misconceptions", {}).values())))
            self.probes[p["id"]] = p
            by_concept[p["conceptId"]].append(p)
        self.probes_by_concept = {cid: sorted(ps, key=lambda x: (x.get("difficulty", 1), x["id"]))
                                  for cid, ps in by_concept.items()}

        self.notes = parse_notes(data_dir / "notes")
        self.notes_by_concept: dict[str, list[dict]] = defaultdict(list)
        for ch in self.notes:
            if ch["conceptId"] not in self.concepts:
                raise ContentError(f"note {ch['sourceId']} is for an unknown concept")
            self.notes_by_concept[ch["conceptId"]].append(ch)

        for cid, c in self.concepts.items():
            c["probeBank"] = [p["id"] for p in self.probes_by_concept.get(cid, [])]
            c["resources"] = [{"title": ch["title"], "sourceId": ch["sourceId"]} for ch in self.notes_by_concept.get(cid, [])]

        for lab in self.labs:
            for t in lab["targetConceptIds"]:
                if t not in self.concepts:
                    raise ContentError(f"{lab['id']} targets unknown concept {t}")

        # Retrieval indexes
        self._concept_ids = list(self.concepts)
        self.concept_index = BM25([self._concept_tokens(self.concepts[cid]) for cid in self._concept_ids])
        self.note_index = BM25([tokenize(ch["title"] + " " + ch["text"]) for ch in self.notes])

    @staticmethod
    def _concept_tokens(c: dict) -> list[str]:
        name = tokenize(c["name"])
        kw = [t for k in c.get("keywords", []) for t in tokenize(k)]
        return name * 3 + kw * 2 + tokenize(c["description"])

    # ---- lookups ---------------------------------------------------------------------------
    def name(self, cid: str | None) -> str | None:
        return self.concepts[cid]["name"] if cid and cid in self.concepts else None

    def search_concepts(self, text: str, k: int = 5) -> list[dict]:
        hits = self.concept_index.top(tokenize(text), k)
        return [{"conceptId": self._concept_ids[i], "name": self.concepts[self._concept_ids[i]]["name"],
                 "score": round(s, 3)} for i, s in hits]

    def search_notes(self, text: str, k: int = 3) -> list[dict]:
        return [self.notes[i] for i, _ in self.note_index.top(tokenize(text), k)]

    def lab_for(self, concept_id: str) -> str | None:
        """The lab that targets this concept, or else the first lab that depends on it."""
        for lab in self.labs:
            if concept_id in lab["targetConceptIds"]:
                return lab["id"]
        for lab in self.labs:
            if any(concept_id in self.graph.ancestors(t) for t in lab["targetConceptIds"]):
                return lab["id"]
        return None

    def public_probe(self, probe: dict) -> dict:
        return {"probeId": probe["id"], "conceptId": probe["conceptId"], "conceptName": self.name(probe["conceptId"]),
                "question": probe["question"], "options": probe["options"], "difficulty": probe.get("difficulty", 1)}

    def catalog_view(self) -> dict:
        levels = self.graph.levels()
        return {
            "course": self.course,
            "labs": self.labs,
            "concepts": [{"id": c["id"], "name": c["name"], "area": c["area"], "description": c["description"],
                          "prerequisites": c["prerequisites"], "resources": c["resources"],
                          "probeCount": len(c["probeBank"]), "level": levels[c["id"]]}
                         for c in self.concepts.values()],
        }
