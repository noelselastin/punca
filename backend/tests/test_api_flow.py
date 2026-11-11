import base64
from concurrent.futures import ThreadPoolExecutor

import pytest

import config
from store.seed import DEMO_PASSWORD, DEMO_STUDENT_EMAIL
from store.local_store import LocalStore

from conftest import answer_as


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def signup(client, email="new.student@gmail.com", **extra):
    body = {
        "name": "New Student",
        "email": email,
        "password": "correct-horse-1",
        "confirmPassword": "correct-horse-1",
        "university": "Example University",
        "studentId": email.split("@")[0].replace(".", ""),
        "programme": "BSc Computer Science",
        **extra,
    }
    return client.post("/api/auth/signup", json=body)


# ---- accounts ----------------------------------------------------------------------------------
def test_student_signup_login_and_me(client):
    r = signup(client, programme=" BSc CS ", year=2, university=" Example University ", studentId=" tp12345 ")
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == "student"
    assert "passwordHash" not in r.json()["user"]
    assert "confirmPassword" not in r.json()["user"]
    r = client.post("/api/auth/login", json={"email": "NEW.student@gmail.com", "password": "correct-horse-1"})
    assert r.status_code == 200
    me = client.get("/api/me", headers=auth(r.json()["token"]))
    assert me.json()["name"] == "New Student" and me.json()["year"] == 2
    assert me.json()["university"] == "Example University"
    assert me.json()["studentId"] == "TP12345"
    assert me.json()["programme"] == "BSc CS"
    passport = client.get("/api/me/passport", headers=auth(r.json()["token"])).json()
    assert passport["studentId"] == "TP12345" and passport["university"] == "Example University"
    assert passport["holderNo"] == "TP12345"
    assert len(passport["regions"]) == 6
    stored = LocalStore(client.svc.store.path).get("users", me.json()["uid"])
    assert stored["studentId"] == "TP12345"
    assert not {"password", "confirmPassword"} & stored.keys()


def test_signup_accepts_any_personal_email(client):
    r = signup(client, email="student@outlook.com", studentId="TP99999")
    assert r.status_code == 200, r.text
    bad = signup(client, email="not-an-email", studentId="TP99998")
    assert bad.status_code == 400
    assert "valid personal email" in bad.json()["error"].lower()


@pytest.mark.parametrize("field,value", [
    ("university", " "), ("university", "U" * 121), ("studentId", ""),
    ("studentId", "TP 123"), ("studentId", "T" * 41), ("programme", " "),
    ("programme", "C" * 81), ("confirmPassword", "different-password"),
    ("confirmPassword", ""),
])
def test_signup_requires_valid_student_details(client, field, value):
    before = len(client.svc.store.list("users"))
    response = signup(client, **{field: value})
    assert response.status_code == 400, response.text
    assert len(client.svc.store.list("users")) == before


def test_student_id_uniqueness_is_case_insensitive(client):
    assert signup(client, studentId="TP001").status_code == 200
    duplicate = signup(client, email="another@gmail.com", studentId=" tp001 ")
    assert duplicate.status_code == 409
    assert "student ID" in duplicate.json()["error"]
    assert signup(client, studentId="TP002").status_code == 409


def test_simultaneous_signups_cannot_reuse_a_student_id(client):
    def create(index):
        return signup(client, email=f"parallel{index}@gmail.com", studentId="TP-CONCURRENT").status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(create, [1, 2]))
    assert sorted(statuses) == [200, 409]
    assert len(client.svc.store.list("users", lambda u: u.get("studentId") == "TP-CONCURRENT")) == 1


def test_lecturer_and_moodle_routes_are_removed(client):
    tok = signup(client).json()["token"]
    assert client.get("/api/lecturer/overview", headers=auth(tok)).status_code == 404
    assert client.get("/api/moodle/status", headers=auth(tok)).status_code == 404


def test_signup_validation(client):
    assert signup(client, email="not-an-email").status_code == 400
    assert client.post("/api/auth/signup", json={"name": "X Y", "email": "a@gmail.com", "password": "short"}).status_code == 400
    assert signup(client).status_code == 200
    assert signup(client).status_code == 409  # duplicate email


