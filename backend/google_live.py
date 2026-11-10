"""Live Google calls made with the student's own Google sign-in (Drive, Calendar + Meet, Tasks, Docs).

How it works:
1. The browser asks Google Identity Services for a short-lived OAuth access token for the
   student's personal Gmail account (the address given at sign-up is passed as the login hint).
2. The browser sends that token to POST /api/google/connect.
3. While the token is valid, Workspace actions in Punca are also written to the student's real
   Google account, and the real links (Drive file, Doc, Calendar event, Meet room) are saved.

Tokens are held in memory only. They are never written to the store or the log, and they expire
after about an hour, after which the student reconnects with one click.

Live mode is switched on by setting GOOGLE_OAUTH_CLIENT_ID (see docs/google-setup.md). Without it
Punca keeps using its built-in workspace store.
"""
from __future__ import annotations

import html
import json
import re
import time
import uuid
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest

# drive.file only reaches files and folders that Punca itself creates in the student's Drive.
SCOPES = [
    "openid",
    "email",
    "profile",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/tasks",
]

DRIVE = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3"
CALENDAR = "https://www.googleapis.com/calendar/v3"
TASKS = "https://tasks.googleapis.com/tasks/v1"
USERINFO = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_DOC_MIME = "application/vnd.google-apps.document"
FOLDER_MIME = "application/vnd.google-apps.folder"


class GoogleLiveError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


def _urllib_transport(method: str, url: str, headers: dict, body: bytes | None) -> tuple[int, bytes]:
    req = urlrequest.Request(url, data=body, method=method, headers=headers)
    try:
        with urlrequest.urlopen(req, timeout=20.0) as resp:
            return resp.status, resp.read()
    except urlerror.HTTPError as exc:
        return exc.code, exc.read()
    except (urlerror.URLError, TimeoutError) as exc:
        raise GoogleLiveError(502, "Could not reach Google. Check the internet connection and try again.") from exc


