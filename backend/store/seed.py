"""Synthetic demo data for Punca.

Creates the demo student login account, a synthetic cohort of 46 peer students with diagnosis history
and weekly availability, and two existing peer study circles with Google Meet and Google Chat rooms.
Every synthetic record has "synthetic": true.
Run `python -m store.seed --reset` from backend/ to wipe and re-seed the local store.
"""
from __future__ import annotations

import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

import auth
import config
import google_workspace as gws
from content import Catalog
from scheduling.circles import ALL_SLOTS, propose_circle
from store.local_store import LocalStore

# Demo-only login accounts for the local prototype.
DEMO_PASSWORD = "punca-demo-2026"
DEMO_STUDENT_EMAIL = "student@punca.demo"
DEMO_STUDENT_UID = "u-demo-student"

DEMO_ACCOUNTS = [
    {
        "uid": DEMO_STUDENT_UID,
        "name": "Demo Student",
        "email": DEMO_STUDENT_EMAIL,
        "studentId": "TP068421",
        "programme": "BSc (Hons) Computer Science (AI)",
        "year": 2,
        "cover": "navy",
        "label": "Fresh Student (Empty Passport)",
        "hint": "Clean slate for live demo walkthroughs",
    },
    {
        "uid": "u-demo-aisyah",
        "name": "Aisyah Rahman",
        "email": "aisyah.student@demo.punca.edu",
        "studentId": "TP071204",
        "programme": "BSc (Hons) Computer Science (AI)",
        "year": 2,
        "cover": "teal",
        "label": "Aisyah · Mid-Journey",
        "hint": "5 completed stamps, 1 re-entry, Chain Rule gap",
    },
    {
        "uid": "u-demo-hafiz",
        "name": "Hafiz Tan",
        "email": "hafiz.student@demo.punca.edu",
        "studentId": "TP072819",
        "programme": "BSc (Hons) Software Engineering",
        "year": 2,
        "cover": "forest",
        "label": "Hafiz · Circle Partner",
        "hint": "Shares Chain Rule gap & Tue 14:00 slot with Aisyah",
    },
    {
        "uid": "u-demo-priya",
        "name": "Priya Nair",
        "email": "priya.student@demo.punca.edu",
        "studentId": "TP065110",
        "programme": "BSc (Hons) Data Science",
        "year": 3,
        "cover": "maroon",
        "label": "Priya · Advanced Passport",
        "hint": "12 completed stamps + 2 needing re-entry across modules",
    },
    {
        "uid": "u-demo-qa",
        "name": "QA Tester",
        "email": "qa.tester@demo.punca.edu",
        "studentId": "TP079900",
        "programme": "BSc (Hons) Computer Science",
        "year": 1,
        "cover": "plum",
        "label": "QA Tester · Onboarding",
        "hint": "Opens directly on Passport Setup screen",
    },
]

SYNTHETIC_NAMES = [
    "Aina", "Wei Jie", "Priya", "Hafiz", "Mei Ling", "Arjun", "Nurul", "Daniel", "Siti", "Kumar", "Farah",
    "Jun Hao", "Divya", "Amir", "Hui Min", "Rahul", "Aisyah", "Kevin", "Shalini", "Irfan", "Xin Yi", "Vikram",
    "Balqis", "Jason", "Kavitha", "Haziq", "Yee Ling", "Naveen", "Zara", "Ethan", "Anis", "Ravi", "Sofia",
    "Adam", "Li Wen", "Deepa", "Imran", "Grace", "Syafiq", "Mira", "Hong Wei", "Lakshmi", "Danish", "Chloe",
    "Arif", "Nisha",
]

# Gaps that are common in the synthetic cohort (weights for random root causes using Root Cause graph IDs).
COMMON_GAPS = {
    "CM-CHAIN": 6,
    "CM-MATMUL": 5,
    "FM-EXP": 4,
    "CM-COND": 4,
    "PY-RECUR": 4,
    "DB-JOIN": 4,
    "CM-GRAPH": 3,
    "CM-COMP": 3,
    "CM-VEC": 3,
    "CM-DERRULES": 3,
    "CM-PARTIAL": 3,
    "JV-POLY": 3,
    "CM-SIGMA": 2,
}


