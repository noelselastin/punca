"""Punca HTTP API (FastAPI) app factory. api/main.py builds the app that uvicorn serves."""
from __future__ import annotations

import logging
import time
import traceback
from pathlib import Path

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

import config
from logging_setup import setup_logging

setup_logging()

from api.service import PuncaService, ServiceError  # noqa: E402
from content import Catalog  # noqa: E402
from llm.client import LLMClient  # noqa: E402
from llm.service import LLMService  # noqa: E402
from store.local_store import LocalStore  # noqa: E402
from store.seed import seed_store  # noqa: E402

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
    availability: list[str] | None = None
    consent: dict | None = None
    passport: dict | None = None
    programme: str | None = None
    year: int | str | None = None


class MapBody(BaseModel):
    stuckInput: str


class StartBody(BaseModel):
    stuckInput: str
    targetConceptId: str
    mapping: dict | None = None


class AnswerBody(BaseModel):
    probeId: str
    choiceIndex: int


class ConceptBody(BaseModel):
    conceptId: str


class SlotBody(BaseModel):
    day: str
    start: int
    end: int
    capacity: int
    linkedConceptIds: list[str]
    kind: str = "consultation"


class ClientLogBody(BaseModel):
    level: str = "error"
    message: str
    stack: str | None = None
    url: str | None = None


class MoodleCheckBody(BaseModel):
    baseUrl: str | None = None


class MoodleConnectBody(BaseModel):
    mode: str = "token"
    baseUrl: str | None = None
    token: str | None = None


class MoodleImportBody(BaseModel):
    title: str | None = None
    courseName: str | None = None
    filename: str | None = None
    contentBase64: str | None = None
    text: str | None = None


def create_app(store_path: Path | None = None, offline: bool | None = None) -> FastAPI:
    catalog = Catalog()
    store = LocalStore(store_path or config.STORE_PATH)
    if store.empty:
        log.info("store is empty: seeding synthetic demo data")
        seed_store(store, catalog)
    llm_client = LLMClient(offline=offline)
    svc = PuncaService(catalog, store, LLMService(catalog, llm_client))

    app = FastAPI(title="Punca API", version="0.1.0")
    app.state.svc = svc

    @app.exception_handler(ServiceError)
    async def _service_error(_: Request, exc: ServiceError):
        return JSONResponse(status_code=exc.status, content={"error": exc.message})

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.error("unhandled error on %s %s: %s\n%s", request.method, request.url.path, exc,
                  "".join(traceback.format_exception(exc)))
        return JSONResponse(status_code=500, content={"error": "Something went wrong on the server. It has been logged."})

    @app.middleware("http")
    async def _access_log(request: Request, call_next):
        t0 = time.perf_counter()
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            log.info("%s %s -> %s (%.0f ms)", request.method, request.url.path, response.status_code,
                     (time.perf_counter() - t0) * 1000)
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
        return {"ok": True, "llm": {"mode": llm_client.mode, "model": llm_client.model, "models": llm_client.models,
                                    "lastModel": llm_client.last_model, "reason": llm_client.reason}}

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
        return svc.map_stuck(body.stuckInput)

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
        return svc.answer(user["uid"], did, body.probeId, body.choiceIndex)

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

    # ---- student: circles --------------------------------------------------------------------
    @app.get("/api/circles/suggestion")
    def circle_suggestion(conceptId: str | None = None, user: dict = Depends(student)):
        return svc.circle_suggestion(user, conceptId)

    @app.post("/api/circles/join")
    def join_circle(body: ConceptBody, user: dict = Depends(student)):
        return svc.join_circle(user, body.conceptId)

    @app.get("/api/circles")
    def my_circles(user: dict = Depends(student)):
        return svc.my_circles(user)

    @app.post("/api/circles/{circle_id}/done")
    def circle_done(circle_id: str, user: dict = Depends(student)):
        return svc.circle_done(user, circle_id)

    # ---- student: moodle ---------------------------------------------------------------------
    @app.get("/api/moodle/status")
    def moodle_status(user: dict = Depends(student)):
        return svc.moodle_status(user)

    @app.post("/api/moodle/check")
    def moodle_check(body: MoodleCheckBody, user: dict = Depends(student)):
        return svc.moodle_check(body.baseUrl)

    @app.post("/api/moodle/connect")
    def moodle_connect(body: MoodleConnectBody, user: dict = Depends(student)):
        return svc.moodle_connect(user, body.model_dump())

    @app.post("/api/moodle/sync")
    def moodle_sync(user: dict = Depends(student)):
        return svc.moodle_sync(user)

    @app.delete("/api/moodle/connection")
    def moodle_disconnect(user: dict = Depends(student)):
        return svc.moodle_disconnect(user)

    @app.post("/api/moodle/import")
    def moodle_import(body: MoodleImportBody, user: dict = Depends(student)):
        return svc.moodle_import(user, body.model_dump())

    # ---- lecturer ----------------------------------------------------------------------------
    @app.get("/api/lecturer/overview")
    def overview(user: dict = Depends(current_user)):
        return svc.lecturer_overview(user)

    @app.post("/api/lecturer/slots")
    def create_slot(body: SlotBody, user: dict = Depends(current_user)):
        return svc.create_slot(user, body.model_dump())

    @app.post("/api/lecturer/clinic")
    def open_clinic(body: ConceptBody, user: dict = Depends(current_user)):
        return svc.open_clinic(user, body.conceptId)

    @app.post("/api/lecturer/circles/{circle_id}/confirm")
    def confirm(circle_id: str, user: dict = Depends(current_user)):
        return svc.confirm_circle(user, circle_id)

    @app.post("/api/lecturer/circles/{circle_id}/endorse")
    def endorse(circle_id: str, user: dict = Depends(current_user)):
        return svc.endorse_circle(user, circle_id)

    @app.post("/api/lecturer/circles/{circle_id}/decline")
    def decline(circle_id: str, user: dict = Depends(current_user)):
        return svc.decline_circle(user, circle_id)

    log.info("Punca API ready: %d concepts, %d probes, %d note passages, LLM mode %s",
             len(catalog.concepts), len(catalog.probes), len(catalog.notes), llm_client.mode)
    return app

