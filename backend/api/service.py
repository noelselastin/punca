"""Application logic behind the HTTP API. Routes in api/main.py stay thin and call PuncaService."""
from __future__ import annotations

import logging
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import auth
import config
from content import Catalog
from diagnosis import bkt
from diagnosis.engine import DiagnosisEngine, DiagnosisError, Params
from llm.service import LLMService
from scheduling import circles as sched
from store.local_store import LocalStore

log = logging.getLogger("punca.api")


PASSPORT_COVERS = ["navy", "maroon", "forest", "teal", "plum"]
PASSPORT_EMBLEMS = ["spring", "compass", "atom", "leaf", "star"]


class ServiceError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat(timespec="seconds")


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


class StoreMastery:
    """Mastery for one user, stored as mastery/{uid}_{conceptId} (README section 7)."""

    def __init__(self, store: LocalStore, uid: str):
        self.store, self.uid = store, uid

    def get(self, cid: str) -> tuple[float, int]:
        d = self.store.get("mastery", f"{self.uid}_{cid}")
        return (d["pKnown"], d["evidenceCount"]) if d else (config.P_INIT, 0)

    def set(self, cid: str, p: float, ev: int, **extra) -> None:
        self.store.put("mastery", f"{self.uid}_{cid}", {"uid": self.uid, "conceptId": cid, "pKnown": round(p, 4),
                                                        "evidenceCount": ev, "lastUpdated": _iso(), **extra})


