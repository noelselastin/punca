"""Google Workspace integration & document text extraction for Punca.

Provides:
1. Document reader (`extract_document_text`) for files uploaded from the student's PC
   (.pdf, .docx, .pptx, .ipynb, .py, .java, .sql, .md, .txt, .csv, .json).
2. The per-user Workspace state Punca keeps (`calendar`, `tasks`, `chat`, `meet`, `docs`)
   with per-user settings (`enabledServices`, `preferences`). Live calls to the student's own
   Google account are in google_live.py; links are stored here only when Google returned them.
"""
from __future__ import annotations

import base64
import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone
from urllib import parse as urlparse


class WorkspaceError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


SERVICES = ("calendar", "tasks", "chat", "meet", "docs")
# Folder in the student's Google Drive that Punca's Google Docs are saved into.
DOCS_FOLDER = "Punca Study Materials"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat(timespec="seconds")


# ===================================================================== Document Extraction ====
def _extract_docx(raw: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        if "word/document.xml" not in zf.namelist():
            return ""
        xml_bytes = zf.read("word/document.xml")
    root = ET.fromstring(xml_bytes)
    paragraphs: list[str] = []
    for p in root.iter():
        if p.tag.endswith("}p"):
            runs = [t.text for t in p.iter() if t.tag.endswith("}t") and t.text]
            if runs:
                paragraphs.append("".join(runs).strip())
    return "\n".join(p for p in paragraphs if p)


def _extract_pptx(raw: bytes) -> str:
    slides: list[str] = []
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        slide_names = sorted(
            n for n in zf.namelist()
            if n.startswith("ppt/slides/slide") and n.endswith(".xml")
        )
        for name in slide_names:
            root = ET.fromstring(zf.read(name))
            texts = [t.text.strip() for t in root.iter() if t.tag.endswith("}t") and t.text and t.text.strip()]
            if texts:
                slides.append(" ".join(texts))
    return "\n\n".join(slides)


def _extract_ipynb(raw: bytes) -> str:
    nb = json.loads(raw.decode("utf-8", errors="replace"))
    cells = nb.get("cells") or []
    parts: list[str] = []
    for cell in cells:
        src = cell.get("source") or []
        text = "".join(src) if isinstance(src, list) else str(src)
        if text.strip():
            parts.append(text.strip())
    return "\n\n".join(parts)


def _extract_pdf(raw: bytes) -> str:
    try:
        import pypdf  # type: ignore
        reader = pypdf.PdfReader(io.BytesIO(raw))
        pages = [page.extract_text() or "" for page in reader.pages]
        joined = "\n".join(p.strip() for p in pages if p.strip())
        if joined:
            return joined
    except Exception:
        pass
    # Fallback lightweight PDF text literal extractor for uncompressed streams
    decoded = raw.decode("latin-1", errors="ignore")
    chunks = re.findall(r"\(([^()\\]{3,200})\)", decoded)
    cleaned = [re.sub(r"\s+", " ", c).strip() for c in chunks if re.search(r"[A-Za-z]{3,}", c)]
    if cleaned:
        return " ".join(cleaned[:400])
    # Fallback printable ASCII strings
    ascii_runs = re.findall(r"[A-Za-z0-9 ,.;:?!'\"/\-\(\)\[\]=+_]{12,}", decoded)
    return "\n".join(ascii_runs[:200])


def extract_document_text(
    filename: str | None = None,
    content_base64: str | None = None,
    text: str | None = None,
    raw: bytes | None = None,
) -> dict:
    """Extract readable text and a concise summary from an uploaded file or text payload.

    The content can come as plain text, as base64 (browser upload) or as raw bytes.
    """
    fname = (filename or "document.txt").strip()
    lower = fname.lower()
    extracted = (text or "").strip()

    if not extracted and (content_base64 or raw is not None):
        if raw is None:
            b64 = content_base64.strip()
            if "," in b64 and b64.split(",", 1)[0].startswith("data:"):
                b64 = b64.split(",", 1)[1]
            try:
                raw = base64.b64decode(b64)
            except Exception as exc:
                raise WorkspaceError(400, "Could not decode the uploaded file.") from exc
        if len(raw) > 8 * 1024 * 1024:
            raise WorkspaceError(400, "File is too large (maximum 8 MB).")
        try:
            if lower.endswith(".docx"):
                extracted = _extract_docx(raw)
            elif lower.endswith(".pptx"):
                extracted = _extract_pptx(raw)
            elif lower.endswith(".ipynb"):
                extracted = _extract_ipynb(raw)
            elif lower.endswith(".pdf"):
                extracted = _extract_pdf(raw)
            else:
                extracted = raw.decode("utf-8", errors="replace")
        except Exception:
            extracted = raw.decode("utf-8", errors="replace")

    extracted = re.sub(r"\r\n?", "\n", extracted)
    extracted = re.sub(r"[ \t]+", " ", extracted).strip()
    if not extracted:
        raise WorkspaceError(400, f"Could not extract readable text from '{fname}'. Try a text, code, markdown, DOCX, PPTX, IPYNB, or PDF file.")

    lines = [ln.strip() for ln in extracted.splitlines() if ln.strip()]
    summary = " ".join(lines[:4])[:360]
    words = re.findall(r"\S+", extracted)
    return {
        "filename": fname,
        "text": extracted[:12000],
        "summary": summary,
        "wordCount": len(words),
    }


# ===================================================================== Calendar + Meet ========
MEET_LINK_RE = re.compile(r"^https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}$")
MEET_NEW_URL = "https://meet.google.com/new"


def clean_meet_link(url: str | None) -> str | None:
    """A real Google Meet room link (https://meet.google.com/abc-defg-hij), or None."""
    link = (url or "").strip().split("?")[0].rstrip("/")
    if link.startswith("meet.google.com/"):
        link = "https://" + link
    return link if MEET_LINK_RE.match(link) else None


def parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat((value or "").strip().replace("Z", "+00:00"))
    except ValueError:
        return None


def one_hour_after(start: str) -> str:
    """End time for an event that only has a start: one hour later, in the same format."""
    dt = parse_time(start)
    if not dt:
        return start
    return (dt + timedelta(hours=1)).isoformat(timespec="minutes" if dt.second == 0 and len(start) <= 16 else "seconds")


def calendar_template_link(title: str, description: str, start: str, end: str, time_zone: str) -> str | None:
    """A link that opens Google Calendar with this event filled in, ready for the student to save.

    Used when no live Google sign-in is active: it needs no API access, only a signed-in browser.
    """
    s, e = parse_time(start), parse_time(end)
    if not s or not e:
        return None
    params = {"action": "TEMPLATE", "text": title, "details": description or ""}
    if s.tzinfo and e.tzinfo:
        fmt = "%Y%m%dT%H%M%SZ"
        params["dates"] = f"{s.astimezone(timezone.utc).strftime(fmt)}/{e.astimezone(timezone.utc).strftime(fmt)}"
    else:
        fmt = "%Y%m%dT%H%M%S"
        params["dates"] = f"{s.strftime(fmt)}/{e.strftime(fmt)}"
        params["ctz"] = time_zone
    return "https://calendar.google.com/calendar/render?" + urlparse.urlencode(params)


# ===================================================================== Seeded Workspace =======
STARTER_VERSION = 3
# Sample files from earlier builds that covered topics outside the six modules in the concept graph.
def _migrate_workspace(ws: dict, now_iso: str) -> None:
    """Bring a workspace saved by an earlier build up to date.

    Earlier builds stored made-up Meet codes and generic Drive/Docs home-page links. Those are
    removed: a link is only kept when it was returned by Google (item marked live) or, for a Meet
    room, pasted in by a circle member.
    """
    if ws.get("starterVersion") == STARTER_VERSION:
        return
    for d in ws.get("docs") or []:
        if not d.get("live"):
            d["url"] = None
            d["live"] = False
    own = ws.get("email")
    for ev in ws.get("calendarEvents") or []:
        if not ev.get("live"):
            ev["live"] = False
            if not ev.get("meetLive"):
                ev["meetUrl"] = None
            if ev.get("id") == "gcal-seed-1":
                ev["attendees"] = [own] if own else []
                ev["sample"] = True
            ev.setdefault("calendarLink", None)
    for sp in ws.get("chatSpaces") or []:
        if not sp.get("meetLive"):
            sp["meetUrl"] = None
        if sp.get("id") == "gchat-seed-chain-rule":
            sp["sample"] = True
    for t in ws.get("tasks") or []:
        t.setdefault("live", False)
    ws["starterVersion"] = STARTER_VERSION


def ensure_workspace(user: dict) -> dict:
    """Ensure the user record has an initialized `googleWorkspace` state."""
    ws = user.get("googleWorkspace")
    now_iso = _iso()
    if not isinstance(ws, dict):
        ws = {}
    ws.setdefault("connected", True)
    ws.setdefault("email", user.get("email") or "")
    ws.setdefault("connectedAt", now_iso)
    ws.setdefault("mode", "workspace")
    enabled = ws.get("enabledServices")
    if not isinstance(enabled, dict):
        enabled = {}
    for s in SERVICES:
        enabled.setdefault(s, True)
    ws["enabledServices"] = enabled

    prefs = ws.get("preferences")
    if not isinstance(prefs, dict):
        prefs = {}
    prefs.setdefault("defaultReminderMinutes", 30)
    prefs.setdefault("autoCreateMeetForCircles", True)
    prefs.setdefault("autoSyncTasksFromDiagnosis", False)
    ws["preferences"] = prefs

    # The Drive feature was removed; files listed by earlier builds are dropped.
    fresh = "calendarEvents" not in ws
    ws.pop("driveFiles", None)
    if isinstance(ws.get("enabledServices"), dict):
        ws["enabledServices"].pop("drive", None)
    prefs.pop("driveFolderName", None)

    if "calendarEvents" not in ws or not isinstance(ws["calendarEvents"], list):
        tomorrow = (_now() + timedelta(days=1)).replace(hour=6, minute=0, second=0, microsecond=0)
        start, end = _iso(tomorrow), _iso(tomorrow + timedelta(hours=1))
        title = "Study session: Chain Rule practice"
        description = "Sample event. Review composite function derivatives before the gradient descent lab."
        ws["calendarEvents"] = [
            {
                "id": "gcal-seed-1",
                "title": title,
                "description": description,
                "startTime": start,
                "endTime": end,
                "location": "Library study room",
                "meetUrl": None,
                "conceptId": "CM-CHAIN",
                "attendees": [ws["email"]] if ws["email"] else [],
                "live": False,
                "sample": True,
                "calendarLink": calendar_template_link(title, description, start, end, "UTC"),
                "createdAt": now_iso,
            }
        ]

    if "tasks" not in ws or not isinstance(ws["tasks"], list):
        ws["tasks"] = [
            {
                "id": "gtask-seed-1",
                "title": "Run a diagnosis on the Gradient Descent lab",
                "notes": "Sample task. Upload the lab sheet in Diagnose and answer the 5 to 10 questions.",
                "due": (_now() + timedelta(days=2)).date().isoformat(),
                "completed": False,
                "completedAt": None,
                "conceptId": "CM-GRADDESC",
                "live": False,
                "sample": True,
                "createdAt": now_iso,
            },
            {
                "id": "gtask-seed-2",
                "title": "Pass the re-check on Matrix Multiplication to complete the stamp",
                "notes": "Sample task. Check that inner dimensions match: (m x k) times (k x n).",
                "due": (_now() + timedelta(days=3)).date().isoformat(),
                "completed": False,
                "completedAt": None,
                "conceptId": "CM-MATMUL",
                "live": False,
                "sample": True,
                "createdAt": now_iso,
            },
        ]

    if "docs" not in ws or not isinstance(ws["docs"], list):
        ws["docs"] = [
            {
                "id": "gdoc-seed-1",
                "title": "Study Notes: Chain Rule and Gradient Descent",
                "conceptId": "CM-CHAIN",
                "content": (
                    "# Chain Rule and Gradient Descent Study Notes\n\n"
                    "- **Outer times inner derivative**: if `y = f(g(x))`, then `dy/dx = f'(g(x)) * g'(x)`.\n"
                    "- **Matrix shapes**: row-by-column products need the inner dimensions to match.\n"
                    "- **Action item**: re-check partial derivatives before attempting gradient descent."
                ),
                "url": None,
                "live": False,
                "sample": True,
                "updatedAt": now_iso,
                "createdAt": now_iso,
            }
        ]

    if "chatSpaces" not in ws or not isinstance(ws["chatSpaces"], list):
        ws["chatSpaces"] = []

    if fresh:
        ws["starterVersion"] = STARTER_VERSION
    else:
        _migrate_workspace(ws, now_iso)

    user["googleWorkspace"] = ws
    return ws


def _require_service(ws: dict, service_name: str) -> None:
    if not ws.get("connected"):
        raise WorkspaceError(409, "Google Workspace is switched off for this account. Turn it on in the Google Workspace page.")
    if not ws.get("enabledServices", {}).get(service_name, True):
        raise WorkspaceError(409, f"Google {service_name.capitalize()} is switched off in your Workspace settings.")
