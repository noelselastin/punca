"""Evaluation runner (README section 10). From the repo root:

    python -m data.eval.run              # uses Gemini if GEMINI_API_KEY is set, otherwise offline
    python -m data.eval.run --offline    # keyword-search mapping only (deterministic baseline)

Each item is a simulated student who is missing exactly one concept. Reports:
  mapping      - stuck text mapped to the expected target concept
  engine       - root cause found when starting from the expected target (isolates the engine)
  end-to-end   - root cause found when starting from whatever the mapping chose
Results are written to data/eval/last_run.json.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from content import Catalog  # noqa: E402
from diagnosis.bkt import MasteryBook  # noqa: E402
from diagnosis.engine import DiagnosisEngine  # noqa: E402
from llm.client import LLMClient  # noqa: E402
from llm.service import LLMService  # noqa: E402


def simulate(engine: DiagnosisEngine, cat: Catalog, target: str, gap: str) -> dict:
    book = MasteryBook()
    st = engine.start(engine.new_state(target), book)
    while st["status"] == "in_progress":
        pend = st["pending"]
        probe = cat.probes[pend["probeId"]]
        c = pend["conceptId"]
        knows = not (c == gap or gap in cat.graph.ancestors(c))
        choice = probe["correctIndex"] if knows else (probe["correctIndex"] + 1) % len(probe["options"])
        engine.answer(st, probe["id"], choice, book)
    return st["result"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="never call Gemini")
    ap.add_argument("--sleep", type=float, default=0.0, help="seconds between Gemini calls (free-tier rate limits)")
    args = ap.parse_args()

    cat = Catalog()
    client = LLMClient(offline=True if args.offline else None)
    svc = LLMService(cat, client)
    engine = DiagnosisEngine(cat.graph, cat.probes, cat.probes_by_concept)
    items = json.loads((ROOT / "data" / "eval" / "stuck_points.json").read_text(encoding="utf-8"))["items"]

    rows, llm_errors = [], 0
    for it in items:
        m = svc.map_stuck_point(it["stuckInput"])
        if m.get("llmError"):
            llm_errors += 1
        mapped = m.get("targetConceptId")
        eng = simulate(engine, cat, it["expectedTarget"], it["gap"])
        e2e = simulate(engine, cat, mapped, it["gap"]) if mapped else {"rootCauseConceptId": None, "probesUsed": 0}
        rows.append({"id": it["id"], "expectedTarget": it["expectedTarget"], "mapped": mapped,
                     "mappingOk": mapped == it["expectedTarget"], "gap": it["gap"],
                     "engineRoot": eng["rootCauseConceptId"], "engineOk": eng["rootCauseConceptId"] == it["gap"],
                     "e2eRoot": e2e["rootCauseConceptId"], "e2eOk": e2e["rootCauseConceptId"] == it["gap"],
                     "probes": eng["probesUsed"], "mappingSource": m["source"]})
        if args.sleep and client.available:
            time.sleep(args.sleep)

    n = len(rows)
    summary = {"mode": client.mode, "model": client.model if client.available else None, "items": n,
               "mappingAccuracy": round(sum(r["mappingOk"] for r in rows) / n, 3),
               "engineRootCauseAccuracy": round(sum(r["engineOk"] for r in rows) / n, 3),
               "endToEndRootCauseAccuracy": round(sum(r["e2eOk"] for r in rows) / n, 3),
               "meanProbes": round(sum(r["probes"] for r in rows) / n, 2), "llmErrors": llm_errors,
               "ranAt": time.strftime("%Y-%m-%d %H:%M:%S")}

    print(f"{'id':4} {'map':4} {'eng':4} {'e2e':4}  expected target -> mapped | gap -> engine root")
    for r in rows:
        ok = lambda b: "ok" if b else "--"  # noqa: E731
        print(f"{r['id']:4} {ok(r['mappingOk']):4} {ok(r['engineOk']):4} {ok(r['e2eOk']):4}  "
              f"{r['expectedTarget']} -> {r['mapped']} | {r['gap']} -> {r['engineRoot']}")
    print(json.dumps(summary, indent=1))
    (ROOT / "data" / "eval" / "last_run.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
