"""Gemini client. Free tier by default (GEMINI_API_KEY from Google AI Studio); Vertex AI when USE_VERTEX=true.
With no key, or PUNCA_OFFLINE=true, the app runs in a deterministic offline mode and never calls a model.

Models are pinned. The primary model (GEMINI_MODEL) is tried first; if Google reports it is overloaded (503/429)
or the call times out (504), the next pinned model in GEMINI_FALLBACK_MODELS is tried, and the busy model is
skipped for LLM_COOLDOWN_S seconds. `last_model` records which model actually answered.
"""
from __future__ import annotations

import json
import logging
import time

from pydantic import BaseModel

import config

log = logging.getLogger("punca.llm")

TRANSIENT_MARKERS = ("503", "UNAVAILABLE", "429", "RESOURCE_EXHAUSTED", "504", "DEADLINE", "timed out", "Timeout",
                     "overloaded", "high demand")


class LLMUnavailable(RuntimeError):
    pass


def is_transient(message: str) -> bool:
    return any(m.lower() in message.lower() for m in TRANSIENT_MARKERS)


class LLMClient:
    def __init__(self, offline: bool | None = None):
        self.model = config.GEMINI_MODEL
        self.models = [config.GEMINI_MODEL] + [m for m in config.GEMINI_FALLBACK_MODELS if m != config.GEMINI_MODEL]
        self.mode = "offline"
        self.reason = ""
        self.last_model: str | None = None
        self._cooldown: dict[str, float] = {}
        self._client = None
        offline = config.PUNCA_OFFLINE if offline is None else offline
        if offline:
            self.reason = "PUNCA_OFFLINE is set"
            return
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            self.reason = "google-genai is not installed"
            return
        http = types.HttpOptions(timeout=config.LLM_TIMEOUT_MS)
        try:
            if config.USE_VERTEX:
                if not config.GCP_PROJECT:
                    self.reason = "USE_VERTEX=true but GCP_PROJECT is empty"
                    return
                self._client = genai.Client(vertexai=True, project=config.GCP_PROJECT,
                                            location=config.GCP_REGION, http_options=http)
                self.mode = "vertex"
            elif config.GEMINI_API_KEY:
                self._client = genai.Client(api_key=config.GEMINI_API_KEY, http_options=http)
                self.mode = "gemini-api"
            else:
                self.reason = "no GEMINI_API_KEY in .env"
        except Exception as exc:  # bad credentials etc.
            self.reason = f"client init failed: {exc}"
            self._client = None
            self.mode = "offline"
        log.info("LLM mode=%s models=%s %s", self.mode, ",".join(self.models), self.reason)

    @property
    def available(self) -> bool:
        return self._client is not None

    def _call(self, model: str, prompt: str, schema: type[BaseModel], temperature: float) -> str:
        from google.genai import types
        resp = self._client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        return resp.text or ""

    def generate_json(self, prompt: str, schema: type[BaseModel], temperature: float,
                      prefer: str | None = None) -> dict:
        """prefer: a model to try before the normal order (used for the fast routing step)."""
        if not self._client:
            raise LLMUnavailable(self.reason or "offline")
        now = time.time()
        order = ([prefer] if prefer else []) + [m for m in self.models if m != prefer]
        candidates = [m for m in order if self._cooldown.get(m, 0) <= now] or order[-1:]
        errors = []
        for model in candidates:
            t0 = time.perf_counter()
            try:
                text = self._call(model, prompt, schema, temperature)
            except Exception as exc:
                msg = str(exc)
                if is_transient(msg):
                    daily = "perday" in msg.replace(" ", "").lower()
                    self._cooldown[model] = time.time() + (config.LLM_DAILY_COOLDOWN_S if daily else config.LLM_COOLDOWN_S)
                    log.warning("model %s busy (%.1fs): %s", model, time.perf_counter() - t0, msg[:160])
                    errors.append(f"{model}: {msg[:120]}")
                    continue
                raise
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{model} returned non-JSON: {text[:200]!r}") from exc
            self.last_model = model
            log.info("model %s answered in %.1fs", model, time.perf_counter() - t0)
            return schema.model_validate(data).model_dump()
        raise LLMUnavailable("all Gemini models are busy: " + " | ".join(errors))