class PuncaService:
    def __init__(self, catalog: Catalog, store: LocalStore, llm: LLMService, params: Params | None = None):
        self.cat = catalog
        self.store = store
        self.llm = llm
        self.params = params or Params()
        self.engine = DiagnosisEngine(catalog.graph, catalog.probes, catalog.probes_by_concept, self.params)

    # ================================================================== accounts ============
    @staticmethod
    def public_user(u: dict) -> dict:
        return {k: u.get(k) for k in ("uid", "role", "name", "email", "programme", "year", "department",
                                      "availability", "consent", "createdAt", "passportStyle")} | {
            "demoAccount": u.get("demoAccount", False)}

    def _user_by_email(self, email: str) -> dict | None:
        email = email.strip().lower()
        hits = self.store.list("users", lambda u: (u.get("email") or "").lower() == email)
        return hits[0] if hits else None

    def _issue_token(self, uid: str) -> str:
        token = auth.new_token()
        self.store.put("authTokens", auth.token_key(token), {
            "uid": uid, "createdAt": _iso(), "expiresAt": _iso(_now() + timedelta(days=auth.TOKEN_TTL_DAYS))})
        return token

    def signup(self, data: dict) -> dict:
        """Student sign-up. Lecturer accounts are not created through the app (the demo has one staff login)."""
        role = "student"
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        if not 2 <= len(name) <= 60:
            raise ServiceError(400, "Enter your name (2 to 60 characters).")
        if not auth.valid_email(email):
            raise ServiceError(400, "Enter a valid email address.")
        if len(password) < 8 or len(password) > 128:
            raise ServiceError(400, "Use a password of at least 8 characters.")
        if self._user_by_email(email):
            raise ServiceError(409, "An account with that email already exists. Sign in instead.")
        extra: dict = {"programme": (data.get("programme") or "").strip()[:80] or None}
        year = data.get("year")
        if year not in (None, ""):
            try:
                year = int(year)
            except (TypeError, ValueError):
                raise ServiceError(400, "Year of study must be a number from 1 to 5.")
            if not 1 <= year <= 5:
                raise ServiceError(400, "Year of study must be a number from 1 to 5.")
            extra["year"] = year
        uid = "u-" + uuid.uuid4().hex[:12]
        user = {"uid": uid, "role": role, "name": name, "email": email,
                "passwordHash": auth.hash_password(password), "programme": None, "year": None,
                "department": None, "courseIds": [self.cat.course["id"]], "availability": [],
                "consent": {"joinCircles": False, "shareNameWithCircle": False, "shareNameWithLecturer": False,
                            "sharePassport": False},
                "synthetic": False, "createdAt": _iso()}
        user.update(extra)
        self.store.put("users", uid, user)
        log.info("account created uid=%s role=%s", uid, role)
        return {"token": self._issue_token(uid), "user": self.public_user(user)}

    def login(self, email: str, password: str) -> dict:
        user = self._user_by_email(email or "")
        if not user or not auth.verify_password(password or "", user.get("passwordHash")):
            raise ServiceError(401, "Email or password is not correct.")
        return {"token": self._issue_token(user["uid"]), "user": self.public_user(user)}

    def logout(self, token: str) -> None:
        self.store.delete("authTokens", auth.token_key(token))

    def user_for_token(self, token: str) -> dict:
        rec = self.store.get("authTokens", auth.token_key(token)) if token else None
        if not rec or _parse(rec["expiresAt"]) < _now():
            raise ServiceError(401, "Please sign in again.")
        user = self.store.get("users", rec["uid"])
        if not user:
            raise ServiceError(401, "Please sign in again.")
        return user

    def update_profile(self, user: dict, data: dict) -> dict:
        if "passport" in data:
            user["passportStyle"] = self._passport_style(user, data["passport"] or {})
        if "programme" in data:
            user["programme"] = (data["programme"] or "").strip()[:80] or None
        if "year" in data:
            year = data["year"]
            if year in (None, ""):
                user["year"] = None
            else:
                try:
                    year = int(year)
                except (TypeError, ValueError):
                    raise ServiceError(400, "Year of study must be a number from 1 to 5.")
                if not 1 <= year <= 5:
                    raise ServiceError(400, "Year of study must be a number from 1 to 5.")
                user["year"] = year
        if "availability" in data:
            slots = data["availability"] or []
            if not isinstance(slots, list) or not all(isinstance(s, str) and sched.valid_slot(s) for s in slots):
                raise ServiceError(400, "Availability must be a list of slots such as 'Tue-14'.")
            user["availability"] = sorted(set(slots), key=sched.ALL_SLOTS.index)
        if "consent" in data:
            for k in ("joinCircles", "shareNameWithCircle", "shareNameWithLecturer", "sharePassport"):
                if k in (data["consent"] or {}):
                    user["consent"][k] = bool(data["consent"][k])
            if "sharePassport" in (data["consent"] or {}):
                for s in self.store.list("stamps", lambda s: s["uid"] == user["uid"]):
                    s["shareable"] = user["consent"]["sharePassport"]
                    self.store.put("stamps", f"{s['uid']}_{s['conceptId']}", s, save=False)
        self.store.put("users", user["uid"], user)
        return self.public_user(user)

    def _passport_style(self, user: dict, p: dict) -> dict:
        """Validate passport customisation: cover colour, emblem, name on the passport, motto, labs in focus."""
        cur = dict(user.get("passportStyle") or {})
        if "cover" in p:
            if p["cover"] not in PASSPORT_COVERS:
                raise ServiceError(400, "Pick one of the passport cover colours.")
            cur["cover"] = p["cover"]
        if "emblem" in p:
            if p["emblem"] not in PASSPORT_EMBLEMS:
                raise ServiceError(400, "Pick one of the passport emblems.")
            cur["emblem"] = p["emblem"]
        if "displayName" in p:
            name = (p["displayName"] or "").strip()
            if not 2 <= len(name) <= 40:
                raise ServiceError(400, "The name on your passport must be 2 to 40 characters.")
            cur["displayName"] = name
        if "motto" in p:
            cur["motto"] = (p["motto"] or "").strip()[:80] or None
        if "focusLabIds" in p:
            labs = {lab["id"] for lab in self.cat.labs}
            cur["focusLabIds"] = [x for x in (p["focusLabIds"] or []) if x in labs]
        cur.setdefault("cover", PASSPORT_COVERS[0])
        cur.setdefault("emblem", PASSPORT_EMBLEMS[0])
        cur.setdefault("displayName", user["name"])
        cur.setdefault("motto", None)
        cur.setdefault("focusLabIds", [])
        cur["setupDone"] = True
        return cur

    # ================================================================== mastery =============
    def mastery_map(self, uid: str) -> dict:
        out = {}
        for d in self.store.list("mastery", lambda m: m["uid"] == uid):
            out[d["conceptId"]] = {"pKnown": d["pKnown"], "evidenceCount": d["evidenceCount"],
                                   "status": bkt.status(d["pKnown"], d["evidenceCount"]),
                                   "selfReported": d.get("selfReported", False)}
        return out

    def mark_known(self, uid: str, cid: str) -> dict:
        if cid not in self.cat.concepts:
            raise ServiceError(404, "Unknown concept.")
        book = StoreMastery(self.store, uid)
        p, ev = book.get(cid)
        book.set(cid, max(p, config.SOLID + 0.05), ev + 1, selfReported=True)
        log.info("uid=%s corrected %s to known", uid, cid)
        return self.mastery_map(uid)

    # ================================================================== diagnosis ===========
    def map_stuck(self, text: str) -> dict:
        text = (text or "").strip()
        if not 3 <= len(text) <= 2000:
            raise ServiceError(400, "Describe what you are stuck on in 3 to 2000 characters.")
        m = self.llm.map_stuck_point(text)
        m["targetName"] = self.cat.name(m.get("targetConceptId"))
        return m

    def _used_probes(self, uid: str) -> list[str]:
        used: list[str] = []
        for d in sorted(self.store.list("diagnoses", lambda x: x["uid"] == uid and "state" in x),
                        key=lambda x: x["createdAt"]):
            used += d["state"]["usedProbeIds"]
        return used

    def start_diagnosis(self, user: dict, text: str, target: str, mapping: dict | None) -> dict:
        if user["role"] != "student":
            raise ServiceError(403, "Only student accounts can run a diagnosis.")
        text = (text or "").strip()
        if not 3 <= len(text) <= 2000:
            raise ServiceError(400, "Describe what you are stuck on in 3 to 2000 characters.")
        if target not in self.cat.concepts:
            raise ServiceError(400, "Pick a concept from the list.")
        state = self.engine.new_state(target, self._used_probes(user["uid"])[-40:])
        self.engine.start(state, StoreMastery(self.store, user["uid"]))
        did = "d-" + uuid.uuid4().hex[:12]
        doc = {"id": did, "uid": user["uid"], "courseId": self.cat.course["id"], "stuckInput": text,
               "targetConceptId": target, "mapping": mapping or {}, "state": state, "status": state["status"],
               "rootCauseConceptId": None, "path": [], "createdAt": _iso()}
        self._finish_if_done(doc)
        self.store.put("diagnoses", did, doc)
        return self.diagnosis_view(doc)

    def _finish_if_done(self, doc: dict) -> None:
        st = doc["state"]
        doc["status"] = st["status"]
        if st["status"] == "done" and st["result"] and doc.get("rootCauseConceptId") is None:
            res = st["result"]
            doc["rootCauseConceptId"] = res["rootCauseConceptId"]
            doc["path"] = res["remediationPath"]
            doc["confidence"] = res["confidence"]
            doc["completedAt"] = _iso()
            if res["rootCauseConceptId"]:
                self.store.put("diagnosisEvents", "ev-" + uuid.uuid4().hex[:10], {
                    "courseId": doc["courseId"], "labId": self.cat.lab_for(doc["targetConceptId"]),
                    "targetConceptId": doc["targetConceptId"], "rootCauseConceptId": res["rootCauseConceptId"],
                    "timestamp": _iso()})

    def _own_diagnosis(self, uid: str, did: str) -> dict:
        doc = self.store.get("diagnoses", did)
        if not doc or doc["uid"] != uid or "state" not in doc:
            raise ServiceError(404, "Diagnosis not found.")
        return doc

    def answer(self, uid: str, did: str, probe_id: str, choice: int) -> dict:
        doc = self._own_diagnosis(uid, did)
        try:
            fb = self.engine.answer(doc["state"], probe_id, choice, StoreMastery(self.store, uid))
        except DiagnosisError as exc:
            raise ServiceError(409, str(exc))
        fb["conceptName"] = self.cat.name(fb["conceptId"])
        fb["misconceptionLabel"] = _label(fb["misconception"])
        self._finish_if_done(doc)
        self.store.put("diagnoses", did, doc)
        return {"feedback": fb, "diagnosis": self.diagnosis_view(doc)}

    def get_diagnosis(self, uid: str, did: str) -> dict:
        return self.diagnosis_view(self._own_diagnosis(uid, did))

    def list_diagnoses(self, uid: str) -> list[dict]:
        docs = sorted(self.store.list("diagnoses", lambda d: d["uid"] == uid and "state" in d),
                      key=lambda d: d["createdAt"], reverse=True)
        return [{"id": d["id"], "stuckInput": d["stuckInput"], "status": d["status"], "createdAt": d["createdAt"],
                 "targetConceptId": d["targetConceptId"], "targetName": self.cat.name(d["targetConceptId"]),
                 "rootCauseConceptId": d.get("rootCauseConceptId"),
                 "rootCauseName": self.cat.name(d.get("rootCauseConceptId"))} for d in docs]

    def diagnosis_view(self, doc: dict) -> dict:
        st = doc["state"]
        pending = None
        if st.get("pending"):
            pending = self.cat.public_probe(self.cat.probes[st["pending"]["probeId"]])
        asked = []
        for a in st["asked"]:
            p = self.cat.probes[a["probeId"]]
            asked.append({"probeId": a["probeId"], "conceptId": a["conceptId"], "conceptName": self.cat.name(a["conceptId"]),
                          "question": p["question"], "yourAnswer": p["options"][a["choiceIndex"]],
                          "correctAnswer": p["options"][p["correctIndex"]], "correct": a["correct"],
                          "misconception": a["misconception"], "misconceptionLabel": _label(a["misconception"])})
        result = None
        if st.get("result"):
            r = st["result"]
            named = lambda ids: [{"id": c, "name": self.cat.name(c)} for c in ids]  # noqa: E731
            result = dict(r, targetName=self.cat.name(r["targetConceptId"]),
                          rootCauseName=self.cat.name(r["rootCauseConceptId"]),
                          path=named(r["remediationPath"]), otherGapsNamed=named(r["otherGaps"]),
                          untestedNamed=named(r["untestedPrerequisites"]), skippedSolidNamed=named(r["skippedSolid"]))
        return {"id": doc["id"], "stuckInput": doc["stuckInput"], "status": st["status"],
                "targetConceptId": doc["targetConceptId"], "targetName": self.cat.name(doc["targetConceptId"]),
                "mapping": doc.get("mapping") or {}, "probesAsked": len(st["asked"]), "maxProbes": st["maxProbes"],
                "pending": pending, "asked": asked, "result": result, "createdAt": doc["createdAt"]}

    # ================================================================== remediation =========
    def remediation(self, uid: str, did: str) -> dict:
        doc = self._own_diagnosis(uid, did)
        if doc["status"] != "done" or not doc.get("rootCauseConceptId"):
            raise ServiceError(409, "Remediation is available once a gap has been found.")
        if not doc.get("remediation"):
            st = doc["state"]
            mis = sorted({a["misconception"] for a in st["asked"] if a["misconception"]})
            rem = self.llm.remediate(doc["targetConceptId"], doc["rootCauseConceptId"], doc["path"], mis)
            doc["remediation"] = rem
            self.store.put("diagnoses", did, doc)
        rem = dict(doc["remediation"])
        rem["practice"] = self.practice(doc["rootCauseConceptId"], doc["path"], doc["state"]["usedProbeIds"])
        rem["rootCauseName"] = self.cat.name(doc["rootCauseConceptId"])
        return rem

    def practice(self, root: str, path: list[str], exclude: list[str], n: int = 3) -> list[dict]:
        out: list[dict] = []
        for cid in path:
            for p in self.cat.probes_by_concept.get(cid, []):
                if p["id"] not in exclude and len(out) < n:
                    out.append(dict(self.cat.public_probe(p), correctIndex=p["correctIndex"],
                                    explanation=p.get("explanation", "")))
            if len(out) >= n:
                break
        return out

    # ================================================================== re-check ============
    def recheck_start(self, user: dict, cid: str) -> dict:
        if cid not in self.cat.concepts:
            raise ServiceError(404, "Unknown concept.")
        last = user.get("lastRecheck", {}).get(cid)
        bank = self.cat.probes_by_concept.get(cid, [])
        if not bank:
            raise ServiceError(409, "No re-check questions for this concept yet.")
        ids = [p["id"] for p in bank]
        start = ids.index(last) + 1 if last in ids else 0
        order = [bank[(start + i) % len(bank)] for i in range(len(bank))]
        seen_in_diagnosis = set(self._used_probes(user["uid"]))
        fresh = [p for p in order if p["id"] not in seen_in_diagnosis and p["id"] != last]
        nxt = fresh[0] if fresh else next((p for p in order if p["id"] != last), bank[0])
        user["pendingRecheck"] = {"probeId": nxt["id"], "conceptId": cid}
        self.store.put("users", user["uid"], user)
        return self.cat.public_probe(nxt)

    def recheck_answer(self, user: dict, probe_id: str, choice: int) -> dict:
        pend = user.get("pendingRecheck")
        if not pend or pend["probeId"] != probe_id:
            raise ServiceError(409, "Start a re-check first.")
        probe = self.cat.probes[probe_id]
        if not isinstance(choice, int) or not 0 <= choice < len(probe["options"]):
            raise ServiceError(400, "choiceIndex out of range")
        book = StoreMastery(self.store, user["uid"])
        cid = pend["conceptId"]
        p, ev = book.get(cid)
        correct = choice == probe["correctIndex"]
        p2 = bkt.update(p, correct, self.params.p_guess, self.params.p_slip, self.params.p_learn)
        book.set(cid, p2, ev + 1)
        user.pop("pendingRecheck", None)
        user.setdefault("lastRecheck", {})[cid] = probe_id
        self.store.put("users", user["uid"], user)
        stamp, earned = self.store.get("stamps", f"{user['uid']}_{cid}"), False
        # Passport rule: a stamp is earned only on a passed re-check, never by the first diagnosis.
        if p2 >= config.SOLID and not stamp:
            stamp = {"uid": user["uid"], "conceptId": cid, "tier": "verified", "earnedAt": _iso(),
                     "basedOnDiagnosisId": self._diagnosis_touching(user["uid"], cid), "endorsedByUid": None,
                     "endorsedAt": None, "shareable": bool(user["consent"].get("sharePassport"))}
            self.store.put("stamps", f"{user['uid']}_{cid}", stamp)
            earned = True
            log.info("uid=%s earned a verified stamp for %s", user["uid"], cid)
        return {"correct": correct, "correctIndex": probe["correctIndex"], "explanation": probe.get("explanation", ""),
                "conceptId": cid, "conceptName": self.cat.name(cid), "pKnown": round(p2, 4),
                "status": bkt.status(p2, ev + 1), "stampEarned": earned, "stamp": stamp}

    def _diagnosis_touching(self, uid: str, cid: str) -> str | None:
        docs = sorted(self.store.list("diagnoses", lambda d: d["uid"] == uid and (
            d.get("rootCauseConceptId") == cid or cid in (d.get("path") or []))), key=lambda d: d["createdAt"])
        return docs[-1]["id"] if docs else None

    # ================================================================== passport ============
    def passport(self, user: dict) -> dict:
        uid = user["uid"]
        mastery = self.mastery_map(uid)
        stamps = {s["conceptId"]: s for s in self.store.list("stamps", lambda s: s["uid"] == uid)}
        open_diag = None
        for d in sorted(self.store.list("diagnoses", lambda d: d["uid"] == uid and d.get("status") == "done"
                                        and d.get("rootCauseConceptId")), key=lambda d: d["createdAt"], reverse=True):
            if d["targetConceptId"] not in stamps:
                open_diag = d
                break
        entry_required = ({next((c for c in open_diag["path"] if c not in stamps), open_diag["targetConceptId"])}
                          if open_diag else set())
        regions: dict[str, list[dict]] = defaultdict(list)
        for cid, c in self.cat.concepts.items():
            m = mastery.get(cid)
            st = stamps.get(cid)
            if st:
                state = "endorsed" if st["tier"] == "endorsed" else "stamped"
            elif cid in entry_required or (m and m["status"] == "gap"):
                state = "entry-required"
            elif m and m["status"] in ("shaky", "solid"):
                state = m["status"]  # solid without a re-check is not stamped yet
            else:
                state = "untested"
            endorser = self.store.get("users", st["endorsedByUid"]) if st and st.get("endorsedByUid") else None
            regions[c["area"]].append({"conceptId": cid, "name": c["name"], "state": state,
                                       "pKnown": m["pKnown"] if m else None,
                                       "earnedAt": st["earnedAt"] if st else None,
                                       "endorsedBy": endorser["name"] if endorser else None,
                                       "endorsedAt": st.get("endorsedAt") if st else None})
        order = ["Foundations", "Calculus", "Linear algebra", "Probability", "Machine learning"]
        holder_no = int(uid.encode().hex()[-6:], 16) % 10000
        nxt = None
        if open_diag:
            # Entry required = the first stop on the route that is not stamped yet.
            first_open = next((c for c in open_diag["path"] if c not in stamps), open_diag["targetConceptId"])
            nxt = {"targetConceptId": open_diag["targetConceptId"], "targetName": self.cat.name(open_diag["targetConceptId"]),
                   "entryRequired": self.cat.name(first_open),
                   "entryRequiredId": first_open,
                   "route": [{"id": c, "name": self.cat.name(c), "stamped": c in stamps} for c in open_diag["path"]],
                   "diagnosisId": open_diag["id"]}
        style = dict(user.get("passportStyle") or {})
        style.setdefault("cover", PASSPORT_COVERS[0])
        style.setdefault("emblem", PASSPORT_EMBLEMS[0])
        lab_names = {lab["id"]: lab["name"] for lab in self.cat.labs}
        return {"holder": style.get("displayName") or user["name"], "holderNo": f"Student #A-{holder_no:04d}",
                "style": style, "focusLabs": [lab_names[x] for x in style.get("focusLabIds", []) if x in lab_names],
                "programme": user.get("programme"), "year": user.get("year"), "module": self.cat.course["name"],
                "regions": [{"name": r, "concepts": regions[r]} for r in order if r in regions],
                "stamps": len(stamps), "endorsed": sum(1 for s in stamps.values() if s["tier"] == "endorsed"),
                "next": nxt, "shared": bool(user["consent"].get("sharePassport"))}

    # ================================================================== circles =============
    def _latest_root(self, uid: str) -> str | None:
        docs = sorted(self.store.list("diagnoses", lambda d: d["uid"] == uid and d.get("status") == "done"
                                      and d.get("rootCauseConceptId")), key=lambda d: d["createdAt"])
        return docs[-1]["rootCauseConceptId"] if docs else None

    def _active_circles(self, concept: str | None = None) -> list[dict]:
        return self.store.list("studyCircles", lambda c: c["status"] != "done" and (concept is None or c["conceptId"] == concept))

    def _eligible(self, concept: str) -> dict[str, list[str]]:
        in_circle = {u for c in self._active_circles(concept) for u in c["memberUids"]}
        out = {}
        for u in self.store.list("users", lambda u: u["role"] == "student"):
            if u["uid"] in in_circle or not u["consent"].get("joinCircles") or not u["availability"]:
                continue
            if self._latest_root(u["uid"]) != concept:
                continue
            if StoreMastery(self.store, u["uid"]).get(concept)[0] >= config.SOLID:
                continue  # already resolved
            out[u["uid"]] = u["availability"]
        return out

    def _booked(self) -> dict[str, int]:
        b: Counter = Counter()
        for c in self._active_circles():
            if c.get("lecturerSlotId"):
                b[c["lecturerSlotId"]] += len(c["memberUids"])
        return dict(b)

    def circle_view(self, c: dict, viewer: dict) -> dict:
        members = []
        for uid in c["memberUids"]:
            u = self.store.get("users", uid) or {}
            if uid == viewer["uid"]:
                label = "You"
            elif viewer["role"] == "lecturer":
                label = u.get("name") if u.get("consent", {}).get("shareNameWithLecturer") else None
            else:
                label = u.get("name") if u.get("consent", {}).get("shareNameWithCircle") else None
            members.append(label or "Anonymous student")
        slot = self.store.get("lecturerSlots", c["lecturerSlotId"]) if c.get("lecturerSlotId") else None
        lect = self.store.get("users", slot["lecturerUid"]) if slot else None
        tiers = [(self.store.get("stamps", f"{u}_{c['conceptId']}") or {}).get("tier") for u in c["memberUids"]]
        return {"id": c["id"], "conceptId": c["conceptId"], "conceptName": self.cat.name(c["conceptId"]),
                "stampsVerified": sum(1 for t in tiers if t == "verified"),
                "stampsEndorsed": sum(1 for t in tiers if t == "endorsed"),
                "status": c["status"], "proposedSlot": c["proposedSlot"], "slotLabel": sched.slot_label(c["proposedSlot"]),
                "memberCount": len(c["memberUids"]), "members": members,
                "lecturerSlotId": c.get("lecturerSlotId"), "lecturerConfirmed": c.get("lecturerConfirmed", False),
                "lecturerName": lect["name"] if lect else None, "slotKind": slot["kind"] if slot else None,
                "mode": "lecturer" if slot else "peer", "isMember": viewer["uid"] in c["memberUids"],
                "note": c.get("note"), "synthetic": c.get("synthetic", False)}

    def circle_suggestion(self, user: dict, concept: str | None = None) -> dict:
        concept = concept or self._latest_root(user["uid"])
        if not concept:
            return {"status": "no-diagnosis"}
        if concept not in self.cat.concepts:
            raise ServiceError(404, "Unknown concept.")
        base = {"conceptId": concept, "conceptName": self.cat.name(concept)}
        mine = [c for c in self._active_circles(concept) if user["uid"] in c["memberUids"]]
        if mine:
            return base | {"status": "member", "circle": self.circle_view(mine[0], user)}
        if not user["availability"]:
            return base | {"status": "need-availability"}
        for c in self._active_circles(concept):
            if c["proposedSlot"] in user["availability"] and len(c["memberUids"]) < config.MAX_GROUP_SIZE:
                return base | {"status": "existing", "circle": self.circle_view(c, user)}
        avail = self._eligible(concept)
        avail[user["uid"]] = user["availability"]
        prop = sched.propose_circle(concept, avail, self.store.list("lecturerSlots"), self._booked(),
                                    config.MIN_GROUP_SIZE, config.MAX_GROUP_SIZE, must_include=user["uid"])
        if not prop:
            others = len(avail) - 1
            return base | {"status": "not-enough", "peersWithGap": others,
                           "message": f"{others} other opted-in student(s) share this gap, but fewer than "
                                      f"{config.MIN_GROUP_SIZE} are free at the same hour as you. Add more free hours "
                                      "or check back later."}
        fake = {"id": "proposal", "status": "proposal", **prop}
        return base | {"status": "proposal", "circle": self.circle_view(fake, user)}

    def join_circle(self, user: dict, concept: str) -> dict:
        sug = self.circle_suggestion(user, concept)
        if sug["status"] == "member":
            return sug["circle"]
        user["consent"]["joinCircles"] = True
        self.store.put("users", user["uid"], user)
        if sug["status"] == "existing":
            c = self.store.get("studyCircles", sug["circle"]["id"])
            c["memberUids"].append(user["uid"])
            self.store.put("studyCircles", c["id"], c)
            return self.circle_view(c, user)
        if sug["status"] != "proposal":
            raise ServiceError(409, sug.get("message") or "No circle can be formed right now.")
        avail = self._eligible(concept)
        avail[user["uid"]] = user["availability"]
        prop = sched.propose_circle(concept, avail, self.store.list("lecturerSlots"), self._booked(),
                                    config.MIN_GROUP_SIZE, config.MAX_GROUP_SIZE, must_include=user["uid"])
        cid = "c-" + uuid.uuid4().hex[:10]
        c = {"id": cid, "courseId": self.cat.course["id"], "conceptId": concept, "memberUids": prop["memberUids"],
             "status": "forming" if prop["lecturerSlotId"] else "scheduled", "proposedSlot": prop["proposedSlot"],
             "lecturerSlotId": prop["lecturerSlotId"], "lecturerConfirmed": False, "peerMentorUid": None,
             "createdAt": _iso()}
        self.store.put("studyCircles", cid, c)
        log.info("circle %s created for %s with %d members", cid, concept, len(c["memberUids"]))
        return self.circle_view(c, user)

    def my_circles(self, user: dict) -> list[dict]:
        return [self.circle_view(c, user) for c in self.store.list("studyCircles", lambda c: user["uid"] in c["memberUids"])]

    def circle_done(self, user: dict, circle_id: str) -> dict:
        c = self.store.get("studyCircles", circle_id)
        if not c or user["uid"] not in c["memberUids"]:
            raise ServiceError(404, "Circle not found.")
        c["status"] = "done"
        self.store.put("studyCircles", circle_id, c)
        return self.circle_view(c, user)

    # ================================================================== lecturer ============
    def _require_lecturer(self, user: dict) -> None:
        if user["role"] != "lecturer":
            raise ServiceError(403, "This page is for lecturer accounts.")

    def lecturer_overview(self, user: dict) -> dict:
        self._require_lecturer(user)
        lab_names = {lab["id"]: lab["name"] for lab in self.cat.labs}
        # Demand: students whose latest root cause is still unresolved.
        demand_users: dict[str, list[str]] = defaultdict(list)
        demand_labs: dict[str, Counter] = defaultdict(Counter)
        latest: dict[str, dict] = {}
        for d in self.store.list("diagnoses", lambda d: d.get("status") == "done" and d.get("rootCauseConceptId")):
            if d["uid"] not in latest or d["createdAt"] > latest[d["uid"]]["createdAt"]:
                latest[d["uid"]] = d
        for uid, d in latest.items():
            root = d["rootCauseConceptId"]
            if StoreMastery(self.store, uid).get(root)[0] >= config.SOLID:
                continue
            demand_users[root].append(uid)
            lab = self.cat.lab_for(d["targetConceptId"])
            if lab:
                demand_labs[root][lab] += 1
        demand, hidden = [], 0
        for root, uids in sorted(demand_users.items(), key=lambda kv: -len(kv[1])):
            if len(uids) < config.MIN_COUNT_SHOWN:
                hidden += 1
                continue
            top_lab = demand_labs[root].most_common(1)[0][0] if demand_labs[root] else None
            demand.append({"conceptId": root, "conceptName": self.cat.name(root), "students": len(uids),
                           "labId": top_lab, "labName": lab_names.get(top_lab)})
        # Heatmap from anonymised events.
        cells: dict[str, Counter] = defaultdict(Counter)
        for ev in self.store.list("diagnosisEvents"):
            if ev.get("labId"):
                cells[ev["rootCauseConceptId"]][ev["labId"]] += 1
        rows = []
        for root, cnt in sorted(cells.items(), key=lambda kv: -sum(kv[1].values()))[:12]:
            rows.append({"conceptId": root, "conceptName": self.cat.name(root), "total": sum(cnt.values()),
                         "cells": {lab["id"]: (cnt[lab["id"]] if cnt[lab["id"]] >= config.MIN_COUNT_SHOWN else None)
                                   for lab in self.cat.labs},
                         "hiddenCells": sum(1 for lab in self.cat.labs if 0 < cnt[lab["id"]] < config.MIN_COUNT_SHOWN)})
        my_slots = self.store.list("lecturerSlots", lambda s: s["lecturerUid"] == user["uid"])
        my_ids = {s["id"] for s in my_slots}
        booked = self._booked()
        circles = [self.circle_view(c, user) for c in self._active_circles() if c.get("lecturerSlotId") in my_ids]
        slots = [dict(s, label=f"{s['day']} {s['start']:02d}:00-{s['end']:02d}:00", booked=booked.get(s["id"], 0),
                      linkedNames=[self.cat.name(c) for c in s["linkedConceptIds"]]) for s in my_slots]
        recent = [e for e in self.store.list("diagnosisEvents") if _parse(e["timestamp"]) > _now() - timedelta(days=14)]
        shared: dict[str, list[dict]] = defaultdict(list)
        for s in self.store.list("stamps", lambda s: s.get("shareable")):
            shared[s["uid"]].append(s)
        shared_passports = []
        for uid, sts in shared.items():
            u = self.store.get("users", uid) or {}
            shared_passports.append({"name": u.get("name", "Student"), "stamps": [
                {"conceptName": self.cat.name(s["conceptId"]), "tier": s["tier"]} for s in sts]})
        return {"minCount": config.MIN_COUNT_SHOWN, "demand": demand, "hiddenDemandGroups": hidden,
                "heatmap": {"labs": [{"id": lab["id"], "name": lab["name"]} for lab in self.cat.labs], "rows": rows},
                "slots": sorted(slots, key=lambda s: (sched.DAYS.index(s["day"]), s["start"])),
                "requests": [c for c in circles if not c["lecturerConfirmed"]],
                "scheduled": [c for c in circles if c["lecturerConfirmed"]],
                "stats": {"diagnosesLast14Days": len(recent), "studentsWithOpenGaps": sum(len(v) for v in demand_users.values())},
                "sharedPassports": shared_passports,
                "syntheticData": any(e.get("synthetic") for e in self.store.list("diagnosisEvents"))}

    def create_slot(self, user: dict, data: dict) -> dict:
        self._require_lecturer(user)
        day, kind = data.get("day"), data.get("kind", "consultation")
        try:
            start, end, cap = int(data.get("start")), int(data.get("end")), int(data.get("capacity"))
        except (TypeError, ValueError):
            raise ServiceError(400, "Start, end and capacity must be whole numbers.")
        linked = [c for c in (data.get("linkedConceptIds") or []) if c in self.cat.concepts]
        if day not in sched.DAYS or not (9 <= start < end <= 18) or not 1 <= cap <= 50:
            raise ServiceError(400, "Pick a weekday and hours between 09:00 and 18:00, with capacity 1 to 50.")
        if not linked:
            raise ServiceError(400, "Link the slot to at least one concept.")
        if kind not in ("consultation", "gap-clinic"):
            raise ServiceError(400, "Unknown slot type.")
        sid = "slot-" + uuid.uuid4().hex[:8]
        slot = {"id": sid, "lecturerUid": user["uid"], "courseId": self.cat.course["id"], "day": day, "start": start,
                "end": end, "capacity": cap, "kind": kind, "linkedConceptIds": linked, "createdAt": _iso()}
        self.store.put("lecturerSlots", sid, slot)
        return slot

    def open_clinic(self, user: dict, concept: str) -> dict:
        self._require_lecturer(user)
        if concept not in self.cat.concepts:
            raise ServiceError(404, "Unknown concept.")
        avail = self._eligible(concept)
        slot, free = sched.best_common_slot(avail)
        if not slot:
            raise ServiceError(409, "No opted-in students with this gap have shared their free hours yet.")
        d, h = slot.split("-")
        new = self.create_slot(user, {"day": d, "start": int(h), "end": int(h) + 1, "kind": "gap-clinic",
                                      "capacity": max(8, len(free) + 2), "linkedConceptIds": [concept]})
        return {"slot": new, "studentsFree": len(free), "slotLabel": sched.slot_label(slot)}

    def _lecturer_circle(self, user: dict, circle_id: str) -> dict:
        self._require_lecturer(user)
        c = self.store.get("studyCircles", circle_id)
        slot = self.store.get("lecturerSlots", c["lecturerSlotId"]) if c and c.get("lecturerSlotId") else None
        if not c or not slot or slot["lecturerUid"] != user["uid"]:
            raise ServiceError(404, "Circle not found in your slots.")
        return c

    def confirm_circle(self, user: dict, circle_id: str) -> dict:
        c = self._lecturer_circle(user, circle_id)
        c.update(lecturerConfirmed=True, status="scheduled")
        self.store.put("studyCircles", circle_id, c)
        return self.circle_view(c, user)

    def endorse_circle(self, user: dict, circle_id: str) -> dict:
        """Countersign the verified stamps of a confirmed circle's members (passport: endorsed tier)."""
        c = self._lecturer_circle(user, circle_id)
        if not c.get("lecturerConfirmed"):
            raise ServiceError(409, "Confirm the session before countersigning stamps.")
        endorsed, waiting = 0, 0
        for uid in c["memberUids"]:
            key = f"{uid}_{c['conceptId']}"
            s = self.store.get("stamps", key)
            if s and s["tier"] == "verified":
                s.update(tier="endorsed", endorsedByUid=user["uid"], endorsedAt=_iso())
                self.store.put("stamps", key, s, save=False)
                endorsed += 1
            elif not s:
                waiting += 1
        self.store.save()
        log.info("lecturer %s endorsed %d stamps in circle %s", user["uid"], endorsed, circle_id)
        return {"endorsed": endorsed, "waitingForRecheck": waiting, "circle": self.circle_view(c, user)}

    def decline_circle(self, user: dict, circle_id: str) -> dict:
        c = self._lecturer_circle(user, circle_id)
        c.update(lecturerSlotId=None, lecturerConfirmed=False, status="scheduled",
                 note="The lecturer could not take this slot, so the circle meets as a peer session.")
        self.store.put("studyCircles", circle_id, c)
        return self.circle_view(c, user)


def _label(tag: str | None) -> str | None:
    return tag.replace("-", " ").capitalize() if tag else None
