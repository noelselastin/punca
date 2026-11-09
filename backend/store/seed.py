"""Synthetic demo data (README section 11: demo data is fake).

Creates two demo login accounts, a synthetic cohort of 46 students with diagnosis history and weekly
availability, lecturer consultation slots and two existing study circles. Every synthetic record has
"synthetic": true. Run `python -m store.seed --reset` from backend/ to wipe and re-seed the local store.
"""
from __future__ import annotations

import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

import auth
import config
from content import Catalog
from scheduling.circles import ALL_SLOTS, propose_circle
from store.local_store import LocalStore

# Demo-only login accounts for the local prototype. Never reuse these anywhere real.
DEMO_PASSWORD = "punca-demo-2026"
DEMO_STUDENT_EMAIL = "student@punca.demo"
DEMO_LECTURER_EMAIL = "lecturer@punca.demo"
DEMO_STUDENT_UID = "u-demo-student"
DEMO_LECTURER_UID = "u-demo-lecturer"

SYNTHETIC_NAMES = [
    "Aina", "Wei Jie", "Priya", "Hafiz", "Mei Ling", "Arjun", "Nurul", "Daniel", "Siti", "Kumar", "Farah",
    "Jun Hao", "Divya", "Amir", "Hui Min", "Rahul", "Aisyah", "Kevin", "Shalini", "Irfan", "Xin Yi", "Vikram",
    "Balqis", "Jason", "Kavitha", "Haziq", "Yee Ling", "Naveen", "Zara", "Ethan", "Anis", "Ravi", "Sofia",
    "Adam", "Li Wen", "Deepa", "Imran", "Grace", "Syafiq", "Mira", "Hong Wei", "Lakshmi", "Danish", "Chloe",
    "Arif", "Nisha",
]

# Gaps that are common in the synthetic cohort (weights for random root causes).
COMMON_GAPS = {"chain-rule": 6, "matrix-multiplication": 5, "logarithms": 4, "conditional-probability": 4,
               "exponents": 3, "function-composition": 3, "dot-product": 3, "derivative-rules": 3,
               "partial-derivatives": 3, "summation": 2}


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _user(uid: str, role: str, name: str, **extra) -> dict:
    base = {"uid": uid, "role": role, "name": name, "email": None, "passwordHash": None,
            "programme": None, "year": None, "department": None, "courseIds": ["maths-for-ml"],
            "availability": [], "consent": {"joinCircles": False, "shareNameWithCircle": False,
                                            "shareNameWithLecturer": False, "sharePassport": False},
            "synthetic": False, "createdAt": _iso(datetime.now(timezone.utc))}
    base.update(extra)
    return base


