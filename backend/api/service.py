"""Application logic behind the HTTP API. Routes in api/factory.py stay thin and call PuncaService."""
from __future__ import annotations

import logging
import re
import uuid
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import auth
import config
import google_workspace as gws
from content import Catalog
from diagnosis import bkt
from diagnosis.engine import DiagnosisEngine, DiagnosisError, Params
from google_live import SCOPES as GOOGLE_SCOPES, GoogleLive, GoogleLiveError
from llm.service import LLMService
from scheduling import circles as sched
from store.local_store import LocalStore

log = logging.getLogger("punca.api")

PASSPORT_COVERS = ["navy", "maroon", "forest", "teal", "plum"]
PASSPORT_EMBLEMS = ["spring", "compass", "atom", "leaf", "star"]

ALL_AREAS_ORDER = [
    "Maths Foundations (pre-university)",
    "Computing & Programming Foundations",
    "Computational Mathematics",
    "Introduction to Python",
    "Object Oriented Programming with Java",
    "Introduction to Databases",
]


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
        self.store.put(
            "mastery",
            f"{self.uid}_{cid}",
            {
                "uid": self.uid,
                "conceptId": cid,
                "pKnown": round(p, 4),
                "evidenceCount": ev,
                "lastUpdated": _iso(),
                **extra,
            },
        )


