"""Synthetic demo data for Punca.

Creates the demo student login account, a synthetic cohort of 46 peer students with diagnosis history
and weekly availability, and two existing peer study circles with a circle chat.
The named demo accounts (DEMO_ACCOUNTS) are built by ensure_demo_users() through the service.
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
from scheduling.circles import ALL_SLOTS, propose_circle, slot_label
from store.local_store import LocalStore

# Demo-only login accounts for the local prototype.
DEMO_PASSWORD = "punca-demo-2026"
DEMO_STUDENT_EMAIL = "student@punca.demo"
DEMO_STUDENT_UID = "u-demo-student"

# Bump this to rebuild the demo accounts' data in an existing store on the next start.
DEMO_DATA_VERSION = 3

# Demo accounts opt in to everything, so they always appear as suggested study partners.
OPEN_CONSENT = {"joinCircles": True, "shareNameWithCircle": True, "shareContact": True, "sharePassport": True}

# One-click sign-in list shown on the sign-in page (kept in step with frontend/src/demo.js).
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
        "hint": "Clean slate for live walkthroughs",
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
        "hint": "5 completed stamps, 1 re-entry, Chain Rule gap and circle",
    },
    {
        "uid": "u-demo-hafiz",
        "name": "Hafiz Tan",
        "email": "hafiz.student@demo.punca.edu",
        "studentId": "TP072819",
        "programme": "BSc (Hons) Software Engineering",
        "year": 2,
        "cover": "forest",
        "label": "Hafiz · Two Circles",
        "hint": "Chain Rule and Recursion gaps, in two study circles",
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
        "hint": "12 completed stamps, 2 re-entry, SQL Joins gap",
    },
    {
        "uid": "u-demo-iman",
        "name": "Nur Iman Zulkifli",
        "email": "iman.student@demo.punca.edu",
        "studentId": "TP073355",
        "programme": "BSc (Hons) Information Technology",
        "year": 1,
        "cover": "plum",
        "label": "Iman · First Year",
        "hint": "Recursion and SQL Joins gaps, in two study circles",
    },
    {
        "uid": "u-demo-marcus",
        "name": "Marcus Wong",
        "email": "marcus.student@demo.punca.edu",
        "studentId": "TP070642",
        "programme": "BSc (Hons) Computer Science (Cyber Security)",
        "year": 2,
        "cover": "navy",
        "label": "Marcus · Circle Organiser",
        "hint": "Chain Rule and SQL Joins gaps, 1 re-entry stamp",
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
            "shareContact": False,
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
        consent=dict(OPEN_CONSENT),
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
    store.save()


# ============================================================================ demo accounts ==
# Each persona is described here and then built through the real service: stamps are written,
# diagnoses are answered question by question by the engine, and tasks, notes and circles are
# created with the same calls the app uses. That keeps every screen working for demo accounts.
PERSONAS = [
    {
        "uid": "u-demo-aisyah",
        "motto": "Find the root cause, not just the answer",
        "focusLabIds": ["T-CM7", "T-PY4", "T-DB4"],
        "customLabs": ["CM Lab 7 · Gradient Descent"],
        "availability": ["Mon-10", "Tue-14", "Tue-15", "Thu-11", "Thu-12"],
        "stamps": ["FM-ARITH", "FM-ALG", "FM-FUNC", "CM-LIM", "CM-DER"],
        "reentry": ["CM-DERRULES"],
        "inProgress": ["CM-PARTIAL"],
        "diagnoses": [
            {
                "target": "CM-GRADDESC",
                "gaps": ["CM-CHAIN"],
                "hoursAgo": 3,
                "text": "Minimising f(x, y) = (x - 3)^2 + (2y + 1)^2 with gradient descent and partial derivatives",
            },
        ],
    },
    {
        "uid": "u-demo-hafiz",
        "motto": "Step by step from foundations to code",
        "focusLabIds": ["T-CM7", "T-PY4", "T-JV3"],
        "customLabs": [],
        "availability": ["Tue-14", "Tue-15", "Wed-16", "Thu-11"],
        "stamps": ["FM-ARITH", "FM-ALG", "PRG-VAR", "PRG-COND", "PRG-LOOP", "PY-FUNC"],
        "reentry": [],
        "inProgress": ["PY-PARAM"],
        "diagnoses": [
            {
                "target": "PY-RECUR",
                "gaps": ["PY-RECUR"],
                "hoursAgo": 30,
                "text": "My recursive factorial and nested-list sum functions keep hitting RecursionError",
            },
            {
                "target": "CM-GRADDESC",
                "gaps": ["CM-CHAIN"],
                "hoursAgo": 5,
                "text": "Stuck on composite derivatives when computing gradients in Lab 7",
            },
        ],
    },
    {
        "uid": "u-demo-priya",
        "motto": "Solid foundations across every module",
        "focusLabIds": ["T-CM6", "T-PY4", "T-JV4", "T-DB4"],
        "customLabs": ["Data Science Capstone Prep"],
        "availability": ["Mon-11", "Tue-14", "Wed-14", "Thu-11", "Fri-10"],
        "stamps": [
            "FM-ARITH", "FM-ALG", "FM-FUNC", "FM-EXP", "PRG-VAR", "PRG-COND", "PRG-LOOP",
            "CM-LIM", "CM-DER", "CM-VEC", "PY-FUNC", "DB-MODEL",
        ],
        "reentry": ["PY-SCOPE", "DB-3NF"],
        "inProgress": ["JV-IFACE"],
        "diagnoses": [
            {
                "target": "DB-JOIN",
                "gaps": ["DB-JOIN"],
                "hoursAgo": 50,
                "text": "My SQL query drops students with 0 enrolments when I use INNER JOIN with COUNT and GROUP BY",
            },
        ],
    },
    {
        "uid": "u-demo-iman",
        "motto": "One concept at a time",
        "focusLabIds": ["T-PY4", "T-DB4", "T-JV4"],
        "customLabs": ["Python Lab 4 · Recursion"],
        "availability": ["Mon-10", "Wed-14", "Wed-16", "Thu-12", "Fri-10"],
        "stamps": ["FM-ARITH", "PRG-VAR", "PRG-COND", "PRG-LOOP", "PY-FUNC", "DB-MODEL", "DB-SELECT"],
        "reentry": [],
        "inProgress": ["PY-SCOPE"],
        "diagnoses": [
            {
                "target": "DB-JOIN",
                "gaps": ["DB-JOIN"],
                "hoursAgo": 26,
                "text": "I cannot tell when to use LEFT JOIN instead of INNER JOIN across students and enrolments",
            },
            {
                "target": "PY-RECUR",
                "gaps": ["PY-RECUR"],
                "hoursAgo": 8,
                "text": "My recursive function for summing a nested list never reaches its base case",
            },
        ],
    },
    {
        "uid": "u-demo-marcus",
        "motto": "Understand it well enough to explain it",
        "focusLabIds": ["T-CM7", "T-DB4", "T-JV4"],
        "customLabs": [],
        "availability": ["Tue-14", "Wed-14", "Thu-11", "Thu-12"],
        "stamps": ["FM-ARITH", "FM-ALG", "FM-FUNC", "CM-LIM", "DB-MODEL", "DB-SELECT", "JV-CLASS"],
        "reentry": ["JV-INHER"],
        "inProgress": [],
        "diagnoses": [
            {
                "target": "DB-JOIN",
                "gaps": ["DB-JOIN"],
                "hoursAgo": 28,
                "text": "Joining three tables gives me duplicate rows and I do not know which join condition is wrong",
            },
            {
                "target": "CM-GRADDESC",
                "gaps": ["CM-CHAIN"],
                "hoursAgo": 6,
                "text": "My gradient descent steps diverge and I think my derivatives of composite terms are wrong",
            },
        ],
    },
]

DEMO_CIRCLES = [
    {
        "id": "c-demo-chain",
        "conceptId": "CM-CHAIN",
        "members": ["u-demo-aisyah", "u-demo-hafiz", "u-demo-marcus"],
        "slot": "Tue-14",
        "chat": [
            ("u-demo-aisyah", "I keep dropping the inner derivative on (2y + 1)^2. Can we go through Lab 7 question 2 together?"),
            ("u-demo-hafiz", "Same here. I will bring my working for the composite terms."),
            ("u-demo-marcus", "Tuesday 2pm works for me. I will start the Meet room and paste the link here."),
        ],
    },
    {
        "id": "c-demo-joins",
        "conceptId": "DB-JOIN",
        "members": ["u-demo-priya", "u-demo-iman", "u-demo-marcus"],
        "slot": "Wed-14",
        "chat": [
            ("u-demo-iman", "Can someone explain why INNER JOIN removes students with no enrolments?"),
            ("u-demo-priya", "I think it only keeps matching rows. Let us draw both tables on Wednesday and compare with LEFT JOIN."),
            ("u-demo-marcus", "I have a three-table example that gives duplicates. I will share it in the session."),
        ],
    },
    {
        "id": "c-demo-recursion",
        "conceptId": "PY-RECUR",
        "members": ["u-demo-hafiz", "u-demo-iman"],
        "slot": "Wed-16",
        "chat": [
            ("u-demo-hafiz", "My factorial never stops. I think my base case is wrong."),
            ("u-demo-iman", "Mine too, for the nested list sum. Wednesday 4pm? We can trace the call stack on paper."),
        ],
    },
]

TAKEAWAYS = {
    "CM-CHAIN": [
        "Differentiate the outer function first, then multiply by the derivative of the inner function.",
        "In d/dy (2y + 1)^2 = 2(2y + 1) * 2, forgetting the inner * 2 scales the gradient wrongly.",
    ],
    "PY-RECUR": [
        "Every recursive function needs a base case that returns without calling itself.",
        "Each call must move closer to the base case, or the call stack grows until RecursionError.",
    ],
    "DB-JOIN": [
        "INNER JOIN keeps only rows that match in both tables.",
        "LEFT JOIN keeps every row of the left table and fills the right side with NULL when nothing matches.",
    ],
}


def _put_stamp(store: LocalStore, uid: str, cid: str, p_known: float, when: datetime) -> None:
    store.put(
        "mastery",
        f"{uid}_{cid}",
        {"uid": uid, "conceptId": cid, "pKnown": round(p_known, 4), "evidenceCount": 3, "lastUpdated": _iso(when)},
        save=False,
    )
    store.put(
        "stamps",
        f"{uid}_{cid}",
        {
            "uid": uid,
            "conceptId": cid,
            "tier": "completed",
            "earnedAt": _iso(when),
            "basedOnDiagnosisId": None,
            "shareable": True,
        },
        save=False,
    )


def _wipe_user_data(store: LocalStore, uid: str) -> None:
    """Remove one demo account's learning records so it can be rebuilt."""
    for col in ("mastery", "stamps"):
        for d in store.list(col, lambda d: d.get("uid") == uid):
            store.delete(col, f"{uid}_{d['conceptId']}", save=False)
    for d in store.list("diagnoses", lambda d: d.get("uid") == uid):
        store.delete("diagnoses", d["id"], save=False)
    for c in store.list("studyCircles", lambda c: uid in c.get("memberUids", [])):
        c["memberUids"] = [u for u in c["memberUids"] if u != uid]
        if c["memberUids"]:
            store.put("studyCircles", c["id"], c, save=False)
        else:
            store.delete("studyCircles", c["id"], save=False)


