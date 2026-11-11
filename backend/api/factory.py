"""Punca HTTP API (FastAPI) app factory. api/main.py builds the app that uvicorn serves."""
from __future__ import annotations

import logging
import time
import traceback
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import config
from logging_setup import setup_logging

setup_logging()

from api.service import PuncaService, ServiceError  # noqa: E402
from content import Catalog  # noqa: E402
from llm.client import LLMClient  # noqa: E402
from llm.service import LLMService  # noqa: E402
from store.local_store import LocalStore  # noqa: E402
from store.seed import DEMO_ACCOUNTS, DEMO_PASSWORD, ensure_demo_users, seed_store  # noqa: E402

log = logging.getLogger("punca.api")
client_log = logging.getLogger("punca.client")


# ---- request bodies ---------------------------------------------------------------------------
class SignupBody(BaseModel):
    name: str
    email: str
    password: str
    confirmPassword: str = ""
    university: str = ""
    studentId: str = ""
    programme: str | None = None
    year: int | str | None = None


class LoginBody(BaseModel):
    email: str
    password: str


class ProfileBody(BaseModel):
    name: str | None = None
    email: str | None = None
    university: str | None = None
    studentId: str | None = None
    availability: list[str] | None = None
    consent: dict | None = None
    passport: dict | None = None
    programme: str | None = None
    year: int | str | None = None


class MapBody(BaseModel):
    stuckInput: str = ""
    fileName: str | None = None
    fileBase64: str | None = None
    fileText: str | None = None


class StartBody(BaseModel):
    stuckInput: str
    targetConceptId: str
    mapping: dict | None = None


class AnswerBody(BaseModel):
    probeId: str
    choiceIndex: int
    confidence: str = "medium"


class ConceptBody(BaseModel):
    conceptId: str


class CircleMessageBody(BaseModel):
    text: str


class CircleMeetBody(BaseModel):
    meetUrl: str


class ClientLogBody(BaseModel):
    level: str = "error"
    message: str
    stack: str | None = None
    url: str | None = None


class GoogleConnectBody(BaseModel):
    accessToken: str
    expiresIn: int | None = None


class GoogleConfigBody(BaseModel):
    connected: bool | None = None
    email: str | None = None
    accessToken: str | None = None
    expiresIn: int | None = None
    enabledServices: dict | None = None
    preferences: dict | None = None


class CalendarEventBody(BaseModel):
    title: str
    description: str | None = None
    startTime: str | None = None
    endTime: str | None = None
    location: str | None = None
    includeMeet: bool = True
    conceptId: str | None = None
    attendees: list[str] | None = None


class TaskCreateBody(BaseModel):
    title: str
    notes: str | None = None
    due: str | None = None
    conceptId: str | None = None
    diagnosisId: str | None = None


class TaskUpdateBody(BaseModel):
    title: str | None = None
    notes: str | None = None
    due: str | None = None
    completed: bool | None = None


class DocCreateBody(BaseModel):
    title: str
    content: str = ""
    conceptId: str | None = None


class DocUpdateBody(BaseModel):
    title: str | None = None
    content: str | None = None


class ChatSpaceCreateBody(BaseModel):
    name: str
    conceptId: str | None = None
    circleId: str | None = None


class ChatMessageBody(BaseModel):
    text: str


