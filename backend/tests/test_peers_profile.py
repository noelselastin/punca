"""Peer suggestions, flexible circles, profile editing, Google Calendar hand-off, and removed features."""
import json

from store.seed import DEMO_ACCOUNTS, DEMO_PASSWORD



def auth(token):
    return {"Authorization": f"Bearer {token}"}


def signup(client, email="fresh.student@gmail.com", student_id="TP900001"):
    body = {
        "name": "Fresh Student",
        "email": email,
        "password": "correct-horse-1",
        "confirmPassword": "correct-horse-1",
        "university": "Asia Pacific University (APU)",
        "studentId": student_id,
        "programme": "BSc Computer Science",
    }
    r = client.post("/api/auth/signup", json=body)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def login(client, email):
    return client.post("/api/auth/login", json={"email": email, "password": DEMO_PASSWORD}).json()["token"]


# ---- demo accounts -----------------------------------------------------------------------------
def test_every_demo_account_signs_in_and_its_route_opens(client):
    assert len(DEMO_ACCOUNTS) == 7
    for acc in DEMO_ACCOUNTS:
        r = client.post("/api/auth/login", json={"email": acc["email"], "password": DEMO_PASSWORD})
        assert r.status_code == 200, acc["email"]
        h = auth(r.json()["token"])
        consent = r.json()["user"]["consent"]
        assert consent["joinCircles"] and consent["shareNameWithCircle"] and consent["shareContact"]
        pp = client.get("/api/me/passport", headers=h).json()
        if pp["next"]:
            # "Open this route" on the passport must lead to a diagnosis that loads.
            assert client.get(f"/api/diagnoses/{pp['next']['diagnosisId']}", headers=h).status_code == 200
        for d in client.get("/api/diagnoses", headers=h).json():
            assert client.get(f"/api/diagnoses/{d['id']}", headers=h).status_code == 200


def test_in_progress_count_matches_the_concepts_the_filter_shows(client):
    h = auth(login(client, "hafiz.student@demo.punca.edu"))
    pp = client.get("/api/me/passport", headers=h).json()
    states = [c["state"] for r in pp["regions"] for c in r["concepts"]]
    assert pp["stampSummary"]["inProgress"] == states.count("shaky") + states.count("solid") > 0
    assert pp["stampSummary"]["completed"] == states.count("stamped") == 6


# ---- peer suggestions and circles ----------------------------------------------------------------
def test_new_account_sees_named_peers_with_contact_emails(client):
    h = auth(signup(client))
    data = client.get("/api/circles/peers", headers=h).json()
    by_name = {p["name"]: p for p in data["peers"]}
    for name in ("Aisyah Rahman", "Hafiz Tan", "Priya Nair", "Nur Iman Zulkifli", "Marcus Wong"):
        assert name in by_name, name
        assert by_name[name]["email"].endswith("@demo.punca.edu")
        assert by_name[name]["gaps"] and by_name[name]["modules"]
    assert {c["id"] for c in data["openCircles"]} >= {"c-demo-chain", "c-demo-joins", "c-demo-recursion"}
    assert data["me"]["gaps"] == [] and data["me"]["optedIn"] is False


def test_peers_are_ranked_by_common_gaps_and_show_shared_free_hours(client):
    h = auth(login(client, "aisyah.student@demo.punca.edu"))
    peers = client.get("/api/circles/peers", headers=h).json()["peers"]
    top = {p["name"] for p in peers[:2]}
    assert top == {"Hafiz Tan", "Marcus Wong"}  # both share Aisyah's chain rule gap
    hafiz = next(p for p in peers if p["name"] == "Hafiz Tan")
    assert "Chain rule" in [g["name"] for g in hafiz["commonGaps"]]
    assert "Tue 14:00-15:00" in hafiz["sharedHours"] and hafiz["inCircleWithYou"] is True
    assert "Computational Mathematics" in hafiz["commonModules"]


def test_peer_without_consent_is_hidden_or_anonymous(client):
    a = auth(signup(client, "a.student@gmail.com", "TP900010"))
    b = auth(signup(client, "b.student@gmail.com", "TP900011"))
    names = lambda: [p["name"] for p in client.get("/api/circles/peers", headers=a).json()["peers"]]  # noqa: E731
    assert "Fresh Student" not in names()  # not opted in: never suggested
    client.patch("/api/me", json={"consent": {"joinCircles": True}}, headers=b)
    listed = client.get("/api/circles/peers", headers=a).json()["peers"]
    anon = [p for p in listed if p["name"] == "Anonymous peer"]
    assert len(anon) == 1 and anon[0]["email"] is None
    client.patch("/api/me", json={"consent": {"shareNameWithCircle": True, "shareContact": True}}, headers=b)
    shown = next(p for p in client.get("/api/circles/peers", headers=a).json()["peers"] if p["name"] == "Fresh Student")
    assert shown["email"] == "b.student@gmail.com"