def _iso(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _user(uid: str, name: str, **extra) -> dict:
    base = {
        "uid": uid,
        "role": "student",
        "name": name,
        "email": None,
        "passwordHash": None,
        "programme": None,
        "year": None,
        "courseIds": ["root-cause-prototype"],
        "availability": [],
        "consent": {
            "joinCircles": False,
            "shareNameWithCircle": False,
            "sharePassport": False,
        },
        "synthetic": False,
        "createdAt": _iso(datetime.now(timezone.utc)),
    }
    base.update(extra)
    return base


def seed_store(store: LocalStore, cat: Catalog, rng_seed: int = 2026) -> None:
    rng = random.Random(rng_seed)
    now = datetime.now(timezone.utc)
    store.clear()

    # --- demo student login account -------------------------------------------------------
    demo_user = _user(
        DEMO_STUDENT_UID,
        "Demo Student",
        email=DEMO_STUDENT_EMAIL,
        university="Asia Pacific University (APU)",
        studentId="TP068421",
        passwordHash=auth.hash_password(DEMO_PASSWORD),
        programme="BSc (Hons) Computer Science (AI)",
        year=2,
        availability=["Mon-10", "Tue-14", "Tue-15", "Wed-16", "Thu-11", "Thu-12"],
        demoAccount=True,
        passportStyle={
            "cover": "navy",
            "displayName": "Demo Student",
            "photoUrl": None,
            "motto": "Master CS & Maths foundations without guessing",
            "focusLabIds": ["T-CM7", "T-PY4", "T-DB4"],
            "customLabs": ["CS204 Operating Systems Lab"],
            "setupDone": True,
        },
    )
    gws.ensure_workspace(demo_user)
    store.put("users", DEMO_STUDENT_UID, demo_user, save=False)

    # --- synthetic peer students ----------------------------------------------------------
    planned = (
        (["CM-CHAIN"] * 7)
        + (["CM-MATMUL"] * 6)
        + (["CM-COND"] * 5)
        + (["PY-RECUR"] * 4)
        + (["DB-JOIN"] * 4)
    )
    anchor = {
        "CM-CHAIN": ["Tue-14", "Tue-15"],
        "CM-MATMUL": ["Thu-11"],
        "CM-COND": ["Wed-15", "Wed-16"],
        "PY-RECUR": ["Mon-10", "Tue-14"],
        "DB-JOIN": ["Thu-12", "Wed-16"],
    }
    planned_lab = {
        "CM-CHAIN": "T-CM7",
        "CM-MATMUL": "T-CM6",
        "CM-COND": "T-CM5",
        "PY-RECUR": "T-PY4",
        "DB-JOIN": "T-DB4",
    }
    gap_ids, gap_w = list(COMMON_GAPS), list(COMMON_GAPS.values())
    lab_by_id = {lab["id"]: lab for lab in cat.labs}
    latest_roots: dict[str, str] = {}

    for i, name in enumerate(SYNTHETIC_NAMES):
        uid = f"u-syn-{i + 1:02d}"
        avail = set(rng.sample(ALL_SLOTS, rng.randint(7, 13)))
        latest_root = planned[i] if i < len(planned) else None
        if latest_root:
            avail.update(anchor[latest_root])
        consent = {
            "joinCircles": (i < len(planned)) or rng.random() < 0.7,
            "shareNameWithCircle": rng.random() < 0.75,
            "sharePassport": False,
        }
        store.put(
            "users",
            uid,
            _user(
                uid,
                name,
                programme=rng.choice([
                    "BSc (Hons) Computer Science (AI)",
                    "BSc (Hons) Data Science",
                    "BSc (Hons) Software Engineering",
                ]),
                year=rng.choice([1, 2, 2, 3]),
                availability=sorted(avail, key=ALL_SLOTS.index),
                consent=consent,
                synthetic=True,
            ),
            save=False,
        )

        n_events = rng.randint(1, 3)
        for k in range(n_events):
            last = k == n_events - 1
            if last and latest_root:
                root = latest_root
                lab = planned_lab[root]
                target = next(
                    t for t in lab_by_id[lab]["targetConceptIds"]
                    if t == root or root in cat.graph.ancestors(t)
                )
            else:
                root = rng.choices(gap_ids, gap_w)[0]
                options = [
                    (lab["id"], t)
                    for lab in cat.labs
                    for t in lab["targetConceptIds"]
                    if t == root or root in cat.graph.ancestors(t)
                ]
                if not options:
                    continue
                lab, target = rng.choice(options)
            when = now - timedelta(days=rng.randint(1 if last else 4, 6 if last else 20), hours=rng.randint(0, 9))
            did = f"d-syn-{uid}-{k}"
            store.put(
                "diagnoses",
                did,
                {
                    "id": did,
                    "uid": uid,
                    "courseId": cat.course["id"],
                    "stuckInput": None,
                    "targetConceptId": target,
                    "rootCauseConceptId": root,
                    "status": "done",
                    "path": cat.graph.path(target, root),
                    "createdAt": _iso(when),
                    "synthetic": True,
                },
                save=False,
            )
            store.put(
                "diagnosisEvents",
                f"ev-{uuid.uuid4().hex[:10]}",
                {
                    "courseId": cat.course["id"],
                    "labId": lab,
                    "targetConceptId": target,
                    "rootCauseConceptId": root,
                    "timestamp": _iso(when),
                    "synthetic": True,
                },
                save=False,
            )
            if last:
                latest_roots[uid] = root
                store.put(
                    "mastery",
                    f"{uid}_{root}",
                    {
                        "uid": uid,
                        "conceptId": root,
                        "pKnown": 0.18,
                        "evidenceCount": 2,
                        "lastUpdated": _iso(when),
                    },
                    save=False,
                )

    # --- two existing peer circles --------------------------------------------------------
    users = {u["uid"]: u for u in store.list("users")}
    for concept in ("CM-MATMUL", "CM-COND"):
        members = {
            uid: users[uid]["availability"]
            for uid, root in latest_roots.items()
            if root == concept and users[uid]["consent"]["joinCircles"]
        }
        prop = propose_circle(concept, members, config.MIN_GROUP_SIZE, config.MAX_GROUP_SIZE)
        if prop:
            cid = f"c-seed-{concept}"
            store.put(
                "studyCircles",
                cid,
                {
                    "id": cid,
                    "courseId": cat.course["id"],
                    "conceptId": concept,
                    "memberUids": prop["memberUids"],
                    "status": "scheduled",
                    "proposedSlot": prop["proposedSlot"],
                    "mode": "peer",
                    "meetUrl": None,
                    "meetLive": False,
                    "messages": [
                        {
                            "id": f"msg-seed-{concept}-1",
                            "sender": "Study Circle",
                            "text": (
                                f"Welcome to the {cat.name(concept)} peer study circle! "
                                "Start a Google Meet room and paste the link above, or post questions below."
                            ),
                            "createdAt": _iso(now - timedelta(hours=6)),
                        }
                    ],
                    "createdAt": _iso(now - timedelta(days=1)),
                    "synthetic": True,
                },
                save=False,
            )
    ensure_demo_users(store, cat, save=False)
    store.save()


def _put_stamp(store: LocalStore, uid: str, cid: str, p_known: float, when: datetime, renewed: datetime | None = None) -> None:
    store.put(
        "mastery",
        f"{uid}_{cid}",
        {
            "uid": uid,
            "conceptId": cid,
            "pKnown": round(p_known, 4),
            "evidenceCount": 3,
            "lastUpdated": _iso(renewed or when),
        },
        save=False,
    )
    stamp = {
        "uid": uid,
        "conceptId": cid,
        "tier": "completed",
        "earnedAt": _iso(when),
        "basedOnDiagnosisId": None,
        "shareable": True,
    }
    if renewed:
        stamp["renewedAt"] = _iso(renewed)
    store.put("stamps", f"{uid}_{cid}", stamp, save=False)


def ensure_demo_users(store: LocalStore, cat: Catalog, save: bool = True) -> None:
    """Non-destructively ensure all demo/testing personas exist and migrate older workspace/circle records."""
    now = datetime.now(timezone.utc)
    pw_hash = auth.hash_password(DEMO_PASSWORD)
    dirty = False

    # Migrate existing circles so fake Meet codes from earlier builds are cleared
    for c in store.list("studyCircles"):
        if c.get("meetUrl") and not c.get("meetLive"):
            c["meetUrl"] = None
            c["meetLive"] = False
            store.put("studyCircles", c["id"], c, save=False)
            dirty = True

    # Ensure every existing non-synthetic user has an up-to-date workspace
    for u in store.list("users", lambda u: not u.get("synthetic")):
        before_ver = (u.get("googleWorkspace") or {}).get("starterVersion")
        gws.ensure_workspace(u)
        if (u.get("googleWorkspace") or {}).get("starterVersion") != before_ver:
            store.put("users", u["uid"], u, save=False)
            dirty = True

    # 1. Aisyah Rahman — Mid-journey persona (5 completed stamps, 1 re-entry, open CM-CHAIN diagnosis)
    if not store.get("users", "u-demo-aisyah"):
        aisyah = _user(
            "u-demo-aisyah",
            "Aisyah Rahman",
            email="aisyah.student@demo.punca.edu",
            university="Asia Pacific University (APU)",
            studentId="TP071204",
            passwordHash=pw_hash,
            programme="BSc (Hons) Computer Science (AI)",
            year=2,
            availability=["Mon-10", "Tue-14", "Tue-15", "Thu-11", "Thu-12"],
            consent={"joinCircles": True, "shareNameWithCircle": True, "sharePassport": True},
            demoAccount=True,
            passportStyle={
                "cover": "teal",
                "displayName": "Aisyah Rahman",
                "photoUrl": None,
                "motto": "Find the root cause, not just the answer",
                "focusLabIds": ["T-CM7", "T-PY4", "T-DB4"],
                "customLabs": ["CM Lab 7 · Gradient Descent"],
                "setupDone": True,
            },
        )
        ws = gws.ensure_workspace(aisyah)
        ws["docs"].insert(
            0,
            {
                "id": "gdoc-aisyah-chain",
                "title": f"Punca Notes · {cat.name('CM-CHAIN')} → {cat.name('CM-GRADDESC')}",
                "conceptId": "CM-CHAIN",
                "diagnosisId": "d-demo-aisyah-1",
                "content": (
                    "# Study Notes: Chain Rule (for Gradient Descent)\n\n"
                    "**Original Question / Lab Brief:** Minimising f(x, y) with gradient descent when composite terms appear.\n\n"
                    "**Remediation Route:** Chain rule → Partial derivatives → Gradient descent\n\n"
                    "## Key Takeaways\n"
                    "- Differentiate the outer function first, then multiply by the derivative of the inner function.\n"
                    "- In `d/dy (2y + 1)^2 = 2(2y + 1) * 2`, forgetting the inner `* 2` scales the gradient wrong."
                ),
                "url": None,
                "live": False,
                "updatedAt": _iso(now - timedelta(hours=3)),
                "createdAt": _iso(now - timedelta(hours=3)),
            },
        )
        ws["tasks"].insert(
            0,
            {
                "id": "gtask-aisyah-chain",
                "title": f"Step 1: Review & pass re-check for {cat.name('CM-CHAIN')}",
                "notes": "From diagnosis on Gradient Descent. Complete your Passport stamp for Chain Rule.",
                "due": (now + timedelta(days=1)).date().isoformat(),
                "completed": False,
                "completedAt": None,
                "live": False,
                "conceptId": "CM-CHAIN",
                "diagnosisId": "d-demo-aisyah-1",
                "createdAt": _iso(now - timedelta(hours=3)),
            },
        )
        store.put("users", aisyah["uid"], aisyah, save=False)

        for idx, cid in enumerate(("FM-ARITH", "FM-ALG", "FM-FUNC", "CM-LIM", "CM-DER")):
            if cid in cat.concepts:
                _put_stamp(store, aisyah["uid"], cid, 0.86, now - timedelta(days=10 - idx))
        # Slipped stamp -> shows "Re-entry required"
        if "CM-DERRULES" in cat.concepts:
            _put_stamp(store, aisyah["uid"], "CM-DERRULES", 0.48, now - timedelta(days=12))
        # Gap on CM-CHAIN & shaky on CM-PARTIAL
        store.put(
            "mastery",
            "u-demo-aisyah_CM-CHAIN",
            {"uid": "u-demo-aisyah", "conceptId": "CM-CHAIN", "pKnown": 0.22, "evidenceCount": 2, "lastUpdated": _iso(now - timedelta(hours=3))},
            save=False,
        )
        store.put(
            "mastery",
            "u-demo-aisyah_CM-PARTIAL",
            {"uid": "u-demo-aisyah", "conceptId": "CM-PARTIAL", "pKnown": 0.52, "evidenceCount": 2, "lastUpdated": _iso(now - timedelta(hours=3))},
            save=False,
        )
        path = cat.graph.path("CM-GRADDESC", "CM-CHAIN")
        store.put(
            "diagnoses",
            "d-demo-aisyah-1",
            {
                "id": "d-demo-aisyah-1",
                "uid": "u-demo-aisyah",
                "courseId": cat.course["id"],
                "labId": "T-CM7",
                "stuckInput": "Minimising f(x, y) = (x - 3)^2 + (2y + 1)^2 with gradient descent and partial derivatives",
                "targetConceptId": "CM-GRADDESC",
                "rootCauseConceptId": "CM-CHAIN",
                "status": "done",
                "path": path,
                "relatedConcepts": [{"id": r, "name": cat.name(r)} for r in cat.graph.related("CM-CHAIN")],
                "probesAsked": 6,
                "answers": [],
                "confidenceSummary": {
                    "total": 6,
                    "overallConfidence": "medium",
                    "calibration": "Well-calibrated — you flagged uncertainty on composite derivatives.",
                    "confidentCorrect": 3,
                    "unsureCorrect": 1,
                    "overconfidentWrong": 1,
                    "admittedGaps": 1,
                },
                "summary": "Root cause traced from Gradient Descent back to Chain Rule.",
                "createdAt": _iso(now - timedelta(hours=3)),
                "completedAt": _iso(now - timedelta(hours=3)),
            },
            save=False,
        )
        dirty = True

    # 2. Hafiz Tan — Study Circle partner sharing the CM-CHAIN gap and Tue-14/Tue-15 slots
    if not store.get("users", "u-demo-hafiz"):
        hafiz = _user(
            "u-demo-hafiz",
            "Hafiz Tan",
            email="hafiz.student@demo.punca.edu",
            university="Asia Pacific University (APU)",
            studentId="TP072819",
            passwordHash=pw_hash,
            programme="BSc (Hons) Software Engineering",
            year=2,
            availability=["Tue-14", "Tue-15", "Wed-16", "Thu-11"],
            consent={"joinCircles": True, "shareNameWithCircle": True, "sharePassport": True},
            demoAccount=True,
            passportStyle={
                "cover": "forest",
                "displayName": "Hafiz Tan",
                "photoUrl": None,
                "motto": "Step by step from foundations to code",
                "focusLabIds": ["T-CM7", "T-PY4", "T-JV3"],
                "customLabs": [],
                "setupDone": True,
            },
        )
        gws.ensure_workspace(hafiz)
        store.put("users", hafiz["uid"], hafiz, save=False)
        for idx, cid in enumerate(("FM-ARITH", "FM-ALG", "FC-VAR")):
            if cid in cat.concepts:
                _put_stamp(store, hafiz["uid"], cid, 0.84, now - timedelta(days=8 - idx))
        store.put(
            "mastery",
            "u-demo-hafiz_CM-CHAIN",
            {"uid": "u-demo-hafiz", "conceptId": "CM-CHAIN", "pKnown": 0.20, "evidenceCount": 2, "lastUpdated": _iso(now - timedelta(hours=5))},
            save=False,
        )
        store.put(
            "diagnoses",
            "d-demo-hafiz-1",
            {
                "id": "d-demo-hafiz-1",
                "uid": "u-demo-hafiz",
                "courseId": cat.course["id"],
                "labId": "T-CM7",
                "stuckInput": "Stuck on composite derivatives when computing gradients in Lab 7",
                "targetConceptId": "CM-GRADDESC",
                "rootCauseConceptId": "CM-CHAIN",
                "status": "done",
                "path": cat.graph.path("CM-GRADDESC", "CM-CHAIN"),
                "probesAsked": 5,
                "answers": [],
                "summary": "Root cause traced to Chain Rule.",
                "createdAt": _iso(now - timedelta(hours=5)),
                "completedAt": _iso(now - timedelta(hours=5)),
            },
            save=False,
        )
        dirty = True

    # 3. Priya Nair — Advanced student with 12 completed stamps + 2 needing re-entry
    if not store.get("users", "u-demo-priya"):
        priya = _user(
            "u-demo-priya",
            "Priya Nair",
            email="priya.student@demo.punca.edu",
            university="Asia Pacific University (APU)",
            studentId="TP065110",
            passwordHash=pw_hash,
            programme="BSc (Hons) Data Science",
            year=3,
            availability=["Mon-11", "Wed-14", "Thu-11", "Fri-10"],
            consent={"joinCircles": True, "shareNameWithCircle": True, "sharePassport": True},
            demoAccount=True,
            passportStyle={
                "cover": "maroon",
                "displayName": "Priya Nair",
                "photoUrl": None,
                "motto": "Solid foundations across every module",
                "focusLabIds": ["T-CM6", "T-PY4", "T-JV4", "T-DB4"],
                "customLabs": ["Data Science Capstone Prep"],
                "setupDone": True,
            },
        )
        gws.ensure_workspace(priya)
        store.put("users", priya["uid"], priya, save=False)
        completed_cids = [
            "FM-ARITH", "FM-ALG", "FM-FUNC", "FM-EXP",
            "FC-VAR", "FC-CTRL", "FC-FUNC",
            "CM-LIM", "CM-DER", "CM-VEC",
            "PY-FUNC", "DB-REL",
        ]
        for idx, cid in enumerate(completed_cids):
            if cid in cat.concepts:
                _put_stamp(store, priya["uid"], cid, 0.88, now - timedelta(days=20 - idx))
        for cid in ("PY-SCOPE", "DB-NORM"):
            if cid in cat.concepts:
                _put_stamp(store, priya["uid"], cid, 0.46, now - timedelta(days=15))
        if "JV-INTERF" in cat.concepts:
            store.put(
                "mastery",
                "u-demo-priya_JV-INTERF",
                {"uid": "u-demo-priya", "conceptId": "JV-INTERF", "pKnown": 0.54, "evidenceCount": 2, "lastUpdated": _iso(now - timedelta(days=2))},
                save=False,
            )
        dirty = True

    # 4. QA Tester — Brand-new onboarding account (setupDone: False)
    if not store.get("users", "u-demo-qa"):
        qa = _user(
            "u-demo-qa",
            "QA Tester",
            email="qa.tester@demo.punca.edu",
            university="Asia Pacific University (APU)",
            studentId="TP079900",
            passwordHash=pw_hash,
            programme="BSc (Hons) Computer Science",
            year=1,
            availability=[],
            demoAccount=True,
            passportStyle={
                "cover": "plum",
                "displayName": "QA Tester",
                "photoUrl": None,
                "motto": "",
                "focusLabIds": ["T-CM7", "T-PY4"],
                "customLabs": [],
                "setupDone": False,
            },
        )
        gws.ensure_workspace(qa)
        store.put("users", qa["uid"], qa, save=False)
        dirty = True

    if dirty and save:
        store.save()


if __name__ == "__main__":
    if "--reset" not in sys.argv:
        print("usage: python -m store.seed --reset   (wipes backend/var/store.json and re-seeds demo data)")
        sys.exit(1)
    s = LocalStore(config.STORE_PATH)
    seed_store(s, Catalog())
    print(f"re-seeded {config.STORE_PATH}")
