"""Moodle LMS connectivity for Punca (APU Moodle Web Services + slide/material import).

Supports:
1. Live public Moodle configuration inspection via `tool_mobile_get_public_config`
   (verifying `enablewebservices`, `enablemobilewebservice`, and identity providers such as Microsoft OAuth).
2. Authenticated Moodle Web Service REST syncing (`core_webservice_get_site_info`,
   `core_enrol_get_users_courses`, `core_course_get_contents`, `mod_assign_get_assignments`).
3. One-click APU Moodle sample feed (`apu-demo` mode) modeled on actual APU Moodle modules
   (`CT127-3-2-PFDA-092026-KLT`, lecture slide folders `PFDA_Lecture01.pptx`–`PFDA_Lecture_7.pptx`,
   and assignment deadlines) so students or reviewers can test syncing without generating a live token.
4. Direct import and text extraction for downloaded Moodle `.pptx` slide decks and `.txt`/`.md` notes.
"""
from __future__ import annotations

import base64
import html
import io
import ipaddress
import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import datetime, timedelta, timezone

log = logging.getLogger("punca.moodle")

DEFAULT_MOODLE_URL = "https://lms2.apiit.edu.my"
USER_AGENT = "PuncaStudyAssistant/0.1 (+https://github.com/noelselastin/study-assistant)"


class MoodleError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat(timespec="seconds")


