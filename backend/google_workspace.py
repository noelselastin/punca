"""Google Workspace integration & document text extraction for Punca.

Provides:
1. Document reader (`extract_document_text`) for PC uploads and Google Drive files
   (.pdf, .docx, .pptx, .ipynb, .py, .java, .sql, .md, .txt, .csv, .json).
2. The per-user Workspace state Punca keeps (`drive`, `calendar`, `tasks`, `chat`, `meet`, `docs`)
   with per-user settings (`enabledServices`, `preferences`). Live calls to the student's own
   Google account are in google_live.py; links are stored here only when Google returned them.
"""
from __future__ import annotations

import base64
import io
import json
import mimetypes
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


SERVICES = ("drive", "calendar", "tasks", "chat", "meet", "docs")


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
) -> dict:
    """Extract readable text and a concise summary from an uploaded file or text payload."""
    fname = (filename or "document.txt").strip()
    lower = fname.lower()
    extracted = (text or "").strip()

    if not extracted and content_base64:
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


# ===================================================================== Upload helpers =========
def decode_upload(content_base64: str | None) -> bytes | None:
    """Raw bytes of an uploaded file (accepts plain base64 or a data: URL)."""
    if not content_base64:
        return None
    b64 = content_base64.strip()
    if "," in b64 and b64.split(",", 1)[0].startswith("data:"):
        b64 = b64.split(",", 1)[1]
    try:
        return base64.b64decode(b64)
    except Exception:
        return None


def guess_mime(filename: str, fallback: str = "text/plain") -> str:
    extra = {
        ".md": "text/markdown", ".py": "text/x-python", ".java": "text/x-java-source",
        ".sql": "application/sql", ".ipynb": "application/x-ipynb+json",
    }
    lower = (filename or "").lower()
    for ext, mime in extra.items():
        if lower.endswith(ext):
            return mime
    return mimetypes.guess_type(filename or "")[0] or fallback


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
RETIRED_STARTER_IDS = {
    "gdrive-lab5-backprop", "gdrive-lab6-oop-recursion", "gdrive-lab7-dsa-graphs",
    "gdrive-lab8-sql-acid", "gdrive-lab9-networks-os",
}


