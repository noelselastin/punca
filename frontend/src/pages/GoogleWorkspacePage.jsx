import React, { useState } from 'react'
import { api } from '../api.js'
import { ErrorNote, Spinner, Toggle, useAsync } from '../components/common.jsx'
import {
  GOOGLE_TASKS_URL,
  NEW_GOOGLE_DOC_URL,
  NEW_MEET_URL,
  copyToNewGoogleDoc,
  googleDocNote,
  openInNewTab,
} from '../googleLinks.js'

function addOneHourLocal(isoLocal) {
  if (!isoLocal) return ''
  const d = new Date(isoLocal)
  if (Number.isNaN(d.getTime())) return ''
  const end = new Date(d.getTime() + 60 * 60 * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${end.getFullYear()}-${pad(end.getMonth() + 1)}-${pad(end.getDate())}T${pad(end.getHours())}:${pad(end.getMinutes())}`
}

const EMPTY_SESSION = { title: '', description: '', startTime: '', endTime: '', attendeesText: '', meetUrl: '' }

export default function GoogleWorkspacePage() {
  const [ws, reload] = useAsync(() => api('/google/status'), [])
  const [tab, setTab] = useState('calendar')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  // { text, link?, linkLabel? }
  const [notice, setNotice] = useState(null)

  const [calForm, setCalForm] = useState(EMPTY_SESSION)

  const [docTitle, setDocTitle] = useState('')
  const [docContent, setDocContent] = useState('')
  const [editingDoc, setEditingDoc] = useState(null)

  const [spaceName, setSpaceName] = useState('')
  const [spaceMeetUrl, setSpaceMeetUrl] = useState('')
  const [chatInputs, setChatInputs] = useState({})
  const [spaceMeetInputs, setSpaceMeetInputs] = useState({})

  if (ws.loading) return <Spinner label="Loading Google Workspace" />
  if (ws.error) return <ErrorNote error={ws.error} />
  const data = ws.data
  const enabled = data.enabledServices || {}

  const act = async (fn, msg) => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await fn()
      await reload()
      if (msg) setNotice({ text: msg })
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  // Saves the session in Punca, then opens Google Calendar with it filled in, ready to save there.
  const createCalendarEvent = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const attendees = calForm.attendeesText
        .split(',')
        .map((x) => x.trim())
        .filter(Boolean)
      const res = await api('/google/calendar/events', {
        method: 'POST',
        body: {
          title: calForm.title,
          description: calForm.description,
          startTime: calForm.startTime || undefined,
          endTime: calForm.endTime || undefined,
          meetUrl: calForm.meetUrl.trim() || undefined,
          attendees,
        },
      })
      const ev = res.event
      const opened = openInNewTab(ev.calendarLink)
      setCalForm(EMPTY_SESSION)
      await reload()
      setNotice(
        opened
          ? { text: `Saved "${ev.title}" in Punca and opened it in Google Calendar. Press Save there to add it.` }
          : { text: `Saved "${ev.title}" in Punca.`, link: ev.calendarLink, linkLabel: 'Add it to Google Calendar ↗' },
      )
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const openDocInGoogle = async (doc) => {
    const result = await copyToNewGoogleDoc(doc.title, doc.content)
    setNotice({
      text: googleDocNote(doc.title, result),
      link: result.opened ? null : NEW_GOOGLE_DOC_URL,
      linkLabel: 'New Google Doc ↗',
    })
  }

  // Saves the note in Punca, then copies it and opens a new Google Doc to paste it into.
  const createDoc = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const res = await api('/google/docs', {
        method: 'POST',
        body: { title: docTitle, content: docContent },
      })
      const result = await copyToNewGoogleDoc(res.doc.title, res.doc.content)
      setDocTitle('')
      setDocContent('')
      await reload()
      setNotice({
        text: `Saved in Punca. ${googleDocNote(res.doc.title, result)}`,
        link: result.opened ? null : NEW_GOOGLE_DOC_URL,
        linkLabel: 'New Google Doc ↗',
      })
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const saveEditedDoc = (e) => {
    e.preventDefault()
    if (!editingDoc) return
    act(async () => {
      await api(`/google/docs/${editingDoc.id}`, {
        method: 'PATCH',
        body: { title: editingDoc.title, content: editingDoc.content },
      })
      setEditingDoc(null)
    }, 'Note updated in Punca.')
  }

  const createChatSpace = (e) => {
    e.preventDefault()
    act(async () => {
      await api('/google/chat/spaces', {
        method: 'POST',
        body: { name: spaceName, meetUrl: spaceMeetUrl.trim() || undefined },
      })
      setSpaceName('')
      setSpaceMeetUrl('')
    }, 'Discussion space created.')
  }

  const saveCircleMeetFromSpace = (circleId, spaceId) => {
    const raw = (spaceMeetInputs[spaceId] || '').trim()
    if (!raw) return
    act(async () => {
      await api(`/circles/${circleId}/meet`, {
        method: 'POST',
        body: { meetUrl: raw },
      })
      setSpaceMeetInputs((prev) => ({ ...prev, [spaceId]: '' }))
    }, 'Shared Google Meet link updated for your peer study circle!')
  }

  const postChatMessage = (spaceId) => {
    const txt = (chatInputs[spaceId] || '').trim()
    if (!txt) return
    act(async () => {
      await api(`/google/chat/spaces/${spaceId}/messages`, {
        method: 'POST',
        body: { text: txt },
      })
      setChatInputs((prev) => ({ ...prev, [spaceId]: '' }))
    })
  }

  const toggleService = (serviceKey, val) =>
    act(async () => {
      await api('/google/configure', {
        method: 'POST',
        body: { enabledServices: { [serviceKey]: val } },
      })
    }, 'Setting updated.')

  return (
    <div className="workspace-page">
      <div className="card hero-card">
        <div className="eyebrow">Google Workspace</div>
        <h1 className="h1">Your Google Study Workspace</h1>
        <p className="muted">
          Plan study sessions for <b>Google Calendar</b>, keep your to-do list in <b>Google Tasks</b>, meet your study
          circle on <b>Google Meet</b>, and keep notes in <b>Google Docs</b>. Punca keeps a copy here and opens each
          Google app in a new tab, in whichever Google account you are signed in to.
        </p>
        <div className="pp-tabs" style={{ marginTop: '1rem' }}>
          <button className={tab === 'calendar' ? 'on' : ''} onClick={() => setTab('calendar')}>
            Google Calendar ({(data.calendarEvents || []).length})
          </button>
          <button className={tab === 'tasks' ? 'on' : ''} onClick={() => setTab('tasks')}>
            Google Tasks
          </button>
          <button className={tab === 'chat' ? 'on' : ''} onClick={() => setTab('chat')}>
            Chat and Google Meet ({(data.chatSpaces || []).length})
          </button>
          <button className={tab === 'docs' ? 'on' : ''} onClick={() => setTab('docs')}>
            Google Docs ({(data.docs || []).length})
          </button>
          <button className={tab === 'settings' ? 'on' : ''} onClick={() => setTab('settings')}>
            Customize
          </button>
        </div>
        {notice && (
          <p className="fine" style={{ marginTop: '0.6rem' }}>
            <b>{notice.text}</b>
            {notice.link && (
              <>
                {' '}
                <a href={notice.link} target="_blank" rel="noreferrer">{notice.linkLabel}</a>
              </>
            )}
          </p>
        )}
        <ErrorNote error={error} />
      </div>

      {/* ---- GOOGLE CALENDAR ---- */}
      {tab === 'calendar' && (
        <div className="grid2 top">
          <div className="card">
            <div className="eyebrow">Google Calendar · Study &amp; Peer Group Sessions</div>
            <h2 className="h2">Upcoming Sessions</h2>
            {(data.calendarEvents || []).length === 0 ? (
              <p className="muted">No scheduled sessions yet. Plan one on the right or from Study Circles.</p>
            ) : (
              <div className="ws-list">
                {data.calendarEvents.map((ev) => (
                  <div key={ev.id} className="ws-item">
                    <div className="ws-item-main">
                      <div className="eyebrow">
                        {new Date(ev.startTime).toLocaleString()}
                        {ev.endTime ? ` – ${new Date(ev.endTime).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : ''}
                      </div>
                      <h3>{ev.title}</h3>
                      {ev.description && <p className="muted">{ev.description}</p>}
                      {ev.attendees && ev.attendees.length > 0 && (
                        <p className="fine">Participants: {ev.attendees.join(', ')}</p>
                      )}
                    </div>
                    <div className="actions left">
                      {ev.calendarLink && (
                        <a className={`btn small${ev.live ? '' : ' primary'}`} href={ev.calendarLink} target="_blank" rel="noreferrer">
                          {ev.live ? 'Open in Google Calendar ↗' : 'Add to Google Calendar ↗'}
                        </a>
                      )}
                      {ev.meetUrl ? (
                        <a className="btn small" href={ev.meetUrl} target="_blank" rel="noreferrer">
                          Join Google Meet ↗
                        </a>
                      ) : (
                        <a className="btn ghost small" href={NEW_MEET_URL} target="_blank" rel="noreferrer">
                          Start Google Meet ↗
                        </a>
                      )}
                      <button
                        type="button"
                        className="btn ghost small"
                        disabled={busy}
                        onClick={() => act(() => api(`/google/calendar/events/${ev.id}`, { method: 'DELETE' }), 'Removed the session from Punca.')}
                      >
                        Remove
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          <form className="card" onSubmit={createCalendarEvent}>
            <div className="eyebrow">Plan a Meeting</div>
            <h2 className="h2">Schedule in Google Calendar</h2>
            <label className="field">Session or Peer Meeting Title
              <input
                value={calForm.title}
                onChange={(e) => setCalForm({ ...calForm, title: e.target.value })}
                placeholder="e.g. Peer Study Session: Chain Rule (CM-CHAIN)"
                required
              />
            </label>
            <div className="row2">
              <label className="field">Start Date &amp; Time
                <input
                  type="datetime-local"
                  value={calForm.startTime}
                  onChange={(e) => {
                    const nextStart = e.target.value
                    const nextEnd = !calForm.endTime || calForm.endTime <= nextStart ? addOneHourLocal(nextStart) : calForm.endTime
                    setCalForm({ ...calForm, startTime: nextStart, endTime: nextEnd })
                  }}
                />
              </label>
              <label className="field">End Date &amp; Time <small>(defaults to +1 hr)</small>
                <input
                  type="datetime-local"
                  value={calForm.endTime}
                  onChange={(e) => setCalForm({ ...calForm, endTime: e.target.value })}
                />
              </label>
            </div>
            <label className="field">Peer email addresses <small>(comma-separated, optional)</small>
              <input
                value={calForm.attendeesText}
                onChange={(e) => setCalForm({ ...calForm, attendeesText: e.target.value })}
                placeholder="friend.one@example.com, friend.two@example.com"
              />
            </label>
            <label className="field">
              <span>
                Google Meet Room Link <small>(optional — <a href={NEW_MEET_URL} target="_blank" rel="noreferrer">start a room at meet.google.com/new ↗</a>)</small>
              </span>
              <input
                type="url"
                value={calForm.meetUrl}
                onChange={(e) => setCalForm({ ...calForm, meetUrl: e.target.value })}
                placeholder="https://meet.google.com/abc-defg-hij"
              />
            </label>
            <label className="field">Agenda / Notes
              <textarea
                rows={3}
                value={calForm.description}
                onChange={(e) => setCalForm({ ...calForm, description: e.target.value })}
                placeholder="What concepts or lab questions will the group cover?"
              />
            </label>
            <p className="fine">Google Calendar opens in a new tab with the session filled in. Press Save there to add it.</p>
            <div className="actions">
              <button className="btn primary" disabled={busy || !calForm.title.trim()}>
                Schedule Session
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ---- GOOGLE TASKS ---- */}
      {tab === 'tasks' && (
        <div className="card">
          <div className="eyebrow">Google Tasks · Study to-do list</div>
          <h2 className="h2">Keep your study to-do list in Google Tasks</h2>
          <p className="muted">
            Open Google Tasks and add the steps you want to remember there, for example each stop on the rebuild
            route from your latest diagnosis, and the re-check that earns your stamp. Tasks with a date also show up
            in Google Calendar.
          </p>
          <div className="actions left">
            <a className="btn primary" href={GOOGLE_TASKS_URL} target="_blank" rel="noreferrer">
              Open Google Tasks ↗
            </a>
          </div>
        </div>
      )}

      {/* ---- CHAT AND GOOGLE MEET ---- */}
      {tab === 'chat' && (
        <div className="grid2 top">
          <div className="card">
            <div className="eyebrow">Chat and Google Meet · peer discussions</div>
            <h2 className="h2">Discussion spaces</h2>
            {(data.chatSpaces || []).length === 0 && (
              <p className="muted">No spaces yet. Joining a study circle adds its chat here, or create a space on the right.</p>
            )}
            {(data.chatSpaces || []).map((sp) => (
              <div key={sp.id} className="circle-card" style={{ marginBottom: '1rem' }}>
                <div className="circle-head">
                  <div>
                    <div className="eyebrow">
                      {sp.circleId ? 'Study circle chat' : 'Discussion space'}
                    </div>
                    <h3>{sp.name}</h3>
                  </div>
                  <div className="actions left" style={{ marginTop: 0 }}>
                    {sp.meetUrl ? (
                      <a className="btn small primary" href={sp.meetUrl} target="_blank" rel="noreferrer">
                        Join Google Meet ↗
                      </a>
                    ) : (
                      <a className="btn small" href={sp.meetNewUrl || NEW_MEET_URL} target="_blank" rel="noreferrer">
                        Start Google Meet ↗
                      </a>
                    )}
                  </div>
                </div>
                {sp.circleId && !sp.meetUrl && (
                  <div className="chat-input-row" style={{ margin: '0.45rem 0' }}>
                    <input
                      type="url"
                      value={spaceMeetInputs[sp.id] || ''}
                      onChange={(e) => setSpaceMeetInputs({ ...spaceMeetInputs, [sp.id]: e.target.value })}
                      placeholder="Paste shared Meet link (https://meet.google.com/abc-defg-hij)"
                    />
                    <button
                      type="button"
                      className="btn small"
                      disabled={busy || !(spaceMeetInputs[sp.id] || '').trim()}
                      onClick={() => saveCircleMeetFromSpace(sp.circleId, sp.id)}
                    >
                      Save Meet Link
                    </button>
                  </div>
                )}
                <div className="circle-chat-messages">
                  {(sp.messages || []).map((m) => (
                    <div key={m.id} className="chat-msg">
                      <b>{m.sender}:</b> <span>{m.text}</span>
                    </div>
                  ))}
                </div>
                <form
                  className="chat-input-row"
                  onSubmit={(e) => {
                    e.preventDefault()
                    postChatMessage(sp.id)
                  }}
                >
                  <input
                    type="text"
                    value={chatInputs[sp.id] || ''}
                    onChange={(e) => setChatInputs({ ...chatInputs, [sp.id]: e.target.value })}
                    placeholder={`Message ${sp.name}...`}
                  />
                  <button type="submit" className="btn small" disabled={busy || !(chatInputs[sp.id] || '').trim()}>
                    Send
                  </button>
                </form>
              </div>
            ))}
          </div>

          <form className="card" onSubmit={createChatSpace}>
            <div className="eyebrow">Create Peer Discussion Space</div>
            <h2 className="h2">New discussion space</h2>
            <p className="muted">
              Create a dedicated space for your peer study group. Start a video room at{' '}
              <a href={NEW_MEET_URL} target="_blank" rel="noreferrer">meet.google.com/new ↗</a>{' '}
              and paste the link if you want it pinned to the space.
            </p>
            <label className="field">Space Name
              <input
                value={spaceName}
                onChange={(e) => setSpaceName(e.target.value)}
                placeholder="e.g. Java OOP & Polymorphism Study Group"
                required
              />
            </label>
            <label className="field">Google Meet Room Link <small>(optional)</small>
              <input
                type="url"
                value={spaceMeetUrl}
                onChange={(e) => setSpaceMeetUrl(e.target.value)}
                placeholder="https://meet.google.com/abc-defg-hij"
              />
            </label>
            <div className="actions">
              <a className="btn ghost small" href={NEW_MEET_URL} target="_blank" rel="noreferrer">
                Start a Meet room ↗
              </a>
              <button className="btn primary" disabled={busy || !spaceName.trim()}>
                Create Space
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ---- GOOGLE DOCS ---- */}
      {tab === 'docs' && (
        <div className="grid2 top">
          <div className="card">
            <div className="ws-section-head">
              <div>
                <div className="eyebrow">Google Docs · Study Notes &amp; Explanations</div>
                <h2 className="h2">Saved Study Docs</h2>
              </div>
              <a className="btn ghost small" href={NEW_GOOGLE_DOC_URL} target="_blank" rel="noreferrer">
                Blank Google Doc ↗
              </a>
            </div>
            {(data.docs || []).length === 0 && (
              <p className="muted">No notes yet. Write one on the right, or save the explanation from a diagnosis result.</p>
            )}
            {(data.docs || []).map((doc) => (
              <div key={doc.id} className="ws-item">
                <div className="ws-item-main">
                  <div className="eyebrow">Updated {new Date(doc.updatedAt).toLocaleString()}</div>
                  <h3>{doc.title}</h3>
                  <pre className="doc-preview">{doc.content}</pre>
                </div>
                <div className="actions left">
                  {doc.url ? (
                    <a className="btn small primary" href={doc.url} target="_blank" rel="noreferrer">
                      Open in Google Docs ↗
                    </a>
                  ) : (
                    <button type="button" className="btn small primary" onClick={() => openDocInGoogle(doc)}>
                      Copy into Google Docs ↗
                    </button>
                  )}
                  <button type="button" className="btn small" onClick={() => setEditingDoc({ ...doc })}>
                    Edit notes
                  </button>
                  <button
                    type="button"
                    className="btn ghost small"
                    disabled={busy}
                    onClick={() => act(() => api(`/google/docs/${doc.id}`, { method: 'DELETE' }), 'Deleted the note from Punca.')}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>

          {editingDoc ? (
            <form className="card" onSubmit={saveEditedDoc}>
              <div className="eyebrow">Editing Study Doc</div>
              <h2 className="h2">{editingDoc.title}</h2>
              <label className="field">Document Title
                <input
                  value={editingDoc.title}
                  onChange={(e) => setEditingDoc({ ...editingDoc, title: e.target.value })}
                  required
                />
              </label>
              <label className="field">Notes Content
                <textarea
                  rows={10}
                  value={editingDoc.content}
                  onChange={(e) => setEditingDoc({ ...editingDoc, content: e.target.value })}
                />
              </label>
              <div className="actions">
                <button type="button" className="btn ghost" onClick={() => setEditingDoc(null)}>
                  Cancel
                </button>
                <button className="btn primary" disabled={busy}>
                  Save changes
                </button>
              </div>
            </form>
          ) : (
            <form className="card" onSubmit={createDoc}>
              <div className="eyebrow">Create Study Document</div>
              <h2 className="h2">New Study Doc</h2>
              <label className="field">Document Title
                <input
                  value={docTitle}
                  onChange={(e) => setDocTitle(e.target.value)}
                  placeholder="e.g. Computational Maths · Chain Rule & Backpropagation Notes"
                  required
                />
              </label>
              <label className="field">Notes &amp; Formulas
                <textarea
                  rows={8}
                  value={docContent}
                  onChange={(e) => setDocContent(e.target.value)}
                  placeholder="Write your revision notes, code snippets, or key takeaways..."
                />
              </label>
              <p className="fine">Punca keeps the note, copies it, and opens a new Google Doc for you to paste it into.</p>
              <div className="actions">
                <button className="btn primary" disabled={busy || !docTitle.trim()}>
                  Save and open in Google Docs
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* ---- CUSTOMIZE ---- */}
      {tab === 'settings' && (
        <div className="card">
          <div className="eyebrow">Customize Enabled Services</div>
          <h2 className="h2">Google Workspace Modules</h2>
          <p className="muted">Choose which Google Workspace tools are active in your Punca account.</p>
          <div className="consents">
            <Toggle
              checked={enabled.calendar !== false}
              label="Google Calendar (Peer group & study session scheduling)"
              onChange={(v) => toggleService('calendar', v)}
            />
            <Toggle
              checked={enabled.chat !== false}
              label="Circle chat (study circle discussion threads)"
              onChange={(v) => toggleService('chat', v)}
            />
            <Toggle
              checked={enabled.meet !== false}
              label="Google Meet (Video meeting links for study circles)"
              onChange={(v) => toggleService('meet', v)}
            />
            <Toggle
              checked={enabled.docs !== false}
              label="Google Docs (Study notes & saved explanations)"
              onChange={(v) => toggleService('docs', v)}
            />
          </div>
        </div>
      )}
    </div>
  )
}