def test_wrong_password_and_missing_token(client):
    signup(client)
    assert client.post("/api/auth/login", json={"email": "new.student@gmail.com", "password": "nope-nope"}).status_code == 401
    assert client.get("/api/me").status_code == 401


def test_logout_revokes_token(client):
    tok = signup(client).json()["token"]
    client.post("/api/auth/logout", headers=auth(tok))
    assert client.get("/api/me", headers=auth(tok)).status_code == 401


def test_demo_accounts_and_passport_reentry_states(client):
    res = client.get("/api/demo/accounts")
    assert res.status_code == 200
    accounts = res.json()["accounts"]
    assert len(accounts) == 7

    login_res = client.post("/api/auth/login", json={"email": "aisyah.student@demo.punca.edu", "password": DEMO_PASSWORD})
    assert login_res.status_code == 200
    tok = login_res.json()["token"]
    pp = client.get("/api/me/passport", headers=auth(tok)).json()
    assert pp["holderNo"] == "TP071204"
    assert pp["stampSummary"]["completed"] == 5
    assert pp["stampSummary"]["reentry"] == 1
    diff_c = next(c for r in pp["regions"] for c in r["concepts"] if c["conceptId"] == "CM-DERRULES")
    assert diff_c["state"] == "reentry"


# ---- full student flow (document foundation assessment, 5-10 probes, stamp, peer circle, Google Workspace) ----
def test_demo_flow_diagnose_with_file_stamp_and_peer_circle(client, catalog):
    stu = client.post("/api/auth/login", json={"email": DEMO_STUDENT_EMAIL, "password": DEMO_PASSWORD}).json()["token"]
    h = auth(stu)

    # Map stuck point with a document uploaded from PC
    doc_bytes = b"Lab 7 Calculus: Implement gradient descent by computing partial derivatives and applying the chain rule."
    m = client.post(
        "/api/map",
        json={
            "stuckInput": "Minimising a function with gradient descent and partial derivatives",
            "fileName": "Calculus_Gradient_Lab.txt",
            "fileBase64": base64.b64encode(doc_bytes).decode("ascii"),
        },
        headers=h,
    ).json()
    assert m["targetConceptId"] == "CM-GRADDESC"
    assert m["documentSummary"]["fileName"] == "Calculus_Gradient_Lab.txt"
    assert len(m["requiredFoundations"]) >= 3

    d = client.post(
        "/api/diagnoses",
        json={"stuckInput": "gradient descent", "targetConceptId": m["targetConceptId"], "mapping": m},
        headers=h,
    ).json()
    while d["status"] == "in_progress":
        p = d["pending"]
        r = client.post(
            f"/api/diagnoses/{d['id']}/answer",
            json={
                "probeId": p["probeId"],
                "choiceIndex": answer_as("CM-CHAIN", catalog, p),
                "confidence": "high",
            },
            headers=h,
        )
        assert r.status_code == 200, r.text
        d = r.json()["diagnosis"]
    assert d["result"]["rootCauseConceptId"] == "CM-CHAIN"
    assert config.MIN_PROBES <= d["probesAsked"] <= config.MAX_PROBES
    assert d["result"]["confidenceAssessment"]["total"] == d["probesAsked"]

    rem = client.get(f"/api/diagnoses/{d['id']}/remediation", headers=h).json()
    assert rem["found"] and rem["citations"][0]["sourceId"] == "cm.md#CM-CHAIN"
    assert len(rem["practice"]) == 3

    # Export remediation to Google Docs and to the study task list
    gdoc = client.post(f"/api/google/docs/from-diagnosis/{d['id']}", headers=h)
    assert gdoc.status_code == 200 and "CM-CHAIN" in gdoc.json()["doc"]["content"]
    gtasks = client.post(f"/api/google/tasks/from-diagnosis/{d['id']}", headers=h)
    assert gtasks.status_code == 200 and len(gtasks.json()["created"]) >= 2

    # Passport: the diagnosis alone never stamps; the gap shows as entry required.
    pp = client.get("/api/me/passport", headers=h).json()
    chain = next(c for r in pp["regions"] for c in r["concepts"] if c["conceptId"] == "CM-CHAIN")
    assert chain["state"] == "entry-required" and pp["stamps"] == 0
    assert pp["holderNo"] == pp["studentId"]
    assert pp["next"]["targetConceptId"] == "CM-GRADDESC"

    # Two passed re-checks: amber, then solid with a completed stamp.
    states = []
    for _ in range(2):
        q = client.post("/api/recheck", json={"conceptId": "CM-CHAIN"}, headers=h).json()
        a = client.post(
            "/api/recheck/answer",
            json={"probeId": q["probeId"], "choiceIndex": catalog.probes[q["probeId"]]["correctIndex"]},
            headers=h,
        ).json()
        states.append((a["status"], a["stampEarned"]))
    assert states == [("shaky", False), ("solid", True)]
    pp_after = client.get("/api/me/passport", headers=h).json()
    assert pp_after["stampSummary"]["completed"] == 1

    # Peer study circle with a circle chat, Google Meet and Google Calendar. The demo accounts
    # already have a chain rule circle with room, so that one is suggested.
    sug = client.get("/api/circles/suggestion", headers=h).json()
    assert sug["status"] == "existing" and sug["circle"]["mode"] == "peer"
    assert sug["circle"]["id"] == "c-demo-chain"
    circle = client.post("/api/circles/join", json={"conceptId": "CM-CHAIN"}, headers=h).json()
    assert circle["isMember"] and 3 <= circle["memberCount"] <= 6
    assert circle["meetNewUrl"] == "https://meet.google.com/new"

    meet_res = client.post(
        f"/api/circles/{circle['id']}/meet",
        json={"meetUrl": "https://meet.google.com/abc-defg-hij"},
        headers=h,
    )
    assert meet_res.status_code == 200
    assert meet_res.json()["meetUrl"] == "https://meet.google.com/abc-defg-hij"
    assert meet_res.json()["meetLive"] is True

    chat_res = client.post(f"/api/circles/{circle['id']}/chat", json={"text": "Let's review the chain rule together!"}, headers=h)
    assert chat_res.status_code == 200
    assert any("chain rule" in msg["text"] for msg in chat_res.json()["messages"])

    cal_res = client.post(f"/api/circles/{circle['id']}/calendar", headers=h)
    assert cal_res.status_code == 200
    assert cal_res.json()["event"]["meetUrl"] == "https://meet.google.com/abc-defg-hij"
    assert "calendar.google.com/calendar/render" in cal_res.json()["event"]["calendarLink"]