def test_circle_can_be_joined_without_any_shared_free_hour(client):
    h = auth(signup(client))  # no free hours saved at all
    sug = client.get("/api/circles/suggestion?conceptId=CM-CHAIN", headers=h).json()
    assert sug["status"] == "existing" and sug["circle"]["id"] == "c-demo-chain"
    joined = client.post("/api/circles/c-demo-joins/join", headers=h).json()
    assert joined["isMember"] and joined["memberCount"] == 4
    emails = {m["email"] for m in joined["memberDetails"]}
    assert {"priya.student@demo.punca.edu", "iman.student@demo.punca.edu", "marcus.student@demo.punca.edu"} <= emails
    assert any("joined the circle" in m["text"] for m in joined["messages"])
    assert client.post("/api/circles/nope/join", headers=h).status_code == 404


def test_new_circle_is_proposed_even_when_no_hour_overlaps(client):
    # PY-SCOPE has no circle yet; two students with different free hours still get one proposed.
    a = auth(signup(client, "a.student@gmail.com", "TP900010"))
    b = auth(signup(client, "b.student@gmail.com", "TP900011"))
    svc = client.svc
    for h, slots in ((a, ["Mon-9"]), (b, ["Fri-17"])):
        uid = client.get("/api/me", headers=h).json()["uid"]
        client.patch("/api/me", json={"availability": slots, "consent": {"joinCircles": True}}, headers=h)
        svc.store.put("mastery", f"{uid}_PY-SCOPE", {"uid": uid, "conceptId": "PY-SCOPE", "pKnown": 0.2, "evidenceCount": 2, "lastUpdated": "2026-11-01T00:00:00+00:00"})
    sug = client.get("/api/circles/suggestion?conceptId=PY-SCOPE", headers=a).json()
    assert sug["status"] == "proposal" and sug["circle"]["slotAgreed"] is False
    circle = client.post("/api/circles/join", json={"conceptId": "PY-SCOPE"}, headers=a).json()
    assert circle["isMember"] and circle["memberCount"] >= 2 and circle["proposedSlot"] is None
    assert circle["slotLabel"] == "Time to be agreed in the chat"
    cal = client.post(f"/api/circles/{circle['id']}/calendar", headers=a)
    assert cal.status_code == 200 and "calendar.google.com" in cal.json()["event"]["calendarLink"]


# ---- edit profile --------------------------------------------------------------------------------
def test_student_can_edit_their_profile(client):
    h = auth(signup(client))
    r = client.patch(
        "/api/me",
        json={
            "name": "Fresh S. Renamed",
            "email": "renamed.student@gmail.com",
            "university": "APU",
            "studentId": "tp900099",
            "programme": "BSc Data Science",
            "year": 3,
        },
        headers=h,
    )
    assert r.status_code == 200, r.text
    me = client.get("/api/me", headers=h).json()
    assert (me["name"], me["email"], me["university"], me["studentId"], me["programme"], me["year"]) == (
        "Fresh S. Renamed", "renamed.student@gmail.com", "APU", "TP900099", "BSc Data Science", 3,
    )
    assert me["googleEmail"] == "renamed.student@gmail.com"
    assert client.get("/api/me/passport", headers=h).json()["holderNo"] == "TP900099"
    # The new email signs in; the old one no longer does.
    ok = client.post("/api/auth/login", json={"email": "renamed.student@gmail.com", "password": "correct-horse-1"})
    old = client.post("/api/auth/login", json={"email": "fresh.student@gmail.com", "password": "correct-horse-1"})
    assert ok.status_code == 200 and old.status_code == 401


def test_profile_edit_rejects_bad_or_taken_details(client):
    h = auth(signup(client))
    auth(signup(client, "other.student@gmail.com", "TP900002"))
    assert client.patch("/api/me", json={"name": "X"}, headers=h).status_code == 400
    assert client.patch("/api/me", json={"email": "not-an-email"}, headers=h).status_code == 400
    assert client.patch("/api/me", json={"email": "OTHER.student@gmail.com"}, headers=h).status_code == 409
    assert client.patch("/api/me", json={"studentId": "tp900002"}, headers=h).status_code == 409
    assert client.patch("/api/me", json={"studentId": "bad id"}, headers=h).status_code == 400
    # Saving the form unchanged is fine, and demo accounts keep their sign-in details.
    assert client.patch("/api/me", json={"email": "fresh.student@gmail.com", "studentId": "TP900001"}, headers=h).status_code == 200
    demo = auth(login(client, "aisyah.student@demo.punca.edu"))
    assert client.patch("/api/me", json={"email": "someone@gmail.com"}, headers=demo).status_code == 400
    assert client.patch("/api/me", json={"name": "Aisyah R."}, headers=demo).status_code == 200


