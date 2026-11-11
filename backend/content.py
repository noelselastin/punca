"""Loads the curated concept graph, probe bank and course notes from data/ and validates them.

Includes `adapt_concept_graph(raw)` to adapt the Root Cause concept graph JSON
(`meta`, `modules`, `topics`, `concepts`, `edges`) into the exact shape the Punca app expects
without modifying the underlying JSON source of truth.
"""
from __future__ import annotations

import json
import random
import re
from collections import defaultdict
from pathlib import Path

import config
from diagnosis.graph import ConceptGraph
from retrieval.bm25 import BM25, tokenize

NOTE_HEADING = re.compile(r"^##\s+([A-Za-z0-9-]+)\s*\|\s*(.+?)\s*$")


class ContentError(ValueError):
    pass


def adapt_concept_graph(raw: dict) -> dict:
    """Adapt the Root Cause concept graph JSON into the shape expected by Punca's Catalog.

    - Preserves all 6 `modules`, 28 `topics`, 138 `concepts`, 211 `hard` edges, and 16 `soft` edges verbatim.
    - Uses ONLY `hard` edges (`type == "hard"`) as `prerequisites` for root-cause tracing.
    - Keeps `soft` edges (`type == "soft"`) in `related` as cross-links that never affect tracing.
    - Adapts `meta` -> `course`, `topics` -> `labs` (while keeping `modules`, `topics`, `edges`),
      and sets `area` on each concept from its `moduleId` name so Passport regions and ConceptMap work seamlessly.
    """
    if "course" in raw and "labs" in raw and "modules" not in raw:
        # Already in legacy Punca shape
        return raw

    meta = raw.get("meta") or {}
    modules: list[dict] = list(raw.get("modules") or [])
    topics: list[dict] = list(raw.get("topics") or [])
    raw_concepts: list[dict] = list(raw.get("concepts") or [])
    edges: list[dict] = list(raw.get("edges") or [])

    if not modules or not topics or not raw_concepts:
        raise ContentError("Concept graph JSON must contain modules, topics, and concepts.")

    module_by_id = {m["id"]: m for m in modules}
    if len(module_by_id) != len(modules):
        raise ContentError("Duplicate module id in concept graph JSON.")
    for m in modules:
        for pm in m.get("prerequisiteModuleIds", []):
            if pm not in module_by_id:
                raise ContentError(f"Module {m['id']} references unknown prerequisiteModuleId {pm}")
        for rm in m.get("recommendedModuleIds", []):
            if rm not in module_by_id:
                raise ContentError(f"Module {m['id']} references unknown recommendedModuleId {rm}")

    topic_by_id = {t["id"]: t for t in topics}
    if len(topic_by_id) != len(topics):
        raise ContentError("Duplicate topic id in concept graph JSON.")
    for t in topics:
        if t.get("moduleId") not in module_by_id:
            raise ContentError(f"Topic {t['id']} references unknown moduleId {t.get('moduleId')}")

    concept_ids = {c["id"] for c in raw_concepts}
    if len(concept_ids) != len(raw_concepts):
        raise ContentError("Duplicate concept id in concept graph JSON.")

    for m in modules:
        for tid in m.get("topicIds", []):
            if tid not in topic_by_id:
                raise ContentError(f"Module {m['id']} references unknown topicId {tid}")
    for t in topics:
        for cid in t.get("conceptIds", []):
            if cid not in concept_ids:
                raise ContentError(f"Topic {t['id']} references unknown conceptId {cid}")

    # Validate explicit edges array (hard vs soft) against concept prerequisites and related lists
    hard_by_concept: dict[str, list[str]] = defaultdict(list)
    soft_by_concept: dict[str, list[str]] = defaultdict(list)
    for e in edges:
        src = e.get("concept")
        pre = e.get("prerequisite")
        etype = e.get("type")
        if src not in concept_ids:
            raise ContentError(f"Edge references unknown concept {src}")
        if pre not in concept_ids:
            raise ContentError(f"Edge on {src} references unknown prerequisite {pre}")
        if etype == "hard":
            hard_by_concept[src].append(pre)
        elif etype == "soft":
            soft_by_concept[src].append(pre)
        else:
            raise ContentError(f"Edge {src} -> {pre} has unknown type {etype!r}")

    adapted_concepts: list[dict] = []
    for c in raw_concepts:
        cid = c["id"]
        mid = c.get("moduleId")
        tid = c.get("topicId")
        if mid not in module_by_id:
            raise ContentError(f"Concept {cid} has unknown moduleId {mid}")
        if tid not in topic_by_id:
            raise ContentError(f"Concept {cid} has unknown topicId {tid}")
        if cid not in topic_by_id[tid].get("conceptIds", []):
            raise ContentError(f"Concept {cid} is not listed in its topic {tid}'s conceptIds")

        # Hard edges are the sole source for root-cause tracing prerequisites
        hard_prereqs = list(c.get("prerequisites") or [])
        soft_related = list(c.get("related") or [])
        if edges:
            if set(hard_prereqs) != set(hard_by_concept.get(cid, [])):
                raise ContentError(f"Concept {cid} prerequisites do not match hard edges")
            if set(soft_related) != set(soft_by_concept.get(cid, [])):
                raise ContentError(f"Concept {cid} related list does not match soft edges")

        mod_obj = module_by_id[mid]
        top_obj = topic_by_id[tid]
        adapted_concepts.append({
            **c,
            "prerequisites": hard_prereqs,
            "related": soft_related,
            # App-expected fields derived cleanly from module and topic metadata:
            "area": mod_obj["name"],
            "topicName": top_obj["name"],
        })

    # Adapt topics into the `labs` shape expected by PassportSetupPage, seed, and lab_for()
    labs = [
        {
            "id": t["id"],
            "moduleId": t["moduleId"],
            "order": t["order"],
            "name": f"{t['moduleId']} · {t['name']}",
            "targetConceptIds": list(t["conceptIds"]),
        }
        for t in sorted(topics, key=lambda x: x.get("order", 0))
    ]

    course = {
        "id": "root-cause-prototype",
        "code": "APU-CS",
        # Shown to students (passport cover), so the working label "(prototype)" is dropped.
        "name": re.sub(r"\s*\(prototype\)\s*$", "", meta.get("name") or "", flags=re.I) or "Root Cause concept graph",
    }

    return {
        "meta": meta,
        "course": course,
        "modules": modules,
        "topics": topics,
        "edges": edges,
        "labs": labs,
        "concepts": adapted_concepts,
    }