def test_passport_customisation_with_photo_and_custom_labs(client):
    tok = signup(client).json()["token"]
    me = client.get("/api/me", headers=auth(tok)).json()
    assert me["passportStyle"] is None
    sample_photo = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    body = {
        "passport": {
            "cover": "forest",
            "photoUrl": sample_photo,
            "displayName": "Nisha R.",
            "motto": "Own Calculus & SQL",
            "focusLabIds": ["T-CM7", "nope"],
            "customLabs": ["CS302 Distributed Systems Lab"],
        },
        "programme": "BSc Data Science",
        "year": 2,
    }
    r = client.patch("/api/me", json=body, headers=auth(tok))
    assert r.status_code == 200, r.text
    st = r.json()["passportStyle"]
    assert st["setupDone"] and st["cover"] == "forest" and st["focusLabIds"] == ["T-CM7"]
    assert st["photoUrl"] == sample_photo and st["customLabs"] == ["CS302 Distributed Systems Lab"]
    pp = client.get("/api/me/passport", headers=auth(tok)).json()
    assert pp["holder"] == "Nisha R."
    assert pp["style"]["photoUrl"] == sample_photo
    assert pp["focusLabs"] == ["CM · Calculus", "CS302 Distributed Systems Lab"]
    assert client.patch("/api/me", json={"passport": {"cover": "neon"}}, headers=auth(tok)).status_code == 400
    assert client.patch("/api/me", json={"passport": {"displayName": "X"}}, headers=auth(tok)).status_code == 400


def test_students_cannot_read_each_others_diagnoses(client):
    a = signup(client, email="a@gmail.com").json()["token"]
    b = signup(client, email="b@gmail.com").json()["token"]
    d = client.post("/api/diagnoses", json={"stuckInput": "SQL joins help", "targetConceptId": "DB-JOIN"}, headers=auth(a)).json()
    assert client.get(f"/api/diagnoses/{d['id']}", headers=auth(b)).status_code == 404