def _starter_drive_files(now_iso: str) -> list[dict]:
    """Sample lab files, one or two per module in the concept graph, so a new account can try
    "pick a file" straight away. They live in Punca only and are marked as samples."""
    def sample(fid: str, name: str, mime: str, summary: str, content: str) -> dict:
        return {
            "id": fid,
            "name": name,
            "mimeType": mime,
            "folder": "Punca Study Materials / Samples",
            "sizeBytes": len(content.encode("utf-8")),
            "updatedAt": now_iso,
            "webViewLink": None,
            "live": False,
            "starter": True,
            "summary": summary,
            "content": content,
        }

    return [
        sample(
            "gdrive-sample-cm-graddesc",
            "CM_Lab7_Gradient_Descent.md",
            "text/markdown",
            "Computational Mathematics lab: minimise a function with gradient descent using partial derivatives and the chain rule.",
            "# Computational Mathematics Lab 7: Gradient Descent\n\n"
            "## Objective\n"
            "Minimise f(x, y) = (x - 3)^2 + (2y + 1)^2 with gradient descent.\n\n"
            "## Tasks\n"
            "1. Work out the partial derivatives df/dx and df/dy by hand.\n"
            "2. The second term is a composite function, so apply the chain rule: d/dy (2y + 1)^2 = 2(2y + 1) * 2.\n"
            "3. Implement the update step x = x - lr * df/dx, y = y - lr * df/dy and run 50 iterations.\n"
            "4. Explain what happens when the learning rate is too large.\n\n"
            "## Common stuck points\n"
            "- Forgetting the inner derivative when differentiating a function of a function.\n"
            "- Mixing up which variable is held constant in a partial derivative.",
        ),
        sample(
            "gdrive-sample-cm-matmul",
            "CM_Worksheet_Matrix_Multiplication.md",
            "text/markdown",
            "Computational Mathematics worksheet: matrix multiplication, dimension compatibility and vectors.",
            "# Computational Mathematics Worksheet: Matrix Multiplication\n\n"
            "1. A is a 2 x 3 matrix and B is a 3 x 4 matrix. State the shape of AB and explain why BA is undefined.\n"
            "2. Multiply the matrices [[1, 2], [3, 4]] and [[0, 1], [1, 0]] row by column.\n"
            "3. Show with an example that matrix multiplication is not commutative.\n"
            "4. Write the dot product of two vectors as a 1 x n matrix times an n x 1 matrix.\n\n"
            "Stuck point: I never know when the inner dimensions match, or which row goes with which column.",
        ),
        sample(
            "gdrive-sample-py-recursion",
            "PY_Lab4_Recursion.py",
            "text/x-python",
            "Introduction to Python lab: recursive functions, base cases and the call stack.",
            "# Introduction to Python Lab 4: Recursion\n"
            "def factorial(n):\n"
            "    # Task 1: add the base case. Without it the function calls itself forever.\n"
            "    return n * factorial(n - 1)\n\n"
            "def count_down(n):\n"
            "    # Task 2: trace the call stack for count_down(3) on paper.\n"
            "    if n == 0:\n"
            "        return\n"
            "    print(n)\n"
            "    count_down(n - 1)\n\n"
            "# Task 3: write a recursive function that sums a nested list such as [1, [2, 3], [4, [5]]].\n"
            "# Stuck point: I get RecursionError: maximum recursion depth exceeded and do not know why.",
        ),
        sample(
            "gdrive-sample-java-polymorphism",
            "JAVA_Lab5_Polymorphism_Shapes.java",
            "text/x-java-source",
            "Object Oriented Programming with Java lab: inheritance, method overriding and polymorphism.",
            "// Object Oriented Programming with Java Lab 5: Polymorphism\n"
            "abstract class Shape {\n"
            "    abstract double area();\n"
            "}\n\n"
            "class Circle extends Shape {\n"
            "    private final double r;\n"
            "    Circle(double r) { this.r = r; }\n"
            "    @Override double area() { return Math.PI * r * r; }\n"
            "}\n\n"
            "class Rectangle extends Shape {\n"
            "    private final double w, h;\n"
            "    Rectangle(double w, double h) { this.w = w; this.h = h; }\n"
            "    @Override double area() { return w * h; }\n"
            "}\n\n"
            "// Task: store a Circle and a Rectangle in a Shape[] array and print each area.\n"
            "// Explain which area() method runs for each element and why (dynamic dispatch).\n"
            "// Stuck point: I do not understand how a Shape variable can call the Circle version of area().",
        ),
        sample(
            "gdrive-sample-db-joins",
            "DB_Lab4_SQL_Joins.sql",
            "application/sql",
            "Introduction to Databases lab: INNER JOIN and LEFT JOIN across students and enrolments, with GROUP BY.",
            "-- Introduction to Databases Lab 4: SQL Joins\n"
            "-- Task 1: List ALL students and how many modules each is enrolled in (0 for students with none).\n"
            "SELECT s.student_id, s.name, COUNT(e.module_id) AS module_count\n"
            "FROM students s\n"
            "LEFT JOIN enrolments e ON s.student_id = e.student_id\n"
            "GROUP BY s.student_id, s.name;\n\n"
            "-- Task 2: Rewrite Task 1 with INNER JOIN and explain which students disappear and why.\n"
            "-- Task 3: Join students, enrolments and modules to list each student's module titles.\n"
            "-- Stuck point: my INNER JOIN drops students with no enrolments and I cannot see why.",
        ),
    ]


def _migrate_workspace(ws: dict, now_iso: str) -> None:
    """Bring a workspace saved by an earlier build up to date.

    Earlier builds stored made-up Meet codes and generic Drive/Docs home-page links. Those are
    removed: a link is only kept when it was returned by Google (item marked live) or, for a Meet
    room, pasted in by a circle member.
    """
    if ws.get("starterVersion") == STARTER_VERSION:
        return
    files = [f for f in ws.get("driveFiles") or [] if f.get("id") not in RETIRED_STARTER_IDS]
    have = {f.get("id") for f in files}
    files += [f for f in _starter_drive_files(now_iso) if f["id"] not in have]
    for f in files:
        if not f.get("live"):
            f["webViewLink"] = None
            f["live"] = False
    ws["driveFiles"] = files
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
    prefs.setdefault("driveFolderName", "Punca Study Materials")
    prefs.setdefault("defaultReminderMinutes", 30)
    prefs.setdefault("autoCreateMeetForCircles", True)
    prefs.setdefault("autoSyncTasksFromDiagnosis", False)
    ws["preferences"] = prefs

    fresh = "driveFiles" not in ws or not isinstance(ws["driveFiles"], list)
    if fresh:
        ws["driveFiles"] = _starter_drive_files(now_iso)

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