def mix_option_order(probe: dict) -> dict:
    """Return the probe with its answer options in a mixed order.

    The probe bank is written with the correct answer first. Showing it that way would make
    option A always right, so the order is shuffled here. The shuffle is seeded by the probe id,
    so a probe shows the same order on every request and after every restart. `correctIndex`
    and the `misconceptions` keys are remapped to the new positions; `originalOptions` keeps
    the written order so answers stored before the mix can still be displayed.
    """
    options = list(probe["options"])
    order = list(range(len(options)))
    random.Random(f"punca-option-order:{probe['id']}").shuffle(order)
    new_pos = {old: new for new, old in enumerate(order)}
    return dict(
        probe,
        options=[options[old] for old in order],
        originalOptions=options,
        correctIndex=new_pos[probe["correctIndex"]],
        misconceptions={str(new_pos[int(k)]): tag for k, tag in (probe.get("misconceptions") or {}).items()},
    )


def parse_notes(notes_dir: Path) -> list[dict]:
    chunks: list[dict] = []
    for md in sorted(notes_dir.glob("*.md")):
        current: tuple[str, str] | None = None
        lines: list[str] = []

        def flush() -> None:
            if current:
                text = " ".join(l.strip() for l in lines if l.strip())
                chunks.append({
                    "sourceId": f"{md.name}#{current[0]}",
                    "conceptId": current[0],
                    "title": current[1],
                    "text": text,
                    "file": md.name,
                })

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
        graph_file = data_dir / "concepts" / "root-cause-graph.json"
        if not graph_file.exists():
            graph_file = data_dir / "concepts" / "maths-to-ml.json"
        raw = json.loads(graph_file.read_text(encoding="utf-8"))
        adapted = adapt_concept_graph(raw)

        self.meta: dict = adapted.get("meta") or {}
        self.course: dict = adapted["course"]
        self.modules: list[dict] = adapted.get("modules") or []
        self.topics: list[dict] = adapted.get("topics") or []
        self.edges: list[dict] = adapted.get("edges") or []
        self.labs: list[dict] = adapted["labs"]
        concept_list: list[dict] = adapted["concepts"]

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
            p = mix_option_order(p)
            p = dict(p, type="multiple_choice", misconceptionTags=sorted(set(p.get("misconceptions", {}).values())))
            self.probes[p["id"]] = p
            by_concept[p["conceptId"]].append(p)
        self.probes_by_concept = {
            cid: sorted(ps, key=lambda x: (x.get("difficulty", 1), x["id"]))
            for cid, ps in by_concept.items()
        }

        self.notes = parse_notes(data_dir / "notes")
        self.notes_by_concept: dict[str, list[dict]] = defaultdict(list)
        for ch in self.notes:
            if ch["conceptId"] not in self.concepts:
                raise ContentError(f"note {ch['sourceId']} is for an unknown concept {ch['conceptId']}")
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
        cid_tokens = tokenize(c["id"].replace("-", " "))
        kw = [t for k in c.get("keywords", []) for t in tokenize(k)]
        topic_tokens = tokenize(c.get("topicName", ""))
        area_tokens = tokenize(c.get("area", ""))
        return name * 3 + cid_tokens * 2 + kw * 2 + topic_tokens + area_tokens + tokenize(c["description"])

    # ---- lookups ---------------------------------------------------------------------------
    def name(self, cid: str | None) -> str | None:
        return self.concepts[cid]["name"] if cid and cid in self.concepts else None

    def search_concepts(self, text: str, k: int = 5) -> list[dict]:
        hits = self.concept_index.top(tokenize(text), k)
        return [
            {
                "conceptId": self._concept_ids[i],
                "name": self.concepts[self._concept_ids[i]]["name"],
                "score": round(s, 3),
            }
            for i, s in hits
        ]

    def search_notes(self, text: str, k: int = 3) -> list[dict]:
        return [self.notes[i] for i, _ in self.note_index.top(tokenize(text), k)]

    def lab_for(self, concept_id: str) -> str | None:
        """The topic/lab that targets this concept, or else the first one that depends on it."""
        c = self.concepts.get(concept_id)
        if c and c.get("topicId"):
            return c["topicId"]
        for lab in self.labs:
            if concept_id in lab["targetConceptIds"]:
                return lab["id"]
        for lab in self.labs:
            if any(concept_id in self.graph.ancestors(t) for t in lab["targetConceptIds"]):
                return lab["id"]
        return None

    def public_probe(self, probe: dict) -> dict:
        return {
            "probeId": probe["id"],
            "conceptId": probe["conceptId"],
            "conceptName": self.name(probe["conceptId"]),
            "question": probe["question"],
            "options": probe["options"],
            "difficulty": probe.get("difficulty", 1),
        }

    def catalog_view(self) -> dict:
        levels = self.graph.levels()
        return {
            "meta": self.meta,
            "course": self.course,
            "modules": self.modules,
            "topics": self.topics,
            "edges": self.edges,
            "labs": self.labs,
            "concepts": [
                {
                    "id": c["id"],
                    "name": c["name"],
                    "description": c["description"],
                    "area": c["area"],
                    "moduleId": c.get("moduleId"),
                    "topicId": c.get("topicId"),
                    "topicName": c.get("topicName"),
                    "level": c.get("level", "core"),
                    "optional": c.get("optional", False),
                    "prerequisites": c["prerequisites"],
                    "related": c.get("related", []),
                    "depth": c.get("depth", levels[c["id"]]),
                    "resources": c["resources"],
                    "probeCount": len(c["probeBank"]),
                }
                for c in self.concepts.values()
            ],
        }
