"""Gemini client. Free tier by default (GEMINI_API_KEY from Google AI Studio); Vertex AI when USE_VERTEX=true.
With no key, or PUNCA_OFFLINE=true, the app runs in a deterministic offline mode and never calls a model."""
from __future__ import annotations

import json
import logging

from pydantic import BaseModel

import config

log = logging.getLogger("punca.llm")


class LLMUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self, offline: bool | None = None):
        self.model = config.GEMINI_MODEL
        self.mode = "offline"
        self.reason = ""
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
        log.info("LLM mode=%s model=%s %s", self.mode, self.model, self.reason)

    @property
    def available(self) -> bool:
        return self._client is not None

    def generate_json(self, prompt: str, schema: type[BaseModel], temperature: float) -> dict:
        if not self._client:
            raise LLMUnavailable(self.reason or "offline")
        from google.genai import types
        resp = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temperature,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        text = resp.text or ""
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"model returned non-JSON: {text[:200]!r}") from exc
        return schema.model_validate(data).model_dump()