def _simulate_diagnosis(svc, user: dict, text: str, target: str, gaps: list[str], when: datetime) -> dict | None:
    """Run one diagnosis through the engine, answering as a student who is missing `gaps`."""
    cat = svc.cat
    d = svc.start_diagnosis(user, text, target, None)
    for _ in range(config.MAX_PROBES + 2):
        if d["status"] != "in_progress" or not d.get("pending"):
            break
        probe = d["pending"]
        cid = probe["conceptId"]
        knows = not any(g == cid or g in cat.graph.ancestors(cid) for g in gaps)
        full = cat.probes[probe["probeId"]]
        choice = full["correctIndex"] if knows else (full["correctIndex"] + 1) % len(full["options"])
        d = svc.answer(user["uid"], d["id"], probe["probeId"], choice, confidence="high" if knows else "medium")["diagnosis"]
    doc = svc.store.get("diagnoses", d["id"])
    if not doc:
        return None
    doc["createdAt"] = _iso(when)
    if doc.get("completedAt"):
        doc["completedAt"] = _iso(when + timedelta(minutes=6))
    doc["demo"] = True
    svc.store.put("diagnoses", doc["id"], doc, save=False)
    return doc


def _build_persona(svc, spec: dict, account: dict, pw_hash: str, now: datetime) -> None:
    store, cat = svc.store, svc.cat
    uid = spec["uid"]
    _wipe_user_data(store, uid)
    user = _user(
        uid,
        account["name"],
        email=account["email"],
        university="Asia Pacific University (APU)",
        studentId=account["studentId"],
        passwordHash=pw_hash,
        programme=account["programme"],
        year=account["year"],
        availability=sorted(spec["availability"], key=ALL_SLOTS.index),
        consent=dict(OPEN_CONSENT),
        demoAccount=True,
        demoDataVersion=DEMO_DATA_VERSION,
        passportStyle={
            "cover": account["cover"],
            "displayName": account["name"],
            "photoUrl": None,
            "motto": spec["motto"],
            "focusLabIds": spec["focusLabIds"],
            "customLabs": spec["customLabs"],
            "setupDone": True,
        },
    )
    gws.ensure_workspace(user)
    store.put("users", uid, user, save=False)

    stamps = [c for c in spec["stamps"] if c in cat.concepts]
    for idx, cid in enumerate(stamps):
        _put_stamp(store, uid, cid, 0.86, now - timedelta(days=len(stamps) + 6 - idx))

    for spec_d in spec["diagnoses"]:
        if spec_d["target"] not in cat.concepts:
            continue
        doc = _simulate_diagnosis(
            svc, user, spec_d["text"], spec_d["target"], spec_d["gaps"], now - timedelta(hours=spec_d["hoursAgo"])
        )
        if not doc:
            continue
        root = doc.get("rootCauseConceptId")
        if root not in spec_d["gaps"]:
            print(f"demo seed: {uid} diagnosis on {spec_d['target']} found {root}, expected one of {spec_d['gaps']}")
        if root:
            svc.google_tasks_from_diagnosis(user, doc["id"])
            route = " → ".join(cat.name(c) for c in (doc.get("path") or []))
            points = "\n".join(f"- {t}" for t in TAKEAWAYS.get(root, []))
            svc.google_docs_create(
                user,
                {
                    "title": f"Punca Notes · {cat.name(root)} → {cat.name(spec_d['target'])}",
                    "conceptId": root,
                    "content": (
                        f"# Study Notes: {cat.name(root)} (for {cat.name(spec_d['target'])})\n\n"
                        f"**Where I got stuck:** {spec_d['text']}\n\n"
                        f"**Route:** {route}\n\n"
                        f"## Key takeaways\n{points}\n"
                    ),
                },
            )

    # A stamp that later slipped below solid: shown as "Re-entry required" until a re-check renews it.
    for cid in spec["reentry"]:
        if cid in cat.concepts:
            _put_stamp(store, uid, cid, 0.86, now - timedelta(days=14))
            store.put(
                "mastery",
                f"{uid}_{cid}",
                {"uid": uid, "conceptId": cid, "pKnown": 0.48, "evidenceCount": 4, "lastUpdated": _iso(now - timedelta(days=2))},
                save=False,
            )
    # One passed re-check so far: "In progress".
    for cid in spec["inProgress"]:
        if cid in cat.concepts:
            store.put(
                "mastery",
                f"{uid}_{cid}",
                {"uid": uid, "conceptId": cid, "pKnown": 0.55, "evidenceCount": 2, "lastUpdated": _iso(now - timedelta(days=1))},
                save=False,
            )