def seed_store(store: LocalStore, cat: Catalog, rng_seed: int = 2026) -> None:
    rng = random.Random(rng_seed)
    now = datetime.now(timezone.utc)
    store.clear()

    # --- demo login accounts --------------------------------------------------------------
    store.put("users", DEMO_STUDENT_UID, _user(
        DEMO_STUDENT_UID, "student", "Demo Student", email=DEMO_STUDENT_EMAIL,
        passwordHash=auth.hash_password(DEMO_PASSWORD), programme="BSc (Hons) Computer Science (AI)", year=2,
        availability=["Mon-10", "Tue-14", "Tue-15", "Wed-16", "Thu-11", "Thu-12"], demoAccount=True), save=False)
    store.put("users", DEMO_LECTURER_UID, _user(
        DEMO_LECTURER_UID, "lecturer", "Dr. Demo Lecturer", email=DEMO_LECTURER_EMAIL,
        passwordHash=auth.hash_password(DEMO_PASSWORD), department="School of Computing (demo)",
        demoAccount=True), save=False)
    store.put("users", "u-syn-lect-kaur", _user("u-syn-lect-kaur", "lecturer", "Ms. Kaur (synthetic)",
                                                department="School of Computing (demo)", synthetic=True), save=False)

    # --- lecturer slots -------------------------------------------------------------------
    slots = [
        {"id": "slot-1", "lecturerUid": DEMO_LECTURER_UID, "day": "Tue", "start": 14, "end": 16, "capacity": 8,
         "kind": "consultation", "linkedConceptIds": ["chain-rule", "derivative-rules", "derivatives",
                                                      "partial-derivatives", "gradient-vector", "gradient-descent",
                                                      "backpropagation", "exp-log-derivatives"]},
        {"id": "slot-2", "lecturerUid": DEMO_LECTURER_UID, "day": "Thu", "start": 11, "end": 12, "capacity": 6,
         "kind": "consultation", "linkedConceptIds": ["matrix-multiplication", "matrices", "dot-product",
                                                      "vectors", "transpose", "forward-pass"]},
        {"id": "slot-3", "lecturerUid": "u-syn-lect-kaur", "day": "Wed", "start": 15, "end": 17, "capacity": 6,
         "kind": "consultation", "linkedConceptIds": ["conditional-probability", "bayes-theorem", "probability",
                                                      "expected-value", "logarithms", "exponents",
                                                      "cross-entropy", "softmax"]},
        {"id": "slot-4", "lecturerUid": "u-syn-lect-kaur", "day": "Fri", "start": 10, "end": 11, "capacity": 4,
         "kind": "consultation", "linkedConceptIds": ["functions", "function-composition", "algebra",
                                                      "linear-functions", "limits", "summation"]},
    ]
    for s in slots:
        store.put("lecturerSlots", s["id"], dict(s, courseId=cat.course["id"], synthetic=True,
                                                  createdAt=_iso(now)), save=False)

    # --- synthetic students ---------------------------------------------------------------
    # The first students share planned gaps so the demo can form circles.
    planned = (["chain-rule"] * 7) + (["matrix-multiplication"] * 6) + (["conditional-probability"] * 5)
    anchor = {"chain-rule": ["Tue-14", "Tue-15"], "matrix-multiplication": ["Thu-11"],
              "conditional-probability": ["Wed-15", "Wed-16"]}
    gap_ids, gap_w = list(COMMON_GAPS), list(COMMON_GAPS.values())
    lab_by_id = {lab["id"]: lab for lab in cat.labs}
    latest_roots: dict[str, str] = {}

    for i, name in enumerate(SYNTHETIC_NAMES):
        uid = f"u-syn-{i + 1:02d}"
        avail = set(rng.sample(ALL_SLOTS, rng.randint(7, 13)))
        latest_root = planned[i] if i < len(planned) else None
        if latest_root:
            avail.update(anchor[latest_root])
        consent = {"joinCircles": (i < len(planned)) or rng.random() < 0.7,
                   "shareNameWithCircle": rng.random() < 0.7, "shareNameWithLecturer": rng.random() < 0.4,
                   "sharePassport": False}
        store.put("users", uid, _user(uid, "student", name, programme=rng.choice(
            ["BSc (Hons) Computer Science (AI)", "BSc (Hons) Data Science", "BSc (Hons) Software Engineering"]),
            year=rng.choice([1, 2, 2, 3]), availability=sorted(avail, key=ALL_SLOTS.index), consent=consent,
            synthetic=True), save=False)

        n_events = rng.randint(1, 3)
        for k in range(n_events):
            last = k == n_events - 1
            if last and latest_root:
                root = latest_root
                lab = {"chain-rule": "lab5", "matrix-multiplication": "lab3", "conditional-probability": "lab4"}[root]
                target = next(t for t in lab_by_id[lab]["targetConceptIds"]
                              if t == root or root in cat.graph.ancestors(t))
            else:
                root = rng.choices(gap_ids, gap_w)[0]
                options = [(lab["id"], t) for lab in cat.labs for t in lab["targetConceptIds"]
                           if t == root or root in cat.graph.ancestors(t)]
                if not options:
                    continue
                lab, target = rng.choice(options)
            when = now - timedelta(days=rng.randint(1 if last else 4, 6 if last else 20), hours=rng.randint(0, 9))
            did = f"d-syn-{uid}-{k}"
            store.put("diagnoses", did, {
                "id": did, "uid": uid, "courseId": cat.course["id"], "stuckInput": None,
                "targetConceptId": target, "rootCauseConceptId": root, "status": "done",
                "path": cat.graph.path(target, root), "createdAt": _iso(when), "synthetic": True}, save=False)
            store.put("diagnosisEvents", f"ev-{uuid.uuid4().hex[:10]}", {
                "courseId": cat.course["id"], "labId": lab, "targetConceptId": target,
                "rootCauseConceptId": root, "timestamp": _iso(when), "synthetic": True}, save=False)
            if last:
                latest_roots[uid] = root
                store.put("mastery", f"{uid}_{root}", {"uid": uid, "conceptId": root, "pKnown": 0.18,
                                                         "evidenceCount": 2, "lastUpdated": _iso(when)}, save=False)

    # --- two existing circles so the lecturer view has something to act on ----------------
    users = {u["uid"]: u for u in store.list("users")}
    for concept, status, confirmed in (("matrix-multiplication", "forming", False),
                                       ("conditional-probability", "scheduled", True)):
        members = {uid: users[uid]["availability"] for uid, root in latest_roots.items()
                   if root == concept and users[uid]["consent"]["joinCircles"]}
        prop = propose_circle(concept, members, slots, {}, config.MIN_GROUP_SIZE, config.MAX_GROUP_SIZE)
        if prop:
            cid = f"c-seed-{concept}"
            store.put("studyCircles", cid, {
                "id": cid, "courseId": cat.course["id"], "conceptId": concept, "memberUids": prop["memberUids"],
                "status": status, "proposedSlot": prop["proposedSlot"], "lecturerSlotId": prop["lecturerSlotId"],
                "lecturerConfirmed": confirmed and bool(prop["lecturerSlotId"]), "peerMentorUid": None,
                "createdAt": _iso(now - timedelta(days=1)), "synthetic": True}, save=False)
    store.save()


if __name__ == "__main__":
    if "--reset" not in sys.argv:
        print("usage: python -m store.seed --reset   (wipes backend/var/store.json and re-seeds demo data)")
        sys.exit(1)
    s = LocalStore(config.STORE_PATH)
    seed_store(s, Catalog())
    print(f"re-seeded {config.STORE_PATH}")