def create_app(store_path: Path | None = None, offline: bool | None = None) -> FastAPI:
    catalog = Catalog()
    store = LocalStore(store_path or config.STORE_PATH)
    if store.empty:
        log.info("store is empty: seeding synthetic demo data")
        seed_store(store, catalog)
    llm_client = LLMClient(offline=offline)
    svc = PuncaService(catalog, store, LLMService(catalog, llm_client))
    # Demo accounts are built through the service so their diagnoses, stamps and circles are real
    # records. Runs on every start and only rebuilds a demo account when its data version changed.
    ensure_demo_users(svc)

    app = FastAPI(title="Punca API", version="0.2.0")
    app.state.svc = svc

    @app.exception_handler(ServiceError)
    async def _service_error(_: Request, exc: ServiceError):
        return JSONResponse(status_code=exc.status, content={"error": exc.message})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.error(
            "unhandled error on %s %s: %s\n%s",
            request.method,
            request.url.path,
            exc,
            "".join(traceback.format_exception(exc)),
        )
        return JSONResponse(status_code=500, content={"error": "Something went wrong on the server. It has been logged."})

    @app.middleware("http")
    async def _access_log(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            log.info(
                "%s %s -> %s (%.0f ms)",
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - t0) * 1000,
            )
        return response

    # ---- auth helpers ----------------------------------------------------------------------
    def _token(authorization: str = Header(default="")) -> str:
        return authorization[7:].strip() if authorization.lower().startswith("bearer ") else ""

    def current_user(token: str = Depends(_token)) -> dict:
        return svc.user_for_token(token)

    def student(user: dict = Depends(current_user)) -> dict:
        if user["role"] != "student":
            raise ServiceError(403, "This action is for student accounts.")
        return user

    # ---- public ------------------------------------------------------------------------------
    @app.get("/api/health")
    def health():
        return {
            "ok": True,
            "llm": {
                "mode": llm_client.mode,
                "model": llm_client.model,
                "models": llm_client.models,
                "lastModel": llm_client.last_model,
                "reason": llm_client.reason,
            },
            "google": {
                "liveAvailable": bool(config.GOOGLE_OAUTH_CLIENT_ID),
                "clientId": config.GOOGLE_OAUTH_CLIENT_ID or None,
            },
        }

    @app.get("/api/demo/accounts")
    def demo_accounts():
        return {"password": DEMO_PASSWORD, "accounts": DEMO_ACCOUNTS}

    @app.get("/api/catalog")
    def get_catalog():
        return catalog.catalog_view()

    @app.post("/api/log/client")
    def log_client(body: ClientLogBody):
        lvl = logging.WARNING if body.level == "warn" else logging.ERROR
        client_log.log(lvl, "%s | %s | %s", (body.url or "")[:200], body.message[:1000], (body.stack or "")[:3000])
        return {"ok": True}

    # ---- accounts ----------------------------------------------------------------------------
    @app.post("/api/auth/signup")
    def signup(body: SignupBody):
        return svc.signup(body.model_dump())

    @app.post("/api/auth/login")
    def login(body: LoginBody):
        return svc.login(body.email, body.password)

    @app.post("/api/auth/logout")
    def logout(token: str = Depends(_token)):
        svc.logout(token)
        return {"ok": True}

    @app.get("/api/me")
    def me(user: dict = Depends(current_user)):
        return svc.public_user(user)

    @app.patch("/api/me")
    def update_me(body: ProfileBody, user: dict = Depends(current_user)):
        return svc.update_profile(user, body.model_dump(exclude_none=True))

    # ---- student: diagnosis ------------------------------------------------------------------
    @app.get("/api/me/mastery")
    def my_mastery(user: dict = Depends(student)):
        return svc.mastery_map(user["uid"])

    @app.post("/api/me/mastery/{concept_id}/known")
    def i_know_this(concept_id: str, user: dict = Depends(student)):
        return svc.mark_known(user["uid"], concept_id)

    @app.post("/api/map")
    def map_stuck(body: MapBody, user: dict = Depends(student)):
        return svc.map_stuck(user, body.stuckInput, body.model_dump())

    @app.post("/api/diagnoses")
    def start(body: StartBody, user: dict = Depends(student)):
        return svc.start_diagnosis(user, body.stuckInput, body.targetConceptId, body.mapping)

    @app.get("/api/diagnoses")
    def my_diagnoses(user: dict = Depends(student)):
        return svc.list_diagnoses(user["uid"])

    @app.get("/api/diagnoses/{did}")
    def get_diagnosis(did: str, user: dict = Depends(student)):
        return svc.get_diagnosis(user["uid"], did)

    @app.post("/api/diagnoses/{did}/answer")
    def answer(did: str, body: AnswerBody, user: dict = Depends(student)):
        return svc.answer(user["uid"], did, body.probeId, body.choiceIndex, confidence=body.confidence)

    @app.get("/api/diagnoses/{did}/remediation")
    def remediation(did: str, user: dict = Depends(student)):
        return svc.remediation(user["uid"], did)

    @app.get("/api/me/passport")
    def my_passport(user: dict = Depends(student)):
        return svc.passport(user)

    @app.post("/api/recheck")
    def recheck(body: ConceptBody, user: dict = Depends(student)):
        return svc.recheck_start(user, body.conceptId)

    @app.post("/api/recheck/answer")
    def recheck_answer(body: AnswerBody, user: dict = Depends(student)):
        return svc.recheck_answer(user, body.probeId, body.choiceIndex)

    # ---- student: peer study circles ---------------------------------------------------------
    @app.get("/api/circles/suggestion")
    def circle_suggestion(conceptId: str | None = None, user: dict = Depends(student)):
        return svc.circle_suggestion(user, conceptId)

    @app.get("/api/circles/peers")
    def circle_peers(user: dict = Depends(student)):
        return svc.peer_suggestions(user)

    @app.post("/api/circles/{circle_id}/join")
    def join_circle_by_id(circle_id: str, user: dict = Depends(student)):
        return svc.join_circle_by_id(user, circle_id)

    @app.post("/api/circles/join")
    def join_circle(body: ConceptBody, user: dict = Depends(student)):
        return svc.join_circle(user, body.conceptId)

    @app.get("/api/circles")
    def my_circles(user: dict = Depends(student)):
        return svc.my_circles(user)

    @app.post("/api/circles/{circle_id}/done")
    def circle_done(circle_id: str, user: dict = Depends(student)):
        return svc.circle_done(user, circle_id)

    @app.post("/api/circles/{circle_id}/chat")
    def circle_chat(circle_id: str, body: CircleMessageBody, user: dict = Depends(student)):
        return svc.circle_chat_post(user, circle_id, body.text)

    @app.post("/api/circles/{circle_id}/meet")
    def circle_meet(circle_id: str, body: CircleMeetBody, user: dict = Depends(student)):
        return svc.circle_set_meet(user, circle_id, body.meetUrl)

    @app.post("/api/circles/{circle_id}/calendar")
    def circle_calendar(circle_id: str, user: dict = Depends(student)):
        return svc.circle_schedule_calendar(user, circle_id)

    # ---- student: Google Workspace -----------------------------------------------------------
    @app.get("/api/google/status")
    def google_status(user: dict = Depends(student)):
        return svc.google_status(user)

    @app.post("/api/google/connect")
    def google_connect(body: GoogleConnectBody, user: dict = Depends(student)):
        return svc.google_connect(user, body.accessToken, body.expiresIn)

    @app.post("/api/google/disconnect")
    def google_disconnect(user: dict = Depends(student)):
        return svc.google_disconnect(user)

    @app.post("/api/google/configure")
    def google_configure(body: GoogleConfigBody, user: dict = Depends(student)):
        return svc.google_configure(user, body.model_dump(exclude_none=True))

    @app.post("/api/google/calendar/events")
    def google_calendar_create(body: CalendarEventBody, user: dict = Depends(student)):
        return svc.google_calendar_create(user, body.model_dump())

    @app.post("/api/google/calendar/events/{event_id}/sync")
    def google_calendar_sync(event_id: str, user: dict = Depends(student)):
        return svc.google_calendar_sync(user, event_id)

    @app.delete("/api/google/calendar/events/{event_id}")
    def google_calendar_delete(event_id: str, user: dict = Depends(student)):
        return svc.google_calendar_delete(user, event_id)

    @app.post("/api/google/tasks")
    def google_tasks_create(body: TaskCreateBody, user: dict = Depends(student)):
        return svc.google_tasks_create(user, body.model_dump())

    @app.patch("/api/google/tasks/{task_id}")
    def google_tasks_update(task_id: str, body: TaskUpdateBody, user: dict = Depends(student)):
        return svc.google_tasks_update(user, task_id, body.model_dump(exclude_none=True))

    @app.delete("/api/google/tasks/{task_id}")
    def google_tasks_delete(task_id: str, user: dict = Depends(student)):
        return svc.google_tasks_delete(user, task_id)

    @app.post("/api/google/tasks/from-diagnosis/{did}")
    def google_tasks_from_diagnosis(did: str, user: dict = Depends(student)):
        return svc.google_tasks_from_diagnosis(user, did)

    @app.post("/api/google/docs")
    def google_docs_create(body: DocCreateBody, user: dict = Depends(student)):
        return svc.google_docs_create(user, body.model_dump())

    @app.patch("/api/google/docs/{doc_id}")
    def google_docs_update(doc_id: str, body: DocUpdateBody, user: dict = Depends(student)):
        return svc.google_docs_update(user, doc_id, body.model_dump(exclude_none=True))

    @app.delete("/api/google/docs/{doc_id}")
    def google_docs_delete(doc_id: str, user: dict = Depends(student)):
        return svc.google_docs_delete(user, doc_id)

    @app.post("/api/google/docs/from-diagnosis/{did}")
    def google_docs_from_diagnosis(did: str, user: dict = Depends(student)):
        return svc.google_docs_from_diagnosis(user, did)

    @app.post("/api/google/chat/spaces")
    def google_chat_create_space(body: ChatSpaceCreateBody, user: dict = Depends(student)):
        return svc.google_chat_create_space(user, body.model_dump())

    @app.post("/api/google/chat/spaces/{space_id}/messages")
    def google_chat_post(space_id: str, body: ChatMessageBody, user: dict = Depends(student)):
        return svc.google_chat_post(user, space_id, body.text)

    dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist_dir.is_dir() and (dist_dir / "index.html").is_file():
        assets_dir = dist_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def serve_spa(full_path: str):
            if full_path == "api" or full_path.startswith("api/"):
                return JSONResponse(status_code=404, content={"error": "Not found"})
            candidate = (dist_dir / full_path).resolve()
            if full_path and candidate.is_file() and str(candidate).startswith(str(dist_dir.resolve())):
                return FileResponse(str(candidate))
            return FileResponse(str(dist_dir / "index.html"))

    log.info(
        "Punca API ready: %d concepts, %d probes, %d note passages, LLM mode %s",
        len(catalog.concepts),
        len(catalog.probes),
        len(catalog.notes),
        llm_client.mode,
    )
    return app