def normalize_base_url(url: str | None) -> str:
    raw = (url or DEFAULT_MOODLE_URL).strip().rstrip("/")
    if not raw:
        raw = DEFAULT_MOODLE_URL
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    parsed = urllib.parse.urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise MoodleError(400, "Enter a valid Moodle URL such as https://lms2.apiit.edu.my.")
    host = (parsed.hostname or "").lower()
    if host in ("localhost", "127.0.0.1", "::1"):
        raise MoodleError(400, "Use a public Moodle hostname such as https://lms2.apiit.edu.my.")
    try:
        ip = ipaddress.ip_address(host)
        if ip.is_private or ip.is_loopback or ip.is_link_local:
            raise MoodleError(400, "Private network addresses are not allowed for Moodle connections.")
    except ValueError:
        pass
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}".rstrip("/")


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = html.unescape(cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def mask_token(token: str | None) -> str | None:
    if not token:
        return None
    t = token.strip()
    if len(t) <= 6:
        return "••••"
    return f"••••{t[-4:]}"


def check_public_config(base_url: str | None = None, timeout: float = 6.0) -> dict:
    """Query Moodle's unauthenticated mobile public config endpoint (`tool_mobile_get_public_config`)."""
    base = normalize_base_url(base_url)
    endpoint = f"{base}/lib/ajax/service-nologin.php?info=tool_mobile_get_public_config"
    payload = json.dumps([{
        "index": 0,
        "methodname": "tool_mobile_get_public_config",
        "args": {},
    }]).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
        if isinstance(body, list) and body and not body[0].get("error"):
            data = body[0].get("data") or {}
            providers = [
                {"name": p.get("name") or "SSO", "url": p.get("url")}
                for p in (data.get("identityproviders") or [])
            ]
            return {
                "baseUrl": base,
                "reachable": True,
                "siteName": strip_html(data.get("sitename")) or "APU Moodle",
                "enableWebServices": bool(int(data.get("enablewebservices", 0) or 0)),
                "enableMobileWebService": bool(int(data.get("enablemobilewebservice", 0) or 0)),
                "typeofLogin": data.get("typeoflogin"),
                "launchUrl": data.get("launchurl"),
                "identityProviders": providers,
                "checkedAt": _iso(),
            }
    except Exception as exc:
        log.warning("moodle public config check failed for %s: %s", base, exc)

    # Fallback snapshot if offline or blocked by local firewall
    is_apu = "apiit.edu.my" in base or "apu.edu.my" in base
    return {
        "baseUrl": base,
        "reachable": False,
        "siteName": "APU Online Learning (Moodle)" if is_apu else base,
        "enableWebServices": True if is_apu else False,
        "enableMobileWebService": True if is_apu else False,
        "typeofLogin": 2 if is_apu else None,
        "launchUrl": f"{base}/admin/tool/mobile/launch.php" if is_apu else None,
        "identityProviders": [{"name": "Microsoft", "url": f"{base}/auth/oauth2/login.php"}] if is_apu else [],
        "checkedAt": _iso(),
        "offlineFallback": True,
    }


def _call_ws(base_url: str, token: str, wsfunction: str, params: dict | None = None, timeout: float = 10.0):
    endpoint = f"{base_url}/webservice/rest/server.php"
    form_data: dict[str, str | int] = {
        "wstoken": token,
        "wsfunction": wsfunction,
        "moodlewsrestformat": "json",
    }
    if params:
        form_data.update(params)
    encoded = urllib.parse.urlencode(form_data, doseq=True).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=encoded,
        headers={"Content-Type": "application/x-www-form-urlencoded", "User-Agent": USER_AGENT},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.URLError as exc:
        raise MoodleError(502, f"Could not reach Moodle at {base_url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise MoodleError(502, "Moodle returned an unexpected response format.") from exc

    if isinstance(data, dict) and (data.get("exception") or data.get("errorcode")):
        code = data.get("errorcode") or ""
        msg = strip_html(data.get("message")) or "Moodle rejected the web service request."
        if code in ("invalidtoken", "accessexception"):
            raise MoodleError(401, f"Moodle token rejected ({msg}). Check your Security Key in Moodle Preferences.")
        raise MoodleError(400, f"Moodle API error: {msg}")
    return data


def sync_with_token(base_url: str, token: str) -> dict:
    """Fetch live courses, course materials, and assignment deadlines from Moodle REST API."""
    base = normalize_base_url(base_url)
    clean_token = (token or "").strip()
    if len(clean_token) < 8:
        raise MoodleError(400, "Enter a valid Moodle Security Key (web service token).")

    site_info = _call_ws(base, clean_token, "core_webservice_get_site_info")
    if not isinstance(site_info, dict) or not site_info.get("userid"):
        raise MoodleError(401, "Could not verify Moodle account with that Security Key.")

    userid = site_info["userid"]
    raw_courses = _call_ws(base, clean_token, "core_enrol_get_users_courses", {"userid": userid})
    if not isinstance(raw_courses, list):
        raw_courses = []

    courses: list[dict] = []
    materials: list[dict] = []
    for c in raw_courses[:6]:
        cid = c.get("id")
        cname = strip_html(c.get("fullname") or c.get("shortname") or f"Course {cid}")
        cshort = strip_html(c.get("shortname") or cname)
        courses.append({
            "id": str(cid),
            "code": cshort,
            "name": cname,
            "progress": c.get("progress"),
            "url": f"{base}/course/view.php?id={cid}",
        })
        try:
            sections = _call_ws(base, clean_token, "core_course_get_contents", {"courseid": cid})
        except MoodleError:
            sections = []
        if isinstance(sections, list):
            for sec in sections:
                sec_name = strip_html(sec.get("name") or "Topic")
                for mod in (sec.get("modules") or []):
                    modname = mod.get("modname") or ""
                    if modname not in ("resource", "folder", "page", "url", "assign"):
                        continue
                    mtitle = strip_html(mod.get("name") or "Resource")
                    mdesc = strip_html(mod.get("description") or "")
                    files = [
                        f.get("filename")
                        for f in (mod.get("contents") or [])
                        if f.get("filename")
                    ]
                    materials.append({
                        "id": f"moodle-mod-{mod.get('id')}",
                        "courseId": str(cid),
                        "courseName": cname,
                        "section": sec_name,
                        "kind": modname,
                        "title": mtitle,
                        "files": files[:8],
                        "summary": mdesc or (f"Files: {', '.join(files[:4])}" if files else f"{sec_name} · {mtitle}"),
                        "url": mod.get("url") or f"{base}/course/view.php?id={cid}",
                    })

    deadlines: list[dict] = []
    try:
        assign_data = _call_ws(base, clean_token, "mod_assign_get_assignments")
        if isinstance(assign_data, dict):
            for ac in (assign_data.get("courses") or []):
                cname = strip_html(ac.get("fullname") or ac.get("shortname") or "Course")
                for a in (ac.get("assignments") or []):
                    due_ts = a.get("duedate") or 0
                    due_iso = _iso(datetime.fromtimestamp(due_ts, tz=timezone.utc)) if due_ts else None
                    intro = strip_html(a.get("intro") or "")
                    deadlines.append({
                        "id": f"moodle-assign-{a.get('id')}",
                        "courseId": str(ac.get("id")),
                        "courseName": cname,
                        "title": strip_html(a.get("name") or "Assignment"),
                        "dueAt": due_iso,
                        "summary": intro[:280] or strip_html(a.get("name") or "Assignment"),
                        "url": f"{base}/mod/assign/view.php?id={a.get('cmid') or a.get('id')}",
                    })
    except MoodleError:
        pass

    return {
        "mode": "token",
        "baseUrl": base,
        "siteName": strip_html(site_info.get("sitename")) or "APU Moodle",
        "accountName": strip_html(site_info.get("fullname")) or site_info.get("username"),
        "username": site_info.get("username"),
        "moodleUserId": userid,
        "tokenMasked": mask_token(clean_token),
        "courses": courses,
        "materials": materials[:30],
        "deadlines": sorted(deadlines, key=lambda d: d.get("dueAt") or "9999")[:15],
        "syncedAt": _iso(),
    }


def build_apu_sample_snapshot(user: dict, base_url: str | None = None) -> dict:
    """Build a realistic APU Moodle sync snapshot matching APU's actual Moodle structure (`lms2.apiit.edu.my`)."""
    base = normalize_base_url(base_url or DEFAULT_MOODLE_URL)
    now = _now()
    student_id = user.get("studentId") or "TP099910"
    courses = [
        {
            "id": "ct127-pfda",
            "code": "CT127-3-2-PFDA-092026-KLT",
            "name": "Programming for Data Analysis (092026-KLT)",
            "progress": 64,
            "url": f"{base}/course/view.php?id=29412",
        },
        {
            "id": "ct098-mlnn",
            "code": "CT098-3-2-MLNN-092026-KLT",
            "name": "Machine Learning & Neural Networks (092026-KLT)",
            "progress": 48,
            "url": f"{base}/course/view.php?id=29488",
        },
        {
            "id": "ct045-foml",
            "code": "CT045-3-1-FOML-092026-KLT",
            "name": "Mathematical Foundations for AI & Data Science",
            "progress": 78,
            "url": f"{base}/course/view.php?id=29104",
        },
    ]
    materials = [
        {
            "id": "moodle-folder-1306651-w7",
            "courseId": "ct098-mlnn",
            "courseName": "Machine Learning & Neural Networks (092026-KLT)",
            "section": "Week 7 · Multi-Layer Perceptrons & Backpropagation",
            "kind": "folder",
            "title": "Lecture 07 Slides · Backpropagation & Chain Rule in Hidden Layers",
            "files": ["MLNN_Lecture_07_Backprop.pptx", "Lab_04_Gradient_Check.ipynb"],
            "summary": "Deriving gradients for hidden-layer weights using the multivariable chain rule, matrix transpose shapes in forward/backward pass, and vanishing gradients.",
            "url": f"{base}/mod/folder/view.php?id=1306651",
        },
        {
            "id": "moodle-folder-1306651-w5",
            "courseId": "ct098-mlnn",
            "courseName": "Machine Learning & Neural Networks (092026-KLT)",
            "section": "Week 5 · Classification & Probabilistic Losses",
            "kind": "folder",
            "title": "Lecture 05B · Logistic Regression, Softmax & Cross-Entropy Loss",
            "files": ["PFDA_Lecture_05B.pptx", "PFDA_Lecture_6.pptx"],
            "summary": "Why cross-entropy loss replaces MSE for classification, sigmoid saturation, log-likelihood, and gradient descent step size.",
            "url": f"{base}/mod/folder/view.php?id=1306651",
        },
        {
            "id": "moodle-folder-1306651-w4",
            "courseId": "ct127-pfda",
            "courseName": "Programming for Data Analysis (092026-KLT)",
            "section": "Lecture Slides Folder · Vectorised Data & Matrix Operations",
            "kind": "folder",
            "title": "PFDA Lecture 03–04 · Matrix Multiplication, Broadcasting & Eigenvalues",
            "files": ["PFDA_Lecture01.pptx", "PFDA_Lecture02.pptx", "PFDA_Lecture03.pptx", "PFDA_Lecture04.pptx"],
            "summary": "Inner dimension alignment in matrix multiplication (matmul shape mismatch), linear transformations, covariance matrices, and PCA.",
            "url": f"{base}/mod/folder/view.php?id=1306651",
        },
        {
            "id": "moodle-folder-1306651-w6",
            "courseId": "ct045-foml",
            "courseName": "Mathematical Foundations for AI & Data Science",
            "section": "Week 6 · Bayesian Inference & Conditional Probability",
            "kind": "resource",
            "title": "PFDA Lecture 06–07 · Bayes' Theorem, Prior vs Posterior & Independence",
            "files": ["PFDA_Lecture_6.pptx", "PFDA_Lecture_7.pptx"],
            "summary": "Computing posterior probabilities with Bayes' theorem, marginalisation over hypotheses, conditional independence, and base-rate fallacy.",
            "url": f"{base}/mod/folder/view.php?id=1306651",
        },
    ]
    deadlines = [
        {
            "id": "moodle-assign-mlnn-lab4",
            "courseId": "ct098-mlnn",
            "courseName": "Machine Learning & Neural Networks (092026-KLT)",
            "title": "Lab 4 Submission · Two-Layer Neural Network Backpropagation from Scratch",
            "dueAt": _iso(now + timedelta(days=4)),
            "summary": "Implement forward pass and backpropagation gradients for hidden layer weights without autograd, verify shapes, and plot cross-entropy loss convergence.",
            "url": f"{base}/mod/assign/view.php?id=1309102",
        },
        {
            "id": "moodle-assign-pfda-part1",
            "courseId": "ct127-pfda",
            "courseName": "Programming for Data Analysis (092026-KLT)",
            "title": "Individual Assignment · Exploratory Data Analysis & Bayesian Classification",
            "dueAt": _iso(now + timedelta(days=9)),
            "summary": "Apply Bayes' theorem posterior updates, covariance matrix decomposition, and vectorised matrix operations on the APU student dataset.",
            "url": f"{base}/mod/assign/view.php?id=1306890",
        },
        {
            "id": "moodle-assign-foml-quiz2",
            "courseId": "ct045-foml",
            "courseName": "Mathematical Foundations for AI & Data Science",
            "title": "In-Course Assessment 2 · Partial Derivatives, Jacobian & Gradient Descent",
            "dueAt": _iso(now + timedelta(days=12)),
            "summary": "Chain rule across composite functions, directional derivatives, and why learning rate overshoots local minima.",
            "url": f"{base}/mod/assign/view.php?id=1304115",
        },
    ]
    return {
        "mode": "apu-demo",
        "baseUrl": base,
        "siteName": "APU Online Learning (Moodle)",
        "accountName": f"{user.get('name')} ({student_id})",
        "username": f"{student_id.lower()}@mail.apu.edu.my",
        "moodleUserId": student_id,
        "tokenMasked": "APU-SSO-DEMO",
        "courses": courses,
        "materials": materials,
        "deadlines": deadlines,
        "syncedAt": _iso(now),
    }


def extract_pptx_text(raw_bytes: bytes) -> list[str]:
    """Extract slide text in order from a `.pptx` file using standard-library zipfile + ElementTree."""
    try:
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            slide_names = sorted(
                [n for n in zf.namelist() if re.match(r"^ppt/slides/slide\d+\.xml$", n)],
                key=lambda n: int(re.findall(r"\d+", n)[-1]),
            )
            slides: list[str] = []
            for sname in slide_names[:40]:
                xml_bytes = zf.read(sname)
                root = ET.fromstring(xml_bytes)
                texts = [elem.text.strip() for elem in root.iter() if elem.tag.endswith("}t") and elem.text and elem.text.strip()]
                if texts:
                    slides.append(" ".join(texts))
            return slides
    except (zipfile.BadZipFile, ET.ParseError, KeyError) as exc:
        raise MoodleError(400, "Could not read that .pptx file. Make sure it is a valid PowerPoint slide deck.") from exc


def parse_imported_material(
    title: str | None,
    course_name: str | None,
    filename: str | None,
    content_base64: str | None,
    text: str | None,
) -> dict:
    """Extract text from an uploaded Moodle slide deck (`.pptx`, `.txt`, `.md`) or pasted notes."""
    fname = (filename or "").strip()
    extracted_parts: list[str] = []
    if text and text.strip():
        extracted_parts.append(text.strip())

    if content_base64:
        b64 = content_base64.strip()
        if "," in b64 and b64.startswith("data:"):
            b64 = b64.split(",", 1)[1]
        try:
            raw = base64.b64decode(b64, validate=False)
        except Exception as exc:
            raise MoodleError(400, "Uploaded file encoding was invalid.") from exc
        if len(raw) > 8 * 1024 * 1024:
            raise MoodleError(400, "Uploaded file must be under 8 MB.")
        lower = fname.lower()
        if lower.endswith(".pptx") or raw[:4] == b"PK\x03\x04":
            slides = extract_pptx_text(raw)
            if not slides:
                raise MoodleError(400, "No readable slide text was found in that .pptx file.")
            extracted_parts.append(" | ".join(f"Slide {i + 1}: {s}" for i, s in enumerate(slides)))
        else:
            decoded = raw.decode("utf-8", errors="replace").strip()
            if decoded:
                extracted_parts.append(decoded)

    combined = re.sub(r"\s+", " ", " ".join(extracted_parts)).strip()
    if len(combined) < 5:
        raise MoodleError(400, "Upload a Moodle .pptx/.txt/.md file or paste slide/assignment text (at least 5 characters).")

    clean_title = (title or "").strip() or fname or combined[:60]
    clean_course = (course_name or "").strip() or "Imported Moodle Material"
    return {
        "title": clean_title[:120],
        "courseName": clean_course[:120],
        "filename": fname or None,
        "summary": combined[:500],
        "fullText": combined[:2000],
    }