def _build_demo_circles(svc, now: datetime) -> None:
    store, cat = svc.store, svc.cat
    for c in store.list("studyCircles", lambda c: c["id"].startswith("c-demo-")):
        store.delete("studyCircles", c["id"], save=False)
    for spec in DEMO_CIRCLES:
        members = [u for u in spec["members"] if store.get("users", u)]
        if spec["conceptId"] not in cat.concepts or len(members) < 2:
            continue
        names = {u: (store.get("users", u) or {}).get("name") or "Student" for u in members}
        messages = [
            {
                "id": f"msg-{spec['id']}-0",
                "sender": "Study Circle",
                "text": (
                    f"Peer circle for {cat.name(spec['conceptId'])}. Suggested time: {slot_label(spec['slot'])}, "
                    "a free hour every member shares. Start a Google Meet room and paste the link above, or discuss here."
                ),
                "createdAt": _iso(now - timedelta(hours=20)),
            }
        ]
        for i, (uid, text) in enumerate(spec["chat"], start=1):
            if uid in names:
                messages.append({
                    "id": f"msg-{spec['id']}-{i}",
                    "sender": names[uid],
                    "text": text,
                    "createdAt": _iso(now - timedelta(hours=20 - 2 * i)),
                })
        circle = {
            "id": spec["id"],
            "courseId": cat.course["id"],
            "conceptId": spec["conceptId"],
            "memberUids": members,
            "status": "scheduled",
            "proposedSlot": spec["slot"],
            "mode": "peer",
            "meetUrl": None,
            "meetLive": False,
            "messages": messages,
            "createdAt": _iso(now - timedelta(hours=20)),
            "demo": True,
        }
        store.put("studyCircles", circle["id"], circle, save=False)
        svc._sync_circle_to_all_members(circle)
        # The first member has already put the session in their calendar.
        svc.circle_schedule_calendar(store.get("users", members[0]), circle["id"])