class PuncaService:
    def __init__(
        self,
        catalog: Catalog,
        store: LocalStore,
        llm: LLMService,
        params: Params | None = None,
        live: GoogleLive | None = None,
    ):
        self.cat = catalog
        self.store = store
        self.llm = llm
        self.params = params or Params()
        self.live = live or GoogleLive()
        self.engine = DiagnosisEngine(catalog.graph, catalog.probes, catalog.probes_by_concept, self.params)

    # ================================================================== accounts ============
    @staticmethod
    def public_user(u: dict) -> dict:
        ws = u.get("googleWorkspace") or {}
        return {
            k: u.get(k)
            for k in (
                "uid",
                "role",
                "name",
                "email",
                "university",
                "studentId",
                "programme",
                "year",
                "availability",
                "consent",
                "createdAt",
                "passportStyle",
            )
        } | {
            "demoAccount": u.get("demoAccount", False),
            "googleConnected": bool(ws.get("connected", True)),
            "googleEmail": ws.get("email") or u.get("email"),
            "googleLive": ws.get("mode") == "oauth-live",
        }

    def _user_by_email(self, email: str) -> dict | None:
        email = email.strip().lower()
        hits = self.store.list("users", lambda u: (u.get("email") or "").lower() == email)
        return hits[0] if hits else None

    def _issue_token(self, uid: str) -> str:
        token = auth.new_token()
        self.store.put(
            "authTokens",
            auth.token_key(token),
            {
                "uid": uid,
                "createdAt": _iso(),
                "expiresAt": _iso(_now() + timedelta(days=auth.TOKEN_TTL_DAYS)),
            },
        )
        return token

    def signup(self, data: dict) -> dict:
        """Student sign-up."""
        role = "student"
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        university = (data.get("university") or "").strip()
        student_id = (data.get("studentId") or "").strip().upper()
        course = (data.get("programme") or "").strip()
        if not 2 <= len(name) <= 60:
            raise ServiceError(400, "Enter your name (2 to 60 characters).")
        if not auth.valid_email(email):
            raise ServiceError(400, "Enter a valid personal email address.")
        if len(password) < 8 or len(password) > 128:
            raise ServiceError(400, "Use a password of at least 8 characters.")
        if password != data.get("confirmPassword"):
            raise ServiceError(400, "Passwords do not match.")
        if not 2 <= len(university) <= 120:
            raise ServiceError(400, "Enter your university (2 to 120 characters).")
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]{0,39}", student_id):
            raise ServiceError(
                400,
                "Enter a student ID of up to 40 letters or numbers. Dots, hyphens, underscores and slashes are allowed.",
            )
        if not 2 <= len(course) <= 80:
            raise ServiceError(400, "Enter your course (2 to 80 characters).")
        extra: dict = {"programme": course, "university": university, "studentId": student_id}
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
        user = {
            "uid": uid,
            "role": role,
            "name": name,
            "email": email,
            "passwordHash": auth.hash_password(password),
            "programme": None,
            "year": None,
            "courseIds": [self.cat.course["id"]],
            "availability": [],
            "consent": {
                "joinCircles": False,
                "shareNameWithCircle": False,
                "shareContact": False,
                "sharePassport": False,
            },
            "synthetic": False,
            "createdAt": _iso(),
        }
        user.update(extra)
        gws.ensure_workspace(user)
        conflict = self.store.create_user(user)
        if conflict == "email":
            raise ServiceError(409, "An account with that email already exists. Sign in instead.")
        if conflict == "studentId":
            raise ServiceError(409, "That student ID is already registered. Sign in to your existing account.")
        log.info("account created uid=%s role=%s", uid, role)
        return {"token": self._issue_token(uid), "user": self.public_user(user)}

    def login(self, email: str, password: str) -> dict:
        user = self._user_by_email(email or "")
        if not user or not auth.verify_password(password or "", user.get("passwordHash")):
            raise ServiceError(401, "Email or password is not correct.")
        if "googleWorkspace" not in user:
            gws.ensure_workspace(user)
            self.store.put("users", user["uid"], user)
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
        """Update the signed-in student's own details. Only the fields present in `data` change."""
        uid = user["uid"]

        def taken(field: str, value: str) -> bool:
            key = value.strip().casefold()
            return any(
                (u.get(field) or "").strip().casefold() == key
                for u in self.store.list("users", lambda u: u["uid"] != uid)
            )

        if "name" in data:
            name = (data["name"] or "").strip()
            if not 2 <= len(name) <= 60:
                raise ServiceError(400, "Enter your name (2 to 60 characters).")
            style = user.get("passportStyle") or {}
            if style.get("displayName") == user.get("name"):
                style["displayName"] = name  # the passport showed the account name, so keep them in step
            user["name"] = name
        if "university" in data:
            university = (data["university"] or "").strip()
            if not 2 <= len(university) <= 120:
                raise ServiceError(400, "Enter your university (2 to 120 characters).")
            user["university"] = university
        if "studentId" in data:
            student_id = (data["studentId"] or "").strip().upper()
            if student_id != (user.get("studentId") or ""):
                if user.get("demoAccount"):
                    raise ServiceError(400, "Demo accounts keep their student ID. Create your own account to use yours.")
                if not re.fullmatch(r"[A-Z0-9][A-Z0-9._/-]{0,39}", student_id):
                    raise ServiceError(
                        400,
                        "Enter a student ID of up to 40 letters or numbers. Dots, hyphens, underscores and slashes are allowed.",
                    )
                if taken("studentId", student_id):
                    raise ServiceError(409, "That student ID is already registered to another account.")
                user["studentId"] = student_id
        if "email" in data:
            email = (data["email"] or "").strip().lower()
            if email != (user.get("email") or "").lower():
                if user.get("demoAccount"):
                    raise ServiceError(400, "Demo accounts keep their sign-in email. Create your own account to use your email.")
                if not auth.valid_email(email):
                    raise ServiceError(400, "Enter a valid personal email address.")
                if taken("email", email):
                    raise ServiceError(409, "Another account already uses that email.")
                ws = user.get("googleWorkspace")
                if isinstance(ws, dict) and (ws.get("email") or "").lower() == (user.get("email") or "").lower():
                    ws["email"] = email
                user["email"] = email
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
            for k in ("joinCircles", "shareNameWithCircle", "shareContact", "sharePassport"):
                if k in (data["consent"] or {}):
                    user["consent"][k] = bool(data["consent"][k])
            if "sharePassport" in (data["consent"] or {}):
                for s in self.store.list("stamps", lambda s: s["uid"] == user["uid"]):
                    s["shareable"] = user["consent"]["sharePassport"]
                    self.store.put("stamps", f"{s['uid']}_{s['conceptId']}", s, save=False)
        self.store.put("users", user["uid"], user)
        return self.public_user(user)

    def _passport_style(self, user: dict, p: dict) -> dict:
        """Validate passport customisation: cover colour, user photo, display name, motto, preset & custom labs."""
        cur = dict(user.get("passportStyle") or {})
        if "cover" in p:
            if p["cover"] not in PASSPORT_COVERS:
                raise ServiceError(400, "Pick one of the passport cover colours.")
            cur["cover"] = p["cover"]
        if "emblem" in p and p["emblem"] in PASSPORT_EMBLEMS:
            cur["emblem"] = p["emblem"]
        if "photoUrl" in p:
            photo = p["photoUrl"]
            if not photo:
                cur["photoUrl"] = None
            elif isinstance(photo, str):
                photo = photo.strip()
                if len(photo) > 500_000:
                    raise ServiceError(400, "Passport photo is too large. Please choose an image under 350 KB.")
                cur["photoUrl"] = photo
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
        if "customLabs" in p:
            raw_custom = p.get("customLabs") or []
            if not isinstance(raw_custom, list):
                raise ServiceError(400, "customLabs must be a list of lab names.")
            cleaned_custom: list[str] = []
            for item in raw_custom[:15]:
                if isinstance(item, str):
                    txt = item.strip()[:80]
                    if txt and txt not in cleaned_custom:
                        cleaned_custom.append(txt)
            cur["customLabs"] = cleaned_custom
        cur.setdefault("cover", PASSPORT_COVERS[0])
        cur.setdefault("emblem", PASSPORT_EMBLEMS[0])
        cur.setdefault("photoUrl", None)
        cur.setdefault("displayName", user["name"])
        cur.setdefault("motto", None)
        cur.setdefault("focusLabIds", [])
        cur.setdefault("customLabs", [])
        cur["setupDone"] = True
        return cur

    # ================================================================== mastery =============
    def mastery_map(self, uid: str) -> dict:
        out = {}
        for d in self.store.list("mastery", lambda m: m["uid"] == uid):
            out[d["conceptId"]] = {
                "pKnown": d["pKnown"],
                "evidenceCount": d["evidenceCount"],
                "status": bkt.status(d["pKnown"], d["evidenceCount"]),
                "selfReported": d.get("selfReported", False),
            }
        return out

    def mark_known(self, uid: str, cid: str) -> dict:
        if cid not in self.cat.concepts:
            raise ServiceError(404, "Unknown concept.")
        book = StoreMastery(self.store, uid)
        p, ev = book.get(cid)
        book.set(cid, max(p, config.SOLID + 0.05), ev + 1, selfReported=True)
        log.info("uid=%s corrected %s to known", uid, cid)
        return self.mastery_map(uid)

    @staticmethod
    def _stamp_slipped(cid: str, mastery: dict) -> bool:
        """A completed stamp needs re-entry once later answers pull the concept back below solid."""
        m = mastery.get(cid)
        return bool(m) and m["pKnown"] < config.SOLID

    def _concept_passport_state(self, cid: str, mastery: dict, stamps: dict) -> str:
        st = stamps.get(cid)
        if st:
            return "reentry" if self._stamp_slipped(cid, mastery) else "stamped"
        m = mastery.get(cid)
        if m and m["status"] == "gap":
            return "entry-required"
        if m and m["status"] in ("shaky", "solid"):
            return m["status"]
        return "untested"

    # ================================================================== diagnosis ===========
    def _assess_required_foundations(self, uid: str, combined_text: str, target_cid: str | None) -> list[dict]:
        """Identify the 5–8 foundational concepts required by the written brief + uploaded document."""
        mastery = self.mastery_map(uid)
        stamps = {s["conceptId"]: s for s in self.store.list("stamps", lambda s: s["uid"] == uid)}
        hits = self.cat.search_concepts(combined_text, k=6)
        ordered_ids: list[str] = []
        if target_cid and target_cid in self.cat.concepts:
            ordered_ids.append(target_cid)
        for h in hits:
            if h["conceptId"] not in ordered_ids:
                ordered_ids.append(h["conceptId"])
        # Add direct and secondary prerequisites of top matched concepts so foundations are covered
        for cid in list(ordered_ids[:3]):
            for pre in self.cat.graph.prereqs(cid):
                if pre not in ordered_ids:
                    ordered_ids.append(pre)
            for anc in self.cat.graph.ancestors(cid):
                if anc not in ordered_ids and len(ordered_ids) < 8:
                    ordered_ids.append(anc)
        foundations: list[dict] = []
        for cid in ordered_ids[:8]:
            c = self.cat.concepts[cid]
            foundations.append({
                "conceptId": cid,
                "name": c["name"],
                "area": c["area"],
                "description": c["description"],
                "state": self._concept_passport_state(cid, mastery, stamps),
                "isTarget": cid == target_cid,
            })
        return foundations

    def map_stuck(self, user: dict, text: str, file_data: dict | None = None) -> dict:
        text = (text or "").strip()
        file_data = file_data or {}
        doc_summary = None
        extracted_doc_text = ""

        # A file uploaded from the student's PC, if any.
        file_name = (file_data.get("fileName") or "").strip()
        file_b64 = file_data.get("fileBase64")
        file_text = file_data.get("fileText")

        if file_name or file_b64 or file_text:
            try:
                parsed = gws.extract_document_text(file_name or "uploaded-brief.txt", file_b64, file_text)
            except gws.WorkspaceError as exc:
                raise ServiceError(exc.status, exc.message) from exc
            extracted_doc_text = parsed["text"]
            doc_summary = {
                "source": "pc-upload",
                "fileName": parsed["filename"],
                "summary": parsed["summary"],
                "wordCount": parsed["wordCount"],
            }

        combined = f"{text}\n\n{extracted_doc_text}".strip()
        if not 3 <= len(combined) <= 15000:
            raise ServiceError(400, "Describe what you are stuck on or attach a lab/question document (at least 3 characters).")
        m = self.llm.map_stuck_point(combined[:2500])
        target_cid = m.get("targetConceptId")
        m["targetName"] = self.cat.name(target_cid)
        foundations = self._assess_required_foundations(user["uid"], combined, target_cid)
        m["requiredFoundations"] = foundations
        m["requiredFoundationIds"] = [f["conceptId"] for f in foundations]
        m["documentSummary"] = doc_summary
        return m

    def _used_probes(self, uid: str) -> list[str]:
        used: list[str] = []
        for d in sorted(
            self.store.list("diagnoses", lambda x: x["uid"] == uid and "state" in x),
            key=lambda x: x["createdAt"],
        ):
            used += d["state"]["usedProbeIds"]
        return used

    def start_diagnosis(self, user: dict, text: str, target: str, mapping: dict | None) -> dict:
        if user["role"] != "student":
            raise ServiceError(403, "Only student accounts can run a diagnosis.")
        text = (text or "").strip()
        mapping = mapping or {}
        doc_summary = mapping.get("documentSummary")
        if not text and doc_summary:
            text = f"Uploaded file: {doc_summary.get('fileName')} — {doc_summary.get('summary', '')}"[:1800]
        if not 3 <= len(text) <= 4000:
            raise ServiceError(400, "Describe what you are stuck on in 3 to 4000 characters.")
        if target not in self.cat.concepts:
            raise ServiceError(400, "Pick a concept from the list.")
        focus_concepts = mapping.get("requiredFoundationIds") or [
            f["conceptId"] for f in (mapping.get("requiredFoundations") or []) if isinstance(f, dict) and "conceptId" in f
        ]
        if not focus_concepts:
            foundations = self._assess_required_foundations(user["uid"], text, target)
            focus_concepts = [f["conceptId"] for f in foundations]
            mapping["requiredFoundations"] = foundations
            mapping["requiredFoundationIds"] = focus_concepts

        state = self.engine.new_state(
            target,
            self._used_probes(user["uid"])[-40:],
            focus_concepts=focus_concepts,
        )
        self.engine.start(state, StoreMastery(self.store, user["uid"]))
        did = "d-" + uuid.uuid4().hex[:12]
        doc = {
            "id": did,
            "uid": user["uid"],
            "courseId": self.cat.course["id"],
            "stuckInput": text,
            "targetConceptId": target,
            "mapping": mapping,
            "state": state,
            "status": state["status"],
            "rootCauseConceptId": None,
            "path": [],
            "createdAt": _iso(),
        }
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
                self.store.put(
                    "diagnosisEvents",
                    "ev-" + uuid.uuid4().hex[:10],
                    {
                        "courseId": doc["courseId"],
                        "labId": self.cat.lab_for(doc["targetConceptId"]),
                        "targetConceptId": doc["targetConceptId"],
                        "rootCauseConceptId": res["rootCauseConceptId"],
                        "timestamp": _iso(),
                    },
                )

    def _own_diagnosis(self, uid: str, did: str) -> dict:
        doc = self.store.get("diagnoses", did)
        if not doc or doc["uid"] != uid or "state" not in doc:
            raise ServiceError(404, "Diagnosis not found.")
        return doc

    def answer(self, uid: str, did: str, probe_id: str, choice: int, confidence: str = "medium") -> dict:
        doc = self._own_diagnosis(uid, did)
        try:
            fb = self.engine.answer(
                doc["state"],
                probe_id,
                choice,
                StoreMastery(self.store, uid),
                confidence=confidence,
            )
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
        docs = sorted(
            self.store.list("diagnoses", lambda d: d["uid"] == uid and "state" in d),
            key=lambda d: d["createdAt"],
            reverse=True,
        )
        return [
            {
                "id": d["id"],
                "stuckInput": d["stuckInput"],
                "status": d["status"],
                "createdAt": d["createdAt"],
                "targetConceptId": d["targetConceptId"],
                "targetName": self.cat.name(d["targetConceptId"]),
                "rootCauseConceptId": d.get("rootCauseConceptId"),
                "rootCauseName": self.cat.name(d.get("rootCauseConceptId")),
                "probesAsked": len((d.get("state") or {}).get("asked") or []),
            }
            for d in docs
        ]

    def diagnosis_view(self, doc: dict) -> dict:
        st = doc["state"]
        pending = None
        if st.get("pending"):
            pending = self.cat.public_probe(self.cat.probes[st["pending"]["probeId"]])
        asked = []
        for a in st["asked"]:
            p = self.cat.probes[a["probeId"]]
            asked.append({
                "probeId": a["probeId"],
                "conceptId": a["conceptId"],
                "conceptName": self.cat.name(a["conceptId"]),
                "question": p["question"],
                # Answers stored before the option order was mixed have no choiceText and
                # point into the written order.
                "yourAnswer": a.get("choiceText") or p.get("originalOptions", p["options"])[a["choiceIndex"]],
                "correctAnswer": p["options"][p["correctIndex"]],
                "correct": a["correct"],
                "confidence": a.get("confidence", "medium"),
                "highConfidenceGap": a.get("highConfidenceGap", False),
                "luckyGuess": a.get("luckyGuess", False),
                "misconception": a["misconception"],
                "misconceptionLabel": _label(a["misconception"]),
            })
        result = None
        if st.get("result"):
            r = st["result"]
            named = lambda ids: [{"id": c, "name": self.cat.name(c)} for c in ids]  # noqa: E731
            root_id = r.get("rootCauseConceptId")
            related_ids = self.cat.graph.related(root_id) if root_id and root_id in self.cat.concepts else []
            result = dict(
                r,
                targetName=self.cat.name(r["targetConceptId"]),
                rootCauseName=self.cat.name(root_id),
                path=named(r["remediationPath"]),
                otherGapsNamed=named(r["otherGaps"]),
                untestedNamed=named(r["untestedPrerequisites"]),
                skippedSolidNamed=named(r["skippedSolid"]),
                relatedNamed=named(related_ids),
            )
        return {
            "id": doc["id"],
            "stuckInput": doc["stuckInput"],
            "status": st["status"],
            "targetConceptId": doc["targetConceptId"],
            "targetName": self.cat.name(doc["targetConceptId"]),
            "mapping": doc.get("mapping") or {},
            "probesAsked": len(st["asked"]),
            "minProbes": st.get("minProbes", self.params.min_probes),
            "maxProbes": st["maxProbes"],
            "pending": pending,
            "asked": asked,
            "result": result,
            "createdAt": doc["createdAt"],
        }

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
                    out.append(
                        dict(
                            self.cat.public_probe(p),
                            correctIndex=p["correctIndex"],
                            explanation=p.get("explanation", ""),
                        )
                    )
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
        prior = max(p, 0.15) if correct else p
        p2 = bkt.update(prior, correct, self.params.p_guess, self.params.p_slip, self.params.p_learn)
        book.set(cid, p2, ev + 1)
        user.pop("pendingRecheck", None)
        user.setdefault("lastRecheck", {})[cid] = probe_id
        self.store.put("users", user["uid"], user)
        stamp, earned, renewed = self.store.get("stamps", f"{user['uid']}_{cid}"), False, False
        if p2 >= config.SOLID and not stamp:
            stamp = {
                "uid": user["uid"],
                "conceptId": cid,
                "tier": "completed",
                "earnedAt": _iso(),
                "basedOnDiagnosisId": self._diagnosis_touching(user["uid"], cid),
                "shareable": bool(user["consent"].get("sharePassport")),
            }
            self.store.put("stamps", f"{user['uid']}_{cid}", stamp)
            earned = True
            log.info("uid=%s completed a stamp for %s", user["uid"], cid)
        elif p2 >= config.SOLID and p < config.SOLID:
            # The stamp had slipped to "re-entry required"; this passed re-check renews it.
            stamp["renewedAt"] = _iso()
            self.store.put("stamps", f"{user['uid']}_{cid}", stamp)
            renewed = True
            log.info("uid=%s renewed the stamp for %s", user["uid"], cid)
        return {
            "correct": correct,
            "correctIndex": probe["correctIndex"],
            "explanation": probe.get("explanation", ""),
            "conceptId": cid,
            "conceptName": self.cat.name(cid),
            "pKnown": round(p2, 4),
            "status": bkt.status(p2, ev + 1),
            "stampEarned": earned,
            "stampRenewed": renewed,
            "stamp": stamp,
        }

    def _diagnosis_touching(self, uid: str, cid: str) -> str | None:
        docs = sorted(
            self.store.list(
                "diagnoses",
                lambda d: d["uid"] == uid and (d.get("rootCauseConceptId") == cid or cid in (d.get("path") or [])),
            ),
            key=lambda d: d["createdAt"],
        )
        return docs[-1]["id"] if docs else None

    # ================================================================== passport ============
    def passport(self, user: dict) -> dict:
        uid = user["uid"]
        mastery = self.mastery_map(uid)
        all_stamps = {s["conceptId"]: s for s in self.store.list("stamps", lambda s: s["uid"] == uid)}
        # Stamps that still hold. A slipped stamp ("re-entry required") no longer clears a route.
        stamps = {cid: s for cid, s in all_stamps.items() if not self._stamp_slipped(cid, mastery)}
        open_diag = None
        for d in sorted(
            self.store.list(
                "diagnoses",
                lambda d: d["uid"] == uid and d.get("status") == "done" and d.get("rootCauseConceptId"),
            ),
            key=lambda d: d["createdAt"],
            reverse=True,
        ):
            if d["targetConceptId"] not in stamps:
                open_diag = d
                break
        entry_required = (
            {next((c for c in open_diag["path"] if c not in stamps), open_diag["targetConceptId"])}
            if open_diag
            else set()
        )
        regions: dict[str, list[dict]] = defaultdict(list)
        summary = {"completed": 0, "reentry": 0, "entryRequired": 0, "inProgress": 0}
        for cid, c in self.cat.concepts.items():
            m = mastery.get(cid)
            st = all_stamps.get(cid)
            if st and cid in stamps:
                state = "stamped"
                summary["completed"] += 1
            elif st:
                state = "reentry"
                summary["reentry"] += 1
            elif cid in entry_required or (m and m["status"] == "gap"):
                state = "entry-required"
                summary["entryRequired"] += 1
            elif m and m["status"] in ("shaky", "solid"):
                # Shaky, or solid but not yet stamped: both are one or two re-checks from a stamp.
                state = m["status"]
                summary["inProgress"] += 1
            else:
                state = "untested"
            regions[c["area"]].append({
                "conceptId": cid,
                "name": c["name"],
                "moduleId": c.get("moduleId"),
                "topicId": c.get("topicId"),
                "topicName": c.get("topicName"),
                "level": c.get("level", "core"),
                "optional": c.get("optional", False),
                "depth": c.get("depth", 0),
                "state": state,
                "pKnown": m["pKnown"] if m else None,
                "earnedAt": st["earnedAt"] if st else None,
                "renewedAt": st.get("renewedAt") if st else None,
                "canRecheck": bool(self.cat.probes_by_concept.get(cid)),
            })

        region_order = [m["name"] for m in self.cat.modules] if self.cat.modules else list(ALL_AREAS_ORDER)
        for area_name in regions:
            if area_name not in region_order:
                region_order.append(area_name)

        # The passport number is the student ID. Accounts without one keep a derived number.
        holder_no = user.get("studentId") or f"A-{int(uid.encode().hex()[-6:], 16) % 10000:04d}"
        nxt = None
        if open_diag:
            first_open = next((c for c in open_diag["path"] if c not in stamps), open_diag["targetConceptId"])
            nxt = {
                "targetConceptId": open_diag["targetConceptId"],
                "targetName": self.cat.name(open_diag["targetConceptId"]),
                "entryRequired": self.cat.name(first_open),
                "entryRequiredId": first_open,
                "route": [{"id": c, "name": self.cat.name(c), "stamped": c in stamps} for c in open_diag["path"]],
                "diagnosisId": open_diag["id"],
            }
        style = dict(user.get("passportStyle") or {})
        style.setdefault("cover", PASSPORT_COVERS[0])
        style.setdefault("emblem", PASSPORT_EMBLEMS[0])
        style.setdefault("photoUrl", None)
        style.setdefault("customLabs", [])
        lab_names = {lab["id"]: lab["name"] for lab in self.cat.labs}
        preset_labs = [lab_names[x] for x in style.get("focusLabIds", []) if x in lab_names]
        custom_labs = [x for x in style.get("customLabs", []) if isinstance(x, str) and x.strip()]
        focus_labs = preset_labs + [x for x in custom_labs if x not in preset_labs]

        ws = gws.ensure_workspace(user)
        live_now = self._is_live(user)
        workspace_summary = {
            "connected": bool(ws.get("connected", True)),
            "email": ws.get("email") or user.get("email"),
            "live": live_now,
            "mode": "oauth-live" if live_now else "workspace",
            "enabledServices": ws.get("enabledServices", {}),
            "calendarCount": len(ws.get("calendarEvents") or []),
            "openTasksCount": sum(1 for t in (ws.get("tasks") or []) if not t.get("completed")),
            "docsCount": len(ws.get("docs") or []),
            "chatSpacesCount": len(ws.get("chatSpaces") or []),
        }
        return {
            "holder": style.get("displayName") or user["name"],
            "holderNo": holder_no,
            "style": style,
            "focusLabs": focus_labs,
            "programme": user.get("programme"),
            "university": user.get("university"),
            "studentId": user.get("studentId"),
            "year": user.get("year"),
            "module": self.cat.course["name"],
            "regions": [{"name": r, "concepts": regions[r]} for r in region_order if r in regions],
            "stamps": len(stamps),
            "stampSummary": summary,
            "next": nxt,
            "shared": bool(user["consent"].get("sharePassport")),
            "googleWorkspace": workspace_summary,
        }

    # ================================================================== peer circles ========
    def _latest_root(self, uid: str) -> str | None:
        docs = sorted(
            self.store.list(
                "diagnoses",
                lambda d: d["uid"] == uid and d.get("status") == "done" and d.get("rootCauseConceptId"),
            ),
            key=lambda d: d["createdAt"],
        )
        return docs[-1]["rootCauseConceptId"] if docs else None

    def _active_circles(self, concept: str | None = None) -> list[dict]:
        return self.store.list(
            "studyCircles",
            lambda c: c["status"] != "done" and (concept is None or c["conceptId"] == concept),
        )

    def _user_gaps(self, uid: str) -> list[str]:
        """Concepts this student still needs to close, most relevant first.

        Root causes found by their diagnoses that are not yet solid come first (newest diagnosis
        first), then any other concept whose mastery is in the gap band.
        """
        mastery = self.mastery_map(uid)
        docs = sorted(
            self.store.list(
                "diagnoses",
                lambda d: d["uid"] == uid and d.get("status") == "done" and d.get("rootCauseConceptId"),
            ),
            key=lambda d: d["createdAt"],
            reverse=True,
        )
        out: list[str] = []
        for d in docs:
            cid = d["rootCauseConceptId"]
            p = mastery[cid]["pKnown"] if cid in mastery else config.P_INIT
            if p < config.SOLID and cid not in out and cid in self.cat.concepts:
                out.append(cid)
        for cid, m in mastery.items():
            if m["status"] == "gap" and cid not in out and cid in self.cat.concepts:
                out.append(cid)
        return out

    def _user_modules(self, user: dict) -> set[str]:
        """Module ids a student is working in: their chosen focus topics plus anything they have touched."""
        uid = user["uid"]
        lab_module = {lab["id"]: lab.get("moduleId") for lab in self.cat.labs}
        mods = {lab_module.get(x) for x in (user.get("passportStyle") or {}).get("focusLabIds", [])}
        for m in self.store.list("mastery", lambda m: m["uid"] == uid):
            mods.add((self.cat.concepts.get(m["conceptId"]) or {}).get("moduleId"))
        for d in self.store.list("diagnoses", lambda d: d["uid"] == uid):
            mods.add((self.cat.concepts.get(d.get("targetConceptId")) or {}).get("moduleId"))
        mods.discard(None)
        return mods

    def _eligible(self, concept: str) -> dict[str, list[str]]:
        """Opted-in students who still have this gap and are not already in a circle for it.

        Free hours are returned for matching, but an empty list no longer excludes anyone.
        """
        in_circle = {u for c in self._active_circles(concept) for u in c["memberUids"]}
        out = {}
        for u in self.store.list("users", lambda u: u["role"] == "student"):
            if u["uid"] in in_circle or not u["consent"].get("joinCircles"):
                continue
            if concept not in self._user_gaps(u["uid"]):
                continue
            out[u["uid"]] = u.get("availability") or []
        return out

    def _propose_members(self, concept: str, user: dict) -> dict | None:
        """Members, and a shared free hour when one exists, for a new circle on this gap.

        A shared hour is preferred but not required. With no overlap the circle is still proposed
        and its members agree a time in the chat. Returns None when nobody else has the gap.
        """
        me = user["uid"]
        avail = self._eligible(concept)
        avail[me] = user.get("availability") or []
        if len(avail) < 2:
            return None
        prop = sched.propose_circle(concept, avail, 2, config.MAX_GROUP_SIZE, must_include=me)
        members = list(prop["memberUids"]) if prop else [me]
        if len(members) < config.MIN_GROUP_SIZE + 1:
            mine = set(avail[me])
            rest = sorted(
                (u for u in avail if u not in members),
                # most free hours in common first; real accounts before sample peers
                key=lambda u: (-len(mine & set(avail[u])), u.startswith("u-syn-"), u),
            )
            members += rest[: config.MIN_GROUP_SIZE + 1 - len(members)]
        return {
            "conceptId": concept,
            "memberUids": members,
            "proposedSlot": prop["proposedSlot"] if prop else None,
            "mode": "peer",
        }

    def circle_view(self, c: dict, viewer: dict) -> dict:
        my_hours = set(viewer.get("availability") or [])
        members, details = [], []
        for uid in c["memberUids"]:
            u = self.store.get("users", uid) or {}
            consent = u.get("consent") or {}
            is_you = uid == viewer["uid"]
            shows_name = bool(consent.get("shareNameWithCircle"))
            name = "You" if is_you else (u.get("name") if shows_name else None) or "Anonymous peer"
            members.append(name)
            details.append({
                "name": name,
                "isYou": is_you,
                "email": u.get("email") if (is_you or consent.get("shareContact")) else None,
                "programme": u.get("programme") if (is_you or shows_name) else None,
                # Free hours this member has in common with the person looking at the circle.
                "sharedHours": []
                if is_you
                else [sched.slot_label(s) for s in (u.get("availability") or []) if s in my_hours][:3],
            })
        tiers = [(self.store.get("stamps", f"{u}_{c['conceptId']}") or {}).get("tier") for u in c["memberUids"]]
        meet_live = bool(c.get("meetLive")) and bool(gws.clean_meet_link(c.get("meetUrl")))
        meet_url = gws.clean_meet_link(c.get("meetUrl")) if meet_live else None
        messages = list(c.get("messages") or [])
        slot = c.get("proposedSlot")
        return {
            "id": c["id"],
            "conceptId": c["conceptId"],
            "conceptName": self.cat.name(c["conceptId"]),
            "moduleName": (self.cat.concepts.get(c["conceptId"]) or {}).get("area"),
            "stampsCompleted": sum(1 for t in tiers if t),
            "stampsVerified": sum(1 for t in tiers if t),
            "status": c["status"],
            "proposedSlot": slot,
            "slotLabel": sched.slot_label(slot) if slot else "Time to be agreed in the chat",
            "slotAgreed": bool(slot),
            "viewerFreeAtSlot": bool(slot) and slot in my_hours,
            "memberCount": len(c["memberUids"]),
            "members": members,
            "memberDetails": details,
            "mode": "peer",
            "meetUrl": meet_url,
            "meetLive": meet_live,
            "meetNewUrl": gws.MEET_NEW_URL,
            "messages": messages,
            "isMember": viewer["uid"] in c["memberUids"],
            "note": c.get("note"),
            "synthetic": c.get("synthetic", False),
        }

    def _open_circle_for(self, concept: str, user: dict) -> dict | None:
        """An active circle on this gap that still has room. Circles of real accounts come first,
        then circles that meet in one of the student's free hours."""
        my_hours = set(user.get("availability") or [])
        open_circles = [c for c in self._active_circles(concept) if len(c["memberUids"]) < config.MAX_GROUP_SIZE]
        if not open_circles:
            return None
        return sorted(
            open_circles,
            key=lambda c: (bool(c.get("synthetic")), c.get("proposedSlot") not in my_hours, c.get("createdAt") or ""),
        )[0]

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
        existing = self._open_circle_for(concept, user)
        if existing:
            return base | {"status": "existing", "circle": self.circle_view(existing, user)}
        prop = self._propose_members(concept, user)
        if not prop:
            return base | {
                "status": "not-enough",
                "peersWithGap": 0,
                "message": (
                    "No other opted-in student has this gap yet. See the suggested study partners on the "
                    "Study circles page, or check back later."
                ),
            }
        fake = {"id": "proposal", "status": "proposal", "meetUrl": None, "meetLive": False, "messages": [], **prop}
        return base | {"status": "proposal", "circle": self.circle_view(fake, user)}

    def _add_member(self, user: dict, c: dict) -> dict:
        user["consent"]["joinCircles"] = True
        self.store.put("users", user["uid"], user)
        c["memberUids"].append(user["uid"])
        c.setdefault("messages", []).append({
            "id": "msg-" + uuid.uuid4().hex[:8],
            "sender": "Study Circle",
            "text": f"{user.get('name') or 'A student'} joined the circle.",
            "createdAt": _iso(),
        })
        self.store.put("studyCircles", c["id"], c)
        self._sync_circle_to_all_members(c)
        return self.circle_view(c, user)

    def join_circle_by_id(self, user: dict, circle_id: str) -> dict:
        """Join one specific open circle (used by the open circles list)."""
        c = self.store.get("studyCircles", circle_id)
        if not c or c.get("status") == "done":
            raise ServiceError(404, "Circle not found.")
        if user["uid"] in c["memberUids"]:
            return self.circle_view(c, user)
        if len(c["memberUids"]) >= config.MAX_GROUP_SIZE:
            raise ServiceError(409, "That circle is full. Pick another one.")
        return self._add_member(user, c)

    def join_circle(self, user: dict, concept: str) -> dict:
        sug = self.circle_suggestion(user, concept)
        if sug["status"] == "member":
            return sug["circle"]
        if sug["status"] == "existing":
            return self._add_member(user, self.store.get("studyCircles", sug["circle"]["id"]))
        if sug["status"] != "proposal":
            raise ServiceError(409, sug.get("message") or "No circle can be formed right now.")
        user["consent"]["joinCircles"] = True
        self.store.put("users", user["uid"], user)
        prop = self._propose_members(concept, user)
        cid = "c-" + uuid.uuid4().hex[:10]
        slot = prop["proposedSlot"]
        when = (
            f"Suggested time: {sched.slot_label(slot)}, a free hour you share."
            if slot
            else "You have no free hour in common yet, so agree a time here."
        )
        c = {
            "id": cid,
            "courseId": self.cat.course["id"],
            "conceptId": concept,
            "memberUids": prop["memberUids"],
            "status": "scheduled",
            "proposedSlot": slot,
            "mode": "peer",
            "meetUrl": None,
            "meetLive": False,
            "messages": [
                {
                    "id": "msg-" + uuid.uuid4().hex[:8],
                    "sender": "Study Circle",
                    "text": (
                        f"Peer circle created for {self.cat.name(concept)}. {when} "
                        "Start a Google Meet room and paste the link above, or discuss here."
                    ),
                    "createdAt": _iso(),
                }
            ],
            "createdAt": _iso(),
        }
        self.store.put("studyCircles", cid, c)
        self._sync_circle_to_all_members(c)
        log.info("circle %s created for %s with %d members", cid, concept, len(c["memberUids"]))
        return self.circle_view(c, user)

    def peer_suggestions(self, user: dict) -> dict:
        """People to study with: every opted-in student, ranked by what they have in common with you.

        Common gaps count most, then common modules, then a shared free hour. A shared hour is a
        bonus shown on the card, never a requirement, so a brand-new account still sees suggestions.
        """
        me = user["uid"]
        my_gaps = self._user_gaps(me)
        my_mods = self._user_modules(user)
        my_hours = set(user.get("availability") or [])
        mod_name = {m["id"]: m["name"] for m in self.cat.modules}
        mod_order = {m["id"]: i for i, m in enumerate(self.cat.modules)}

        def named(ids: list[str]) -> list[dict]:
            return [{"id": c, "name": self.cat.name(c)} for c in ids]

        def mod_names(ids) -> list[str]:
            return [mod_name[m] for m in sorted(ids, key=lambda m: mod_order.get(m, 99)) if m in mod_name]

        my_circles = self.store.list("studyCircles", lambda c: c["status"] != "done" and me in c["memberUids"])
        peers = []
        for u in self.store.list(
            "users", lambda u: u["role"] == "student" and not u.get("synthetic") and u["uid"] != me
        ):
            consent = u.get("consent") or {}
            if not consent.get("joinCircles"):
                continue
            gaps = self._user_gaps(u["uid"])
            mods = self._user_modules(u)
            common_gaps = [g for g in gaps if g in my_gaps]
            common_mods = mods & my_mods
            shared = [s for s in (u.get("availability") or []) if s in my_hours]
            shows_name = bool(consent.get("shareNameWithCircle"))
            peers.append({
                "uid": u["uid"],
                "name": u["name"] if shows_name else "Anonymous peer",
                "email": u.get("email") if consent.get("shareContact") else None,
                "programme": u.get("programme") if shows_name else None,
                "year": u.get("year") if shows_name else None,
                "university": u.get("university") if shows_name else None,
                "gaps": named(gaps[:4]),
                "commonGaps": named(common_gaps[:4]),
                "modules": mod_names(mods),
                "commonModules": mod_names(common_mods),
                "sharedHours": [sched.slot_label(s) for s in shared[:4]],
                "inCircleWithYou": any(u["uid"] in c["memberUids"] for c in my_circles),
                "score": 3 * len(common_gaps) + len(common_mods) + (1 if shared else 0),
            })
        peers.sort(key=lambda p: (-p["score"], p["name"]))

        ranked = []
        for c in self._active_circles():
            if me in c["memberUids"] or len(c["memberUids"]) >= config.MAX_GROUP_SIZE:
                continue
            module = (self.cat.concepts.get(c["conceptId"]) or {}).get("moduleId")
            reason = "common-gap" if c["conceptId"] in my_gaps else "common-module" if module in my_mods else None
            ranked.append(({"common-gap": 0, "common-module": 1}.get(reason, 2), bool(c.get("synthetic")), c, reason))
        ranked.sort(key=lambda t: (t[0], t[1], t[2].get("createdAt") or ""))
        consent = user.get("consent") or {}
        return {
            "me": {
                "gaps": named(my_gaps[:6]),
                "modules": mod_names(my_mods),
                "optedIn": bool(consent.get("joinCircles")),
                "showsName": bool(consent.get("shareNameWithCircle")),
                "sharesContact": bool(consent.get("shareContact")),
            },
            "peers": peers[:12],
            "openCircles": [dict(self.circle_view(c, user), reason=reason) for _, _, c, reason in ranked[:6]],
        }

    def _sync_circle_to_workspace(self, user: dict, circle: dict) -> None:
        ws = gws.ensure_workspace(user)
        concept_name = self.cat.name(circle["conceptId"])
        meet_live = bool(circle.get("meetLive")) and bool(gws.clean_meet_link(circle.get("meetUrl")))
        meet_url = gws.clean_meet_link(circle.get("meetUrl")) if meet_live else None
        existing_space = next((s for s in ws["chatSpaces"] if s.get("circleId") == circle["id"]), None)
        if existing_space:
            existing_space["meetUrl"] = meet_url
            existing_space["meetLive"] = meet_live
            existing_space["messages"] = list(circle.get("messages") or [])
        else:
            ws["chatSpaces"].insert(
                0,
                {
                    "id": "gchat-" + circle["id"],
                    "name": f"Study Circle · {concept_name}",
                    "conceptId": circle["conceptId"],
                    "circleId": circle["id"],
                    "meetUrl": meet_url,
                    "meetLive": meet_live,
                    "messages": list(circle.get("messages") or []),
                    "createdAt": _iso(),
                },
            )
        self.store.put("users", user["uid"], user)

    def _sync_circle_to_all_members(self, circle: dict) -> None:
        for uid in circle.get("memberUids") or []:
            u = self.store.get("users", uid)
            if u and not u.get("synthetic"):
                self._sync_circle_to_workspace(u, circle)

    def my_circles(self, user: dict) -> list[dict]:
        return [
            self.circle_view(c, user)
            for c in self.store.list("studyCircles", lambda c: user["uid"] in c["memberUids"])
        ]

    def circle_done(self, user: dict, circle_id: str) -> dict:
        c = self.store.get("studyCircles", circle_id)
        if not c or user["uid"] not in c["memberUids"]:
            raise ServiceError(404, "Circle not found.")
        c["status"] = "done"
        self.store.put("studyCircles", circle_id, c)
        return self.circle_view(c, user)

    def circle_set_meet(self, user: dict, circle_id: str, meet_url: str) -> dict:
        c = self.store.get("studyCircles", circle_id)
        if not c or user["uid"] not in c["memberUids"]:
            raise ServiceError(404, "Circle not found.")
        clean = gws.clean_meet_link(meet_url)
        if not clean:
            raise ServiceError(
                400,
                "Paste a valid Google Meet link (for example https://meet.google.com/abc-defg-hij).",
            )
        c["meetUrl"] = clean
        c["meetLive"] = True
        msg = {
            "id": "msg-" + uuid.uuid4().hex[:8],
            "sender": user.get("name") or "Student",
            "text": f"Shared Google Meet room for the circle: {clean}",
            "createdAt": _iso(),
        }
        c.setdefault("messages", []).append(msg)
        self.store.put("studyCircles", circle_id, c)
        self._sync_circle_to_all_members(c)
        return self.circle_view(c, user)

    def circle_chat_post(self, user: dict, circle_id: str, text: str) -> dict:
        c = self.store.get("studyCircles", circle_id)
        if not c or user["uid"] not in c["memberUids"]:
            raise ServiceError(404, "Circle not found.")
        msg_text = (text or "").strip()
        if not msg_text:
            raise ServiceError(400, "Enter a message to post to the study circle chat.")
        msg = {
            "id": "msg-" + uuid.uuid4().hex[:8],
            "sender": user.get("name") or "Student",
            "text": msg_text[:1000],
            "createdAt": _iso(),
        }
        c.setdefault("messages", []).append(msg)
        self.store.put("studyCircles", circle_id, c)
        self._sync_circle_to_all_members(c)
        return self.circle_view(c, user)

    @staticmethod
    def _local_tz():
        """The campus time zone (PUNCA_TIMEZONE). Falls back to UTC+8 when tz data is not installed."""
        try:
            from zoneinfo import ZoneInfo

            return ZoneInfo(config.PUNCA_TIMEZONE)
        except Exception:
            return timezone(timedelta(hours=8))

    @classmethod
    def _next_slot_start(cls, slot: str | None) -> datetime:
        """Next occurrence of a weekly slot such as 'Tue-14', in campus local time.

        A circle with no agreed slot gets tomorrow at the next full hour as a placeholder.
        """
        now = datetime.now(cls._local_tz())
        day_map = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
        try:
            d_str, h_str = (slot or "").split("-")
            days_ahead = (day_map[d_str] - now.weekday()) % 7 or 7
            return (now + timedelta(days=days_ahead)).replace(hour=int(h_str), minute=0, second=0, microsecond=0)
        except (ValueError, KeyError):
            return (now + timedelta(days=1, hours=1)).replace(minute=0, second=0, microsecond=0)

    def circle_schedule_calendar(self, user: dict, circle_id: str) -> dict:
        c = self.store.get("studyCircles", circle_id)
        if not c or user["uid"] not in c["memberUids"]:
            raise ServiceError(404, "Circle not found.")
        ws = gws.ensure_workspace(user)
        concept_name = self.cat.name(c["conceptId"])
        slot_lbl = sched.slot_label(c["proposedSlot"]) if c.get("proposedSlot") else "time to be agreed"
        start_dt = self._next_slot_start(c["proposedSlot"])
        start_iso = _iso(start_dt)
        end_iso = _iso(start_dt + timedelta(hours=1))
        existing_meet = gws.clean_meet_link(c.get("meetUrl")) if c.get("meetLive") else None
        desc = f"Peer group study session for {concept_name}."
        if existing_meet:
            desc += f" Meet room: {existing_meet}"
        created = self.google_calendar_create(
            user,
            {
                "title": f"Peer Study Circle: {concept_name} ({slot_lbl})",
                "description": desc,
                "startTime": start_iso,
                "endTime": end_iso,
                "location": "Google Meet",
                "includeMeet": True,
                "meetUrl": existing_meet,
                "conceptId": c["conceptId"],
                "circleId": c["id"],
                "attendees": [ws.get("email") or user.get("email")] if (ws.get("email") or user.get("email")) else [],
            },
        )
        ev = created["event"]
        if ev.get("meetUrl") and gws.clean_meet_link(ev["meetUrl"]):
            c["meetUrl"] = gws.clean_meet_link(ev["meetUrl"])
            c["meetLive"] = True
            self.store.put("studyCircles", circle_id, c)
            self._sync_circle_to_all_members(c)
        return {"event": ev, "warning": created.get("warning"), "circle": self.circle_view(c, user)}

    # ================================================================== Google Workspace ====
    def _is_live(self, user: dict) -> bool:
        ws = user.get("googleWorkspace") or {}
        return bool(ws.get("connected", True) and self.live and self.live.is_live(user["uid"]))

    def _mirror(self, fn) -> tuple[dict | None, str | None]:
        """Run a live Google call; return (result, None) or (None, warning_message)."""
        try:
            return fn(), None
        except GoogleLiveError as exc:
            log.warning("live Google call failed: %s", exc.message)
            return None, exc.message

    def google_connect(self, user: dict, access_token: str, expires_in: int | None = None) -> dict:
        ws = gws.ensure_workspace(user)
        try:
            info = self.live.connect(user["uid"], access_token, expires_in)
        except GoogleLiveError as exc:
            raise ServiceError(exc.status, exc.message) from exc
        ws["connected"] = True
        ws["email"] = info["email"]
        ws["mode"] = "oauth-live"
        ws["connectedAt"] = _iso()
        user["googleWorkspace"] = ws
        self.store.put("users", user["uid"], user)
        return self.google_status(user)

    def google_disconnect(self, user: dict) -> dict:
        ws = gws.ensure_workspace(user)
        self.live.disconnect(user["uid"])
        ws["mode"] = "workspace"
        user["googleWorkspace"] = ws
        self.store.put("users", user["uid"], user)
        return self.google_status(user)

    def google_status(self, user: dict) -> dict:
        ws = gws.ensure_workspace(user)
        # Keep study-circle chat spaces synced with the latest shared circle state
        for c in self.store.list("studyCircles", lambda c: user["uid"] in c["memberUids"]):
            self._sync_circle_to_workspace(user, c)
        ws = user["googleWorkspace"]
        live_session = self.live.session(user["uid"]) if self.live else None
        if not live_session and ws.get("mode") == "oauth-live":
            ws["mode"] = "workspace"
        # Every session gets an "Add to Google Calendar" link, including ones saved before the
        # link existed.
        for ev in ws.get("calendarEvents") or []:
            if not ev.get("calendarLink") and ev.get("title") and ev.get("startTime"):
                ev["calendarLink"] = gws.calendar_template_link(
                    ev["title"],
                    ev.get("description") or "",
                    ev["startTime"],
                    ev.get("endTime") or gws.one_hour_after(ev["startTime"]),
                    config.PUNCA_TIMEZONE,
                )
        self.store.put("users", user["uid"], user)
        return {
            "connected": bool(ws.get("connected", True)),
            "email": (live_session or {}).get("email") or ws.get("email") or user.get("email"),
            "accountEmail": user.get("email"),
            "mode": "oauth-live" if live_session else "workspace",
            "liveConnected": bool(live_session),
            "liveExpiresAt": live_session["expiresAt"] if live_session else None,
            "liveAvailable": bool(config.GOOGLE_OAUTH_CLIENT_ID),
            "oauthClientId": config.GOOGLE_OAUTH_CLIENT_ID or None,
            "oauthScopes": list(GOOGLE_SCOPES),
            "meetNewUrl": gws.MEET_NEW_URL,
            "connectedAt": ws.get("connectedAt"),
            "enabledServices": ws.get("enabledServices", {}),
            "preferences": ws.get("preferences", {}),
            "calendarEvents": ws.get("calendarEvents", []),
            "tasks": ws.get("tasks", []),
            "docs": ws.get("docs", []),
            "chatSpaces": ws.get("chatSpaces", []),
        }

    def google_configure(self, user: dict, data: dict) -> dict:
        ws = gws.ensure_workspace(user)
        if "connected" in data and data["connected"] is not None:
            ws["connected"] = bool(data["connected"])
            if not ws["connected"]:
                self.live.disconnect(user["uid"])
                ws["mode"] = "workspace"
        if data.get("email"):
            ws["email"] = data["email"].strip()
        if data.get("accessToken"):
            return self.google_connect(user, data["accessToken"], data.get("expiresIn"))
        if isinstance(data.get("enabledServices"), dict):
            for k in gws.SERVICES:
                if k in data["enabledServices"]:
                    ws["enabledServices"][k] = bool(data["enabledServices"][k])
        if isinstance(data.get("preferences"), dict):
            for k in ("defaultReminderMinutes", "autoCreateMeetForCircles", "autoSyncTasksFromDiagnosis"):
                if k in data["preferences"] and data["preferences"][k] is not None:
                    ws["preferences"][k] = data["preferences"][k]
        user["googleWorkspace"] = ws
        self.store.put("users", user["uid"], user)
        return self.google_status(user)

    def _require_live(self, user: dict, what: str) -> None:
        if not self._is_live(user):
            raise ServiceError(409, f"Connect your Google account to {what}.")

    def google_calendar_create(self, user: dict, data: dict) -> dict:
        ws = gws.ensure_workspace(user)
        try:
            gws._require_service(ws, "calendar")
        except gws.WorkspaceError as exc:
            raise ServiceError(exc.status, exc.message) from exc
        title = (data.get("title") or "").strip()
        if not title:
            raise ServiceError(400, "Enter a title for the Google Calendar study session or meeting.")
        start_time = (data.get("startTime") or "").strip() or _iso(_now() + timedelta(days=1))
        end_time = (data.get("endTime") or "").strip() or gws.one_hour_after(start_time)
        s_dt, e_dt = gws.parse_time(start_time), gws.parse_time(end_time)
        if s_dt and e_dt and e_dt <= s_dt:
            end_time = gws.one_hour_after(start_time)
        description = (data.get("description") or "").strip()[:800]
        include_meet = bool(data.get("includeMeet", True))
        typed_attendees = [
            a.strip() for a in (data.get("attendees") or []) if isinstance(a, str) and auth.valid_email(a.strip())
        ]
        own_email = ws.get("email") or user.get("email")
        attendees = list(typed_attendees)
        if own_email and own_email not in attendees:
            attendees.insert(0, own_email)

        warning = None
        live_res = None
        if self._is_live(user):
            reminder = ws.get("preferences", {}).get("defaultReminderMinutes", 30)
            live_res, warning = self._mirror(
                lambda: self.live.calendar_insert(
                    user["uid"],
                    title[:140],
                    description,
                    start_time,
                    end_time,
                    config.PUNCA_TIMEZONE,
                    typed_attendees,
                    include_meet,
                    reminder,
                )
            )
        meet_url = (live_res or {}).get("meetUrl") or gws.clean_meet_link(data.get("meetUrl"))
        # The student saves the event in their own calendar, so they are not listed as a guest.
        guests = [a for a in typed_attendees if a.lower() != (own_email or "").lower()]
        cal_link = (live_res or {}).get("htmlLink") or gws.calendar_template_link(
            title[:140], description, start_time, end_time, config.PUNCA_TIMEZONE, guests, meet_url
        )
        ev = {
            "id": "gcal-" + uuid.uuid4().hex[:8],
            "googleId": (live_res or {}).get("id"),
            "title": title[:140],
            "description": description,
            "startTime": start_time,
            "endTime": end_time,
            "location": "Google Meet" if (include_meet or meet_url) else (data.get("location") or "Study Room"),
            "meetUrl": meet_url,
            "meetLive": bool(meet_url),
            "calendarLink": cal_link,
            "live": bool(live_res),
            "conceptId": data.get("conceptId"),
            "circleId": data.get("circleId"),
            "attendees": attendees,
            "createdAt": _iso(),
        }
        ws["calendarEvents"].insert(0, ev)
        self.store.put("users", user["uid"], user)
        return {"event": ev, "warning": warning, "workspace": self.google_status(user)}

    def google_calendar_delete(self, user: dict, event_id: str) -> dict:
        ws = gws.ensure_workspace(user)
        target = next((e for e in ws.get("calendarEvents", []) if e["id"] == event_id), None)
        if target and target.get("live") and target.get("googleId") and self._is_live(user):
            self._mirror(lambda: self.live.calendar_delete(user["uid"], target["googleId"]))
        ws["calendarEvents"] = [e for e in ws.get("calendarEvents", []) if e["id"] != event_id]
        self.store.put("users", user["uid"], user)
        return self.google_status(user)

    def google_tasks_create(self, user: dict, data: dict) -> dict:
        ws = gws.ensure_workspace(user)
        try:
            gws._require_service(ws, "tasks")
        except gws.WorkspaceError as exc:
            raise ServiceError(exc.status, exc.message) from exc
        title = (data.get("title") or "").strip()
        if not title:
            raise ServiceError(400, "Enter a task title.")
        notes = (data.get("notes") or "").strip()[:600]
        due = (data.get("due") or (_now() + timedelta(days=2)).date().isoformat())[:10]
        task = {
            "id": "gtask-" + uuid.uuid4().hex[:8],
            "title": title[:200],
            "notes": notes,
            "due": due,
            "completed": False,
            "completedAt": None,
            "conceptId": data.get("conceptId"),
            "diagnosisId": data.get("diagnosisId"),
            "createdAt": _iso(),
        }
        ws["tasks"].insert(0, task)
        self.store.put("users", user["uid"], user)
        return {"task": task, "workspace": self.google_status(user)}

    def google_tasks_update(self, user: dict, task_id: str, data: dict) -> dict:
        ws = gws.ensure_workspace(user)
        target = next((t for t in ws.get("tasks", []) if t["id"] == task_id), None)
        if not target:
            raise ServiceError(404, "Task not found.")
        if "completed" in data and data["completed"] is not None:
            target["completed"] = bool(data["completed"])
            target["completedAt"] = _iso() if target["completed"] else None
        if data.get("title"):
            target["title"] = data["title"].strip()[:200]
        if "notes" in data and data["notes"] is not None:
            target["notes"] = data["notes"].strip()[:600]
        if "due" in data and data["due"] is not None:
            target["due"] = data["due"][:10]
        self.store.put("users", user["uid"], user)
        return {"task": target, "workspace": self.google_status(user)}

    def google_calendar_sync(self, user: dict, event_id: str) -> dict:
        """Put a session that only exists in Punca into the student's real Google Calendar."""
        ws = gws.ensure_workspace(user)
        ev = next((e for e in ws.get("calendarEvents") or [] if e["id"] == event_id), None)
        if not ev:
            raise ServiceError(404, "Session not found.")
        self._require_live(user, "add sessions straight to Google Calendar")
        if not (ev.get("live") and ev.get("googleId")):
            own = (ws.get("email") or user.get("email") or "").lower()
            guests = [a for a in ev.get("attendees") or [] if auth.valid_email(a) and a.lower() != own]
            end = ev.get("endTime") or gws.one_hour_after(ev["startTime"])
            wants_meet = not ev.get("meetUrl")
            description = ev.get("description") or ""
            if ev.get("meetUrl") and ev["meetUrl"] not in description:
                description = f"{description} Meet room: {ev['meetUrl']}".strip()
            res, warning = self._mirror(
                lambda: self.live.calendar_insert(
                    user["uid"], ev["title"], description, ev["startTime"], end, config.PUNCA_TIMEZONE,
                    guests, wants_meet, ws.get("preferences", {}).get("defaultReminderMinutes", 30),
                )
            )
            if not res or not res.get("id"):
                raise ServiceError(502, warning or "Google Calendar did not accept the session.")
            ev.update(googleId=res["id"], live=True, calendarLink=res.get("htmlLink") or ev.get("calendarLink"))
            if res.get("meetUrl") and not ev.get("meetUrl"):
                ev.update(meetUrl=res["meetUrl"], meetLive=True)
            self.store.put("users", user["uid"], user)
        return {"event": ev, "workspace": self.google_status(user)}

    def google_tasks_delete(self, user: dict, task_id: str) -> dict:
        ws = gws.ensure_workspace(user)
        ws["tasks"] = [t for t in ws.get("tasks", []) if t["id"] != task_id]
        self.store.put("users", user["uid"], user)
        return self.google_status(user)

    def google_tasks_from_diagnosis(self, user: dict, did: str) -> dict:
        doc = self._own_diagnosis(user["uid"], did)
        ws = gws.ensure_workspace(user)
        try:
            gws._require_service(ws, "tasks")
        except gws.WorkspaceError as exc:
            raise ServiceError(exc.status, exc.message) from exc
        path = doc.get("path") or [doc["targetConceptId"]]
        created: list[dict] = []
        for idx, cid in enumerate(path):
            cname = self.cat.name(cid)
            title = f"Step {idx + 1}: Review & pass re-check for {cname}"
            notes = f"From diagnosis on {self.cat.name(doc['targetConceptId'])}. Complete your Passport stamp for {cname}."
            due = (_now() + timedelta(days=idx + 1)).date().isoformat()
            task = {
                "id": "gtask-" + uuid.uuid4().hex[:8],
                "title": title,
                "notes": notes,
                "due": due,
                "completed": False,
                "completedAt": None,
                "conceptId": cid,
                "diagnosisId": did,
                "createdAt": _iso(),
            }
            ws["tasks"].insert(0, task)
            created.append(task)
        self.store.put("users", user["uid"], user)
        return {"created": created, "workspace": self.google_status(user)}

    def google_docs_create(self, user: dict, data: dict) -> dict:
        ws = gws.ensure_workspace(user)
        try:
            gws._require_service(ws, "docs")
        except gws.WorkspaceError as exc:
            raise ServiceError(exc.status, exc.message) from exc
        title = (data.get("title") or "").strip()
        if not title:
            raise ServiceError(400, "Enter a title for the Google Doc.")
        content = (data.get("content") or "").strip()[:20000]
        folder = gws.DOCS_FOLDER
        warning = None
        live_res = None
        if self._is_live(user):
            live_res, warning = self._mirror(
                lambda: self.live.doc_create(user["uid"], title[:160], content, folder)
            )
        now_iso = _iso()
        gdoc = {
            "id": "gdoc-" + uuid.uuid4().hex[:8],
            "googleId": (live_res or {}).get("id"),
            "title": title[:160],
            "conceptId": data.get("conceptId"),
            "content": content,
            "url": (live_res or {}).get("webViewLink"),
            "live": bool(live_res),
            "updatedAt": now_iso,
            "createdAt": now_iso,
        }
        ws["docs"].insert(0, gdoc)
        self.store.put("users", user["uid"], user)
        return {"doc": gdoc, "warning": warning, "workspace": self.google_status(user)}

    def google_docs_update(self, user: dict, doc_id: str, data: dict) -> dict:
        ws = gws.ensure_workspace(user)
        target = next((d for d in ws.get("docs", []) if d["id"] == doc_id), None)
        if not target:
            raise ServiceError(404, "Google Doc not found.")
        if data.get("title"):
            target["title"] = data["title"].strip()[:160]
        if "content" in data and data["content"] is not None:
            target["content"] = data["content"][:20000]
        target["updatedAt"] = _iso()
        warning = None
        if target.get("live") and target.get("googleId") and self._is_live(user):
            _, warning = self._mirror(
                lambda: self.live.doc_update(
                    user["uid"],
                    target["googleId"],
                    target["title"] if data.get("title") else None,
                    target["content"] if "content" in data else None,
                )
            )
        self.store.put("users", user["uid"], user)
        return {"doc": target, "warning": warning, "workspace": self.google_status(user)}

    def google_docs_delete(self, user: dict, doc_id: str) -> dict:
        ws = gws.ensure_workspace(user)
        target = next((d for d in ws.get("docs", []) if d["id"] == doc_id), None)
        if target and target.get("live") and target.get("googleId") and self._is_live(user):
            self._mirror(lambda: self.live.drive_trash(user["uid"], target["googleId"]))
        ws["docs"] = [d for d in ws.get("docs", []) if d["id"] != doc_id]
        self.store.put("users", user["uid"], user)
        return self.google_status(user)

    def google_docs_from_diagnosis(self, user: dict, did: str) -> dict:
        doc = self._own_diagnosis(user["uid"], did)
        rem = self.remediation(user["uid"], did)
        ws = gws.ensure_workspace(user)
        try:
            gws._require_service(ws, "docs")
        except gws.WorkspaceError as exc:
            raise ServiceError(exc.status, exc.message) from exc
        root_name = self.cat.name(doc.get("rootCauseConceptId")) or "Foundation"
        target_name = self.cat.name(doc.get("targetConceptId"))
        route_str = " → ".join(self.cat.name(c) for c in (doc.get("path") or []))
        points = "\n".join(f"- {kp}" for kp in (rem.get("keyPoints") or []))
        content = (
            f"# Study Notes: {root_name} (for {target_name})\n\n"
            f"**Original Question / Lab Brief:** {doc.get('stuckInput')}\n\n"
            f"**Remediation Route:** {route_str}\n\n"
            f"## Core Explanation\n{rem.get('explanation', '')}\n\n"
            f"## Key Takeaways\n{points}\n"
        )
        title = f"Punca Notes · {root_name} → {target_name}"
        folder = gws.DOCS_FOLDER
        warning = None
        live_res = None
        if self._is_live(user):
            live_res, warning = self._mirror(lambda: self.live.doc_create(user["uid"], title, content, folder))
        now_iso = _iso()
        gdoc = {
            "id": "gdoc-" + uuid.uuid4().hex[:8],
            "googleId": (live_res or {}).get("id"),
            "title": title,
            "conceptId": doc.get("rootCauseConceptId"),
            "diagnosisId": did,
            "content": content,
            "url": (live_res or {}).get("webViewLink"),
            "live": bool(live_res),
            "updatedAt": now_iso,
            "createdAt": now_iso,
        }
        ws["docs"].insert(0, gdoc)
        self.store.put("users", user["uid"], user)
        return {"doc": gdoc, "warning": warning, "workspace": self.google_status(user)}

    def google_chat_create_space(self, user: dict, data: dict) -> dict:
        ws = gws.ensure_workspace(user)
        try:
            gws._require_service(ws, "chat")
        except gws.WorkspaceError as exc:
            raise ServiceError(exc.status, exc.message) from exc
        name = (data.get("name") or "").strip()
        if not name:
            raise ServiceError(400, "Enter a name for the peer chat space.")
        meet_url = gws.clean_meet_link(data.get("meetUrl"))
        space = {
            "id": "gchat-" + uuid.uuid4().hex[:8],
            "name": name[:120],
            "conceptId": data.get("conceptId"),
            "circleId": data.get("circleId"),
            "meetUrl": meet_url,
            "meetLive": bool(meet_url),
            "messages": [
                {
                    "id": "msg-" + uuid.uuid4().hex[:8],
                    "sender": user.get("name") or "Student",
                    "text": f"Created peer discussion space '{name}'. Start a Google Meet room anytime and share the link here.",
                    "createdAt": _iso(),
                }
            ],
            "createdAt": _iso(),
        }
        ws["chatSpaces"].insert(0, space)
        self.store.put("users", user["uid"], user)
        return {"space": space, "workspace": self.google_status(user)}

    def google_chat_post(self, user: dict, space_id: str, text: str) -> dict:
        ws = gws.ensure_workspace(user)
        try:
            gws._require_service(ws, "chat")
        except gws.WorkspaceError as exc:
            raise ServiceError(exc.status, exc.message) from exc
        space = next((s for s in ws.get("chatSpaces", []) if s["id"] == space_id), None)
        if not space:
            raise ServiceError(404, "Chat space not found.")
        msg_text = (text or "").strip()
        if not msg_text:
            raise ServiceError(400, "Enter a message.")
        if space.get("circleId"):
            c = self.store.get("studyCircles", space["circleId"])
            if c and user["uid"] in c["memberUids"]:
                self.circle_chat_post(user, c["id"], msg_text)
                ws = user["googleWorkspace"]
                space = next((s for s in ws.get("chatSpaces", []) if s["id"] == space_id), space)
                return {"space": space, "workspace": self.google_status(user)}
        msg = {
            "id": "msg-" + uuid.uuid4().hex[:8],
            "sender": user.get("name") or "Student",
            "text": msg_text[:1000],
            "createdAt": _iso(),
        }
        space.setdefault("messages", []).append(msg)
        self.store.put("users", user["uid"], user)
        return {"space": space, "workspace": self.google_status(user)}


def _label(tag: str | None) -> str | None:
    return tag.replace("-", " ").capitalize() if tag else None
