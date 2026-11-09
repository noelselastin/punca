from store.seed import DEMO_LECTURER_EMAIL, DEMO_PASSWORD, DEMO_STUDENT_EMAIL

from conftest import answer_as


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def signup(client, email="new.student@example.edu", **extra):
    body = {"name": "New Student", "email": email, "password": "correct-horse-1", **extra}
    return client.post("/api/auth/signup", json=body)


# ---- accounts ----------------------------------------------------------------------------------
def test_student_signup_login_and_me(client):
    r = signup(client, programme="BSc CS", year=2)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["role"] == "student"
    assert "passwordHash" not in r.json()["user"]
    r = client.post("/api/auth/login", json={"email": "NEW.student@example.edu", "password": "correct-horse-1"})
    assert r.status_code == 200
    me = client.get("/api/me", headers=auth(r.json()["token"]))
    assert me.json()["name"] == "New Student" and me.json()["year"] == 2


def test_signup_cannot_create_a_lecturer(client):
    r = signup(client, role="lecturer")
    assert r.status_code == 200
    assert r.json()["user"]["role"] == "student"


def test_signup_validation(client):
    assert signup(client, email="not-an-email").status_code == 400
    assert client.post("/api/auth/signup", json={"name": "X Y", "email": "a@b.co", "password": "short"}).status_code == 400
    assert signup(client).status_code == 200
    assert signup(client).status_code == 409  # duplicate email


def test_wrong_password_and_missing_token(client):
    signup(client)
    assert client.post("/api/auth/login", json={"email": "new.student@example.edu", "password": "nope-nope"}).status_code == 401
    assert client.get("/api/me").status_code == 401


def test_logout_revokes_token(client):
    tok = signup(client).json()["token"]
    client.post("/api/auth/logout", headers=auth(tok))
    assert client.get("/api/me", headers=auth(tok)).status_code == 401


def test_student_cannot_open_lecturer_dashboard(client):
    tok = signup(client).json()["token"]
    assert client.get("/api/lecturer/overview", headers=auth(tok)).status_code == 403


# ---- full demo flow ----------------------------------------------------------------------------
def test_demo_flow_diagnose_stamp_circle_endorse(client, catalog):
    stu = client.post("/api/auth/login", json={"email": DEMO_STUDENT_EMAIL, "password": DEMO_PASSWORD}).json()["token"]
    h = auth(stu)

    m = client.post("/api/map", json={"stuckInput": "I don't get how backprop computes gradients for hidden layer weights"}, headers=h).json()
    assert m["targetConceptId"] == "backpropagation"

    d = client.post("/api/diagnoses", json={"stuckInput": "backprop", "targetConceptId": m["targetConceptId"], "mapping": m}, headers=h).json()
    while d["status"] == "in_progress":
        p = d["pending"]
        r = client.post(f"/api/diagnoses/{d['id']}/answer", json={"probeId": p["probeId"], "choiceIndex": answer_as("chain-rule", catalog, p)}, headers=h)
        assert r.status_code == 200, r.text
        d = r.json()["diagnosis"]
    assert d["result"]["rootCauseConceptId"] == "chain-rule"
    assert 3 <= d["probesAsked"] <= 5

    rem = client.get(f"/api/diagnoses/{d['id']}/remediation", headers=h).json()
    assert rem["found"] and rem["citations"][0]["sourceId"] == "calculus.md#chain-rule"
    assert len(rem["practice"]) == 3

    # Passport: the diagnosis alone never stamps; the gap shows as entry required.
    pp = client.get("/api/me/passport", headers=h).json()
    chain = next(c for r in pp["regions"] for c in r["concepts"] if c["conceptId"] == "chain-rule")
    assert chain["state"] == "entry-required" and pp["stamps"] == 0
    assert pp["next"]["targetConceptId"] == "backpropagation"

    # Two passed re-checks: amber, then solid with a verified stamp.
    states = []
    for _ in range(2):
        q = client.post("/api/recheck", json={"conceptId": "chain-rule"}, headers=h).json()
        a = client.post("/api/recheck/answer", json={"probeId": q["probeId"], "choiceIndex": catalog.probes[q["probeId"]]["correctIndex"]}, headers=h).json()
        states.append((a["status"], a["stampEarned"]))
    assert states == [("shaky", False), ("solid", True)]

    # Study circle with a lecturer slot.
    sug = client.get("/api/circles/suggestion", headers=h).json()
    assert sug["status"] == "proposal" and sug["circle"]["mode"] == "lecturer"
    circle = client.post("/api/circles/join", json={"conceptId": "chain-rule"}, headers=h).json()
    assert circle["isMember"] and 3 <= circle["memberCount"] <= 6

    # Demo staff login confirms the circle and countersigns the stamp.
    lec = client.post("/api/auth/login", json={"email": DEMO_LECTURER_EMAIL, "password": DEMO_PASSWORD}).json()["token"]
    ov = client.get("/api/lecturer/overview", headers=auth(lec)).json()
    assert any(c["id"] == circle["id"] for c in ov["requests"])
    assert all(row["students"] >= ov["minCount"] for row in ov["demand"])
    assert client.post(f"/api/lecturer/circles/{circle['id']}/endorse", headers=auth(lec)).status_code == 409
    client.post(f"/api/lecturer/circles/{circle['id']}/confirm", headers=auth(lec))
    e = client.post(f"/api/lecturer/circles/{circle['id']}/endorse", headers=auth(lec)).json()
    assert e["endorsed"] == 1

    pp = client.get("/api/me/passport", headers=h).json()
    chain = next(c for r in pp["regions"] for c in r["concepts"] if c["conceptId"] == "chain-rule")
    assert chain["state"] == "endorsed" and chain["endorsedBy"] == "Dr. Demo Lecturer"


def test_passport_customisation(client):
    tok = signup(client).json()["token"]
    me = client.get("/api/me", headers=auth(tok)).json()
    assert me["passportStyle"] is None  # not set up yet: the app sends new students to the setup page
    body = {"passport": {"cover": "forest", "emblem": "atom", "displayName": "Nisha R.", "motto": "Own Lab 5",
                         "focusLabIds": ["lab5", "nope"]}, "programme": "BSc Data Science", "year": 2}
    r = client.patch("/api/me", json=body, headers=auth(tok))
    assert r.status_code == 200, r.text
    st = r.json()["passportStyle"]
    assert st["setupDone"] and st["cover"] == "forest" and st["focusLabIds"] == ["lab5"]
    pp = client.get("/api/me/passport", headers=auth(tok)).json()
    assert pp["holder"] == "Nisha R." and pp["style"]["emblem"] == "atom" and pp["focusLabs"] == ["Lab 5: Backpropagation"]
    assert client.patch("/api/me", json={"passport": {"cover": "neon"}}, headers=auth(tok)).status_code == 400
    assert client.patch("/api/me", json={"passport": {"displayName": "X"}}, headers=auth(tok)).status_code == 400


def test_students_cannot_read_each_others_diagnoses(client):
    a = signup(client, email="a@example.edu").json()["token"]
    b = signup(client, email="b@example.edu").json()["token"]
    d = client.post("/api/diagnoses", json={"stuckInput": "softmax help", "targetConceptId": "softmax"}, headers=auth(a)).json()
    assert client.get(f"/api/diagnoses/{d['id']}", headers=auth(b)).status_code == 404