def ensure_demo_users(svc) -> None:
    """Make sure every demo account exists with current data, without touching real accounts.

    Runs on every start. Real accounts and the fresh "Demo Student" keep whatever they have; the
    named personas are rebuilt only when DEMO_DATA_VERSION changes or one of them is missing.
    """
    store, cat = svc.store, svc.cat
    now = datetime.now(timezone.utc)
    accounts = {a["uid"]: a for a in DEMO_ACCOUNTS}

    with store.batch():
        # Clear made-up Meet codes saved by earlier builds, and bring saved workspaces up to date.
        for c in store.list("studyCircles"):
            if c.get("meetUrl") and not c.get("meetLive"):
                c["meetUrl"], c["meetLive"] = None, False
                store.put("studyCircles", c["id"], c, save=False)
        for u in store.list("users", lambda u: not u.get("synthetic")):
            before = (u.get("googleWorkspace") or {}).get("starterVersion")
            gws.ensure_workspace(u)
            if (u.get("googleWorkspace") or {}).get("starterVersion") != before:
                store.put("users", u["uid"], u, save=False)

        current = all(
            (store.get("users", p["uid"]) or {}).get("demoDataVersion") == DEMO_DATA_VERSION for p in PERSONAS
        )
        qa = store.get("users", "u-demo-qa")
        demo = store.get("users", DEMO_STUDENT_UID)
        if current and qa and (qa.get("demoDataVersion") == DEMO_DATA_VERSION) and (
            not demo or demo.get("demoDataVersion") == DEMO_DATA_VERSION
        ):
            return

        pw_hash = auth.hash_password(DEMO_PASSWORD)

        # Fresh "Demo Student": keep its history, just make sure it can be suggested to peers.
        if demo and demo.get("demoDataVersion") != DEMO_DATA_VERSION:
            demo["consent"] = dict(demo.get("consent") or {}, **OPEN_CONSENT)
            demo["demoAccount"] = True
            demo["demoDataVersion"] = DEMO_DATA_VERSION
            store.put("users", demo["uid"], demo, save=False)

        # QA Tester: a brand-new account that still has to set up its passport.
        if not qa or qa.get("demoDataVersion") != DEMO_DATA_VERSION:
            account = accounts["u-demo-qa"]
            qa = _user(
                "u-demo-qa",
                account["name"],
                email=account["email"],
                university="Asia Pacific University (APU)",
                studentId=account["studentId"],
                passwordHash=(qa or {}).get("passwordHash") or pw_hash,
                programme=account["programme"],
                year=account["year"],
                availability=(qa or {}).get("availability") or [],
                consent=dict(OPEN_CONSENT),
                demoAccount=True,
                demoDataVersion=DEMO_DATA_VERSION,
                passportStyle=(qa or {}).get("passportStyle")
                or {
                    "cover": account["cover"],
                    "displayName": account["name"],
                    "photoUrl": None,
                    "motto": "",
                    "focusLabIds": ["T-CM7", "T-PY4"],
                    "customLabs": [],
                    "setupDone": False,
                },
            )
            gws.ensure_workspace(qa)
            store.put("users", qa["uid"], qa, save=False)

        if not current:
            for spec in PERSONAS:
                _build_persona(svc, spec, accounts[spec["uid"]], pw_hash, now)
            _build_demo_circles(svc, now)


if __name__ == "__main__":
    if "--reset" not in sys.argv:
        print("usage: python -m store.seed --reset   (wipes backend/var/store.json and re-seeds demo data)")
        sys.exit(1)
    from api.service import PuncaService
    from llm.client import LLMClient
    from llm.service import LLMService

    s = LocalStore(config.STORE_PATH)
    catalog = Catalog()
    seed_store(s, catalog)
    ensure_demo_users(PuncaService(catalog, s, LLMService(catalog, LLMClient(offline=True))))
    print(f"re-seeded {config.STORE_PATH}")