# ---- Google Calendar, and the removed Drive and Google Tasks features ----------------------------
class FakeGoogle:
    """Stands in for Google's APIs: records calls and answers the few endpoints Punca uses."""

    def __init__(self):
        self.calls = []

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url))
        assert headers["Authorization"] == "Bearer test-token"
        if "oauth2/v3/userinfo" in url:
            return 200, json.dumps({"email": "fresh.student@gmail.com", "name": "Fresh Student"}).encode()
        if "calendar/v3/calendars/primary/events" in url and method == "POST":
            return 200, json.dumps({"id": "ev-1", "htmlLink": "https://calendar.google.com/event?eid=1", "hangoutLink": "https://meet.google.com/abc-defg-hij"}).encode()
        return 404, b"{}"


def connect(client, h):
    fake = FakeGoogle()
    client.svc.live._transport = fake
    r = client.post("/api/google/connect", json={"accessToken": "test-token", "expiresIn": 3600}, headers=h)
    assert r.status_code == 200 and r.json()["liveConnected"] is True
    return fake


def test_drive_and_google_tasks_features_are_gone(client):
    h = auth(signup(client))
    ws = client.get("/api/google/status", headers=h).json()
    assert "driveFiles" not in ws and "drive" not in ws["enabledServices"]
    assert not any("drive.readonly" in s or s.endswith("/auth/tasks") for s in ws["oauthScopes"])
    for method, path in (
        ("get", "/api/google/drive/browse"),
        ("post", "/api/google/drive/import"),
        ("post", "/api/google/drive/import-link"),
        ("post", "/api/google/drive/upload"),
        ("post", "/api/google/tasks/sync"),
        ("post", f"/api/google/tasks/{ws['tasks'][0]['id']}/sync"),
    ):
        r = getattr(client, method)(path, json={}, headers=h) if method == "post" else client.get(path, headers=h)
        assert r.status_code in (404, 405), (path, r.status_code)
    # Diagnose ignores old Drive fields and still reads a file uploaded from the PC.
    m = client.post(
        "/api/map",
        json={"stuckInput": "", "driveFileId": "gdrive-sample-cm-graddesc", "fileName": "lab.txt",
              "fileText": "Gradient descent with partial derivatives and the chain rule."},
        headers=h,
    ).json()
    assert m["documentSummary"]["source"] == "pc-upload"


def test_study_tasks_stay_in_punca_even_when_google_is_connected(client):
    h = auth(signup(client))
    fake = connect(client, h)
    task = client.post("/api/google/tasks", json={"title": "Revise joins"}, headers=h).json()["task"]
    assert "googleId" not in task and "live" not in task
    client.patch(f"/api/google/tasks/{task['id']}", json={"completed": True}, headers=h)
    client.delete(f"/api/google/tasks/{task['id']}", headers=h)
    assert not any("tasks" in url for _, url in fake.calls)


def test_every_session_has_an_add_to_calendar_link(client):
    h = auth(login(client, "aisyah.student@demo.punca.edu"))
    uid = client.get("/api/me", headers=h).json()["uid"]
    user = client.svc.store.get("users", uid)
    for ev in user["googleWorkspace"]["calendarEvents"]:
        ev["calendarLink"] = None  # as saved by an earlier build
    client.svc.store.put("users", uid, user)
    events = client.get("/api/google/status", headers=h).json()["calendarEvents"]
    assert len(events) >= 2
    assert all("calendar.google.com/calendar/render" in ev["calendarLink"] for ev in events)


def test_existing_sessions_can_be_added_to_google_calendar(client):
    h = auth(signup(client))
    event_id = client.get("/api/google/status", headers=h).json()["calendarEvents"][0]["id"]
    # Without a Google connection Punca explains what is needed.
    blocked = client.post(f"/api/google/calendar/events/{event_id}/sync", headers=h)
    assert blocked.status_code == 409 and "Connect your Google account" in blocked.json()["error"]

    fake = connect(client, h)
    ev = client.post(f"/api/google/calendar/events/{event_id}/sync", headers=h).json()["event"]
    assert ev["live"] and ev["calendarLink"] == "https://calendar.google.com/event?eid=1"
    assert ev["meetUrl"] == "https://meet.google.com/abc-defg-hij"
    assert sum("calendar/v3" in url for method, url in fake.calls if method == "POST") == 1