def markdown_to_html(text: str) -> str:
    """Small Markdown subset (headings, bullets, bold, inline code) to HTML for Google Docs import."""
    out: list[str] = []
    in_list = False

    def inline(s: str) -> str:
        s = html.escape(s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        return re.sub(r"`(.+?)`", r"<code>\1</code>", s)

    for raw in (text or "").splitlines():
        line = raw.rstrip()
        bullet = re.match(r"^\s*[-*]\s+(.*)$", line)
        if bullet:
            if not in_list:
                out.append("<ul>")
                in_list = True
            out.append(f"<li>{inline(bullet.group(1))}</li>")
            continue
        if in_list:
            out.append("</ul>")
            in_list = False
        heading = re.match(r"^(#{1,3})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            out.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
        elif line.strip():
            out.append(f"<p>{inline(line)}</p>")
    if in_list:
        out.append("</ul>")
    return "<html><body>" + "".join(out) + "</body></html>"


class GoogleLive:
    """Per-user live Google sessions and the handful of API calls Punca needs."""

    def __init__(self, transport=None):
        self._transport = transport or _urllib_transport
        self._sessions: dict[str, dict] = {}

    # ---- sessions ---------------------------------------------------------------------------
    def connect(self, uid: str, access_token: str, expires_in: int | None = None) -> dict:
        token = (access_token or "").strip()
        if not token:
            raise GoogleLiveError(400, "Google did not return an access token. Try connecting again.")
        info = self._request(token, "GET", USERINFO)
        if not info.get("email"):
            raise GoogleLiveError(401, "Google did not confirm that sign-in. Try connecting again.")
        try:
            ttl = int(expires_in or 3600)
        except (TypeError, ValueError):
            ttl = 3600
        self._sessions[uid] = {
            "token": token,
            "expiresAt": time.time() + max(120, ttl) - 60,
            "email": info["email"],
            "name": info.get("name"),
            "folders": {},
        }
        return info

    def disconnect(self, uid: str) -> None:
        self._sessions.pop(uid, None)

    def session(self, uid: str) -> dict | None:
        s = self._sessions.get(uid)
        if s and s["expiresAt"] <= time.time():
            self._sessions.pop(uid, None)
            return None
        return s

    def is_live(self, uid: str) -> bool:
        return self.session(uid) is not None

    # ---- low-level --------------------------------------------------------------------------
    def _request(self, token: str, method: str, url: str, body: bytes | None = None,
                 content_type: str = "application/json; charset=UTF-8") -> dict:
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = content_type
        status, raw = self._transport(method, url, headers, body)
        data: dict = {}
        if raw:
            try:
                data = json.loads(raw.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                data = {}
        if status in (401, 403):
            detail = (data.get("error") or {}).get("message") if isinstance(data.get("error"), dict) else None
            raise GoogleLiveError(
                status,
                "Google refused the request"
                + (f" ({detail})" if detail else "")
                + ". Reconnect your Google account and allow Drive, Calendar and Tasks access.",
            )
        if status >= 400:
            detail = (data.get("error") or {}).get("message") if isinstance(data.get("error"), dict) else None
            raise GoogleLiveError(502, f"Google returned an error ({status}){': ' + detail if detail else ''}.")
        return data if isinstance(data, dict) else {}

    def _call(self, uid: str, method: str, url: str, payload: dict | None = None) -> dict:
        s = self.session(uid)
        if not s:
            raise GoogleLiveError(401, "Your Google connection has expired. Connect your Google account again.")
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        return self._request(s["token"], method, url, body)

    # ---- Drive ------------------------------------------------------------------------------
    def _folder_id(self, uid: str, name: str) -> str:
        s = self.session(uid)
        if not s:
            raise GoogleLiveError(401, "Your Google connection has expired. Connect your Google account again.")
        name = (name or "Punca Study Materials").split("/")[0].strip() or "Punca Study Materials"
        if name in s["folders"]:
            return s["folders"][name]
        escaped = name.replace("\\", "\\\\").replace("'", "\\'")
        query = urlparse.urlencode({
            "q": f"mimeType='{FOLDER_MIME}' and name='{escaped}' and trashed=false",
            "fields": "files(id,name)",
            "spaces": "drive",
        })
        found = self._call(uid, "GET", f"{DRIVE}/files?{query}").get("files") or []
        if found:
            folder_id = found[0]["id"]
        else:
            folder_id = self._call(uid, "POST", f"{DRIVE}/files?fields=id", {"name": name, "mimeType": FOLDER_MIME})["id"]
        s["folders"][name] = folder_id
        return folder_id

    def _multipart_upload(self, uid: str, metadata: dict, content: bytes, content_type: str) -> dict:
        s = self.session(uid)
        if not s:
            raise GoogleLiveError(401, "Your Google connection has expired. Connect your Google account again.")
        boundary = "punca-" + uuid.uuid4().hex
        body = b"".join([
            f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode(),
            json.dumps(metadata).encode("utf-8"),
            f"\r\n--{boundary}\r\nContent-Type: {content_type}\r\n\r\n".encode(),
            content,
            f"\r\n--{boundary}--\r\n".encode(),
        ])
        url = f"{DRIVE_UPLOAD}/files?uploadType=multipart&fields=id,name,webViewLink,mimeType"
        return self._request(s["token"], "POST", url, body, f"multipart/related; boundary={boundary}")

    def drive_upload(self, uid: str, name: str, content: bytes, mime_type: str, folder: str) -> dict:
        """Upload a file into the student's Punca folder in their own Drive."""
        metadata = {"name": name, "parents": [self._folder_id(uid, folder)]}
        return self._multipart_upload(uid, metadata, content, mime_type or "application/octet-stream")

    def drive_trash(self, uid: str, file_id: str) -> None:
        """Move a file Punca created to the Drive bin (recoverable for 30 days)."""
        self._call(uid, "PATCH", f"{DRIVE}/files/{urlparse.quote(file_id)}", {"trashed": True})

    # ---- Docs (created through Drive, which converts HTML into a Google Doc) -----------------
    def doc_create(self, uid: str, title: str, markdown: str, folder: str) -> dict:
        metadata = {"name": title, "mimeType": GOOGLE_DOC_MIME, "parents": [self._folder_id(uid, folder)]}
        return self._multipart_upload(uid, metadata, markdown_to_html(markdown).encode("utf-8"), "text/html")

    def doc_update(self, uid: str, file_id: str, title: str | None, markdown: str | None) -> None:
        s = self.session(uid)
        if not s:
            raise GoogleLiveError(401, "Your Google connection has expired. Connect your Google account again.")
        fid = urlparse.quote(file_id)
        if title:
            self._call(uid, "PATCH", f"{DRIVE}/files/{fid}", {"name": title})
        if markdown is not None:
            self._request(
                s["token"], "PATCH", f"{DRIVE_UPLOAD}/files/{fid}?uploadType=media",
                markdown_to_html(markdown).encode("utf-8"), "text/html",
            )

    # ---- Calendar + Meet --------------------------------------------------------------------
    def calendar_insert(self, uid: str, title: str, description: str, start: str, end: str,
                        time_zone: str, attendees: list[str], with_meet: bool,
                        reminder_minutes: int | None = None) -> dict:
        def when(value: str) -> dict:
            aware = bool(re.search(r"(Z|[+-]\d{2}:?\d{2})$", value))
            return {"dateTime": value} if aware else {"dateTime": value, "timeZone": time_zone}

        event: dict = {
            "summary": title,
            "description": description or "",
            "start": when(start),
            "end": when(end),
            "attendees": [{"email": a} for a in attendees],
        }
        if reminder_minutes is not None:
            event["reminders"] = {"useDefault": False, "overrides": [{"method": "popup", "minutes": int(reminder_minutes)}]}
        url = f"{CALENDAR}/calendars/primary/events"
        if with_meet:
            event["conferenceData"] = {
                "createRequest": {"requestId": uuid.uuid4().hex, "conferenceSolutionKey": {"type": "hangoutsMeet"}}
            }
            url += "?conferenceDataVersion=1"
        res = self._call(uid, "POST", url, event)
        return {"id": res.get("id"), "htmlLink": res.get("htmlLink"), "meetUrl": res.get("hangoutLink")}

    def calendar_delete(self, uid: str, event_id: str) -> None:
        self._call(uid, "DELETE", f"{CALENDAR}/calendars/primary/events/{urlparse.quote(event_id)}")

    # ---- Tasks ------------------------------------------------------------------------------
    @staticmethod
    def _task_body(title: str | None, notes: str | None, due: str | None, completed: bool | None) -> dict:
        body: dict = {}
        if title is not None:
            body["title"] = title
        if notes is not None:
            body["notes"] = notes
        if due:
            body["due"] = f"{due[:10]}T00:00:00.000Z"
        if completed is not None:
            body["status"] = "completed" if completed else "needsAction"
        return body

    def task_insert(self, uid: str, title: str, notes: str, due: str | None) -> dict:
        res = self._call(uid, "POST", f"{TASKS}/lists/@default/tasks", self._task_body(title, notes, due, None))
        return {"id": res.get("id")}

    def task_patch(self, uid: str, task_id: str, title: str | None = None, notes: str | None = None,
                   due: str | None = None, completed: bool | None = None) -> None:
        body = self._task_body(title, notes, due, completed)
        if body:
            self._call(uid, "PATCH", f"{TASKS}/lists/@default/tasks/{urlparse.quote(task_id)}", body)

    def task_delete(self, uid: str, task_id: str) -> None:
        self._call(uid, "DELETE", f"{TASKS}/lists/@default/tasks/{urlparse.quote(task_id)}")
