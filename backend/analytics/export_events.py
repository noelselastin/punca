"""Export anonymised diagnosis events as newline-delimited JSON for BigQuery (README section 8).

From backend/:   python -m analytics.export_events > diagnosis_events.ndjson
Then:            bq load --source_format=NEWLINE_DELIMITED_JSON <dataset>.diagnosis_events diagnosis_events.ndjson
"""
from __future__ import annotations

import json
import sys

import config
from store.local_store import LocalStore

FIELDS = ("courseId", "labId", "targetConceptId", "rootCauseConceptId", "timestamp", "synthetic")


def main() -> int:
    store = LocalStore(config.STORE_PATH)
    for ev in store.list("diagnosisEvents"):
        sys.stdout.write(json.dumps({k: ev.get(k) for k in FIELDS}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
