"""Local JSON document store with Firestore-shaped collections (README section 7).

The MVP keeps state in backend/var/store.json so it runs with no cloud account. The collection and
document shapes match the planned Firestore layout, so a Firestore adapter can replace this class.
"""
from __future__ import annotations

import copy
import json
import logging
import os
import threading
from pathlib import Path
from typing import Callable, Iterable

log = logging.getLogger("punca.store")

COLLECTIONS = ("users", "authTokens", "mastery", "diagnoses", "studyCircles", "lecturerSlots", "diagnosisEvents",
               "stamps")


class LocalStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self._lock = threading.RLock()
        self.data: dict[str, dict[str, dict]] = {c: {} for c in COLLECTIONS}
        if self.path.exists():
            try:
                loaded = json.loads(self.path.read_text(encoding="utf-8"))
                for c in COLLECTIONS:
                    self.data[c] = loaded.get(c, {})
            except (OSError, json.JSONDecodeError) as exc:
                backup = self.path.with_suffix(".corrupt.json")
                log.error("store file unreadable (%s); moving it to %s and starting empty", exc, backup)
                os.replace(self.path, backup)

    @property
    def empty(self) -> bool:
        return not any(self.data[c] for c in COLLECTIONS)

    def save(self) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=1), encoding="utf-8")
            os.replace(tmp, self.path)

    def get(self, col: str, doc_id: str) -> dict | None:
        with self._lock:
            d = self.data[col].get(doc_id)
            return copy.deepcopy(d) if d is not None else None

    def put(self, col: str, doc_id: str, doc: dict, save: bool = True) -> None:
        with self._lock:
            self.data[col][doc_id] = copy.deepcopy(doc)
            if save:
                self.save()

    def delete(self, col: str, doc_id: str, save: bool = True) -> None:
        with self._lock:
            self.data[col].pop(doc_id, None)
            if save:
                self.save()

    def create_user(self, user: dict) -> str | None:
        """Atomically enforce account identifiers within this single-process local store.

        Return the conflicting field, or persist the account and return None.
        Existing demo/legacy users without a student ID remain valid.
        """
        with self._lock:
            for field in ("email", "studentId"):
                key = (user.get(field) or "").strip().casefold()
                if key and any((existing.get(field) or "").strip().casefold() == key
                               for existing in self.data["users"].values()):
                    return field
            self.put("users", user["uid"], user)
            return None

    def list(self, col: str, where: Callable[[dict], bool] | None = None) -> list[dict]:
        with self._lock:
            docs: Iterable[dict] = self.data[col].values()
            return [copy.deepcopy(d) for d in docs if where is None or where(d)]

    def clear(self) -> None:
        with self._lock:
            self.data = {c: {} for c in COLLECTIONS}
