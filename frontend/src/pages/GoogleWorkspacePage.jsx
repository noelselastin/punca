import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { ErrorNote, Spinner, Toggle, go, useAsync } from '../components/common.jsx'
import { GOOGLE_NOT_SET_UP, connectGoogle, ensureGoogle, prepareGoogle, savedWhere } from '../googleAuth.js'

function addOneHourLocal(isoLocal) {
  if (!isoLocal) return ''
  const d = new Date(isoLocal)
  if (Number.isNaN(d.getTime())) return ''
  const end = new Date(d.getTime() + 60 * 60 * 1000)
  const pad = (n) => String(n).padStart(2, '0')
  return `${end.getFullYear()}-${pad(end.getMonth() + 1)}-${pad(end.getDate())}T${pad(end.getHours())}:${pad(end.getMinutes())}`
}

export default function GoogleWorkspacePage() {
  const [ws, reload] = useAsync(() => api('/google/status'), [])
  useEffect(() => {
    prepareGoogle()
  }, [])
  const [tab, setTab] = useState('calendar')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  // Calendar form state
  const [calForm, setCalForm] = useState({
    title: '',
    description: '',
    startTime: '',
    endTime: '',
    attendeesText: '',
    meetUrl: '',
    includeMeet: true,
  })

  // Tasks form state
  const [taskTitle, setTaskTitle] = useState('')
  const [taskNotes, setTaskNotes] = useState('')
  const [taskDue, setTaskDue] = useState('')

  // Docs form state
  const [docTitle, setDocTitle] = useState('')
  const [docContent, setDocContent] = useState('')
  const [editingDoc, setEditingDoc] = useState(null)

  // Chat & Meet form state
  const [spaceName, setSpaceName] = useState('')
  const [spaceMeetUrl, setSpaceMeetUrl] = useState('')
  const [chatInputs, setChatInputs] = useState({})
  const [spaceMeetInputs, setSpaceMeetInputs] = useState({})

  // Customize form state
  const [oauthEmail, setOauthEmail] = useState('')
  const [oauthToken, setOauthToken] = useState('')

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
      if (msg) setNotice(msg)
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  const handleLiveGoogleConnect = () =>
    act(async () => {
      await connectGoogle(data)
    }, 'Google account connected. Calendar and Docs now use your own Google account.')

  const handleLiveGoogleDisconnect = () =>
    act(async () => {
      await api('/google/disconnect', { method: 'POST' })
    }, 'Google account disconnected. Your sessions, tasks and notes are still in Punca.')

  // Writing to the student's Google account needs a connection. Opens Google's window when sign-in
  // is set up; returns false (with an explanation on screen) when it is not available here.
  const ensureLive = async () => {
    const google = await ensureGoogle()
    if (google.state === 'connected') return true
    if (google.state === 'unavailable') setNotice(`${GOOGLE_NOT_SET_UP} Use the Open Google links for now.`)
    else if (google.error) throw google.error
    return false
  }

  const withGoogle = async (fn, msg) => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      if (await ensureLive()) {
        await fn()
        if (msg) setNotice(msg)
      }
      await reload()
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  const addEventToGoogle = (ev) =>
    withGoogle(
      () => api(`/google/calendar/events/${ev.id}/sync`, { method: 'POST' }),
      `Added "${ev.title}" to your Google Calendar.`,
    )

  const createCalendarEvent = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const google = await ensureGoogle()
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
          includeMeet: calForm.includeMeet,
          attendees,
        },
      })
      setCalForm({
        title: '',
        description: '',
        startTime: '',
        endTime: '',
        attendeesText: '',
        meetUrl: '',
        includeMeet: true,
      })
      await reload()
      setNotice(savedWhere('event', res.event, google, res.warning))
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  const createTask = (e) => {
    e.preventDefault()
    act(async () => {
      await api('/google/tasks', {
        method: 'POST',
        body: { title: taskTitle, notes: taskNotes, due: taskDue || undefined },
      })
      setTaskTitle('')
      setTaskNotes('')
      setTaskDue('')
    }, 'Task added to your study tasks.')
  }

  const toggleTask = (t) =>
    act(async () => {
      await api(`/google/tasks/${t.id}`, {
        method: 'PATCH',
        body: { completed: !t.completed },
      })
    })

  const createDoc = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      const google = await ensureGoogle()
      const res = await api('/google/docs', {
        method: 'POST',
        body: { title: docTitle, content: docContent },
      })
      setDocTitle('')
      setDocContent('')
      await reload()
      setNotice(savedWhere('doc', res.doc, google, res.warning))
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
    }, editingDoc.live ? 'Note updated here and in Google Docs.' : 'Note updated in Punca.')
  }

  const copyDocNotes = async (doc) => {
    try {
      await navigator.clipboard.writeText(`${doc.title}\n\n${doc.content || ''}`)
      setNotice(`Copied "${doc.title}" to clipboard — paste directly into Google Docs!`)
    } catch {
      setNotice('Could not copy automatically — select the text to copy.')
    }
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

  const saveCustomization = (e) => {
    e.preventDefault()
    act(async () => {
      const body = {}
      if (oauthEmail.trim()) body.email = oauthEmail.trim()
      if (oauthToken.trim()) body.accessToken = oauthToken.trim()
      await api('/google/configure', { method: 'POST', body })
      setOauthToken('')
    }, 'Workspace settings saved.')
  }

  return (
    <div className="workspace-page">
      <div className="card hero-card">
        <div className="ws-conn-bar">
          <div>
            <div className="eyebrow">
              Google Workspace Integration · Personal Gmail: <b>{data.email}</b>
            </div>
            <h1 className="h1">Your Google Study Workspace</h1>
          </div>
          <div className="ws-conn-actions">
            <span className={`chip ${data.liveConnected ? 'state-stamped' : 'state-endorsed'}`}>
              {data.liveConnected ? '● Google account connected' : '● Google account not connected'}
            </span>
            {data.liveAvailable && !data.liveConnected && (
              <button type="button" className="btn small primary" disabled={busy} onClick={handleLiveGoogleConnect}>
                Connect Google Account
              </button>
            )}
            {data.liveConnected && (
              <button type="button" className="btn ghost small" disabled={busy} onClick={handleLiveGoogleDisconnect}>
                Disconnect Google
              </button>
            )}
          </div>
        </div>
        <p className="muted">
          Schedule study sessions in <b>Google Calendar</b>, keep a study to-do list, talk to your study circle with chat and <b>Google Meet</b>, and keep notes in <b>Google Docs</b>.
        </p>
        <div className="pp-tabs" style={{ marginTop: '1rem' }}>
          <button className={tab === 'calendar' ? 'on' : ''} onClick={() => setTab('calendar')}>
            Google Calendar ({(data.calendarEvents || []).length})
          </button>
          <button className={tab === 'tasks' ? 'on' : ''} onClick={() => setTab('tasks')}>
            Study tasks ({(data.tasks || []).filter((t) => !t.completed).length} open)
          </button>
          <button className={tab === 'chat' ? 'on' : ''} onClick={() => setTab('chat')}>
            Chat and Google Meet ({(data.chatSpaces || []).length})
          </button>
          <button className={tab === 'docs' ? 'on' : ''} onClick={() => setTab('docs')}>
            Google Docs ({(data.docs || []).length})
          </button>
          <button className={tab === 'settings' ? 'on' : ''} onClick={() => setTab('settings')}>
            Customize &amp; Access
          </button>
        </div>
        {notice && <p className="fine" style={{ marginTop: '0.6rem' }}><b>{notice}</b></p>}
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
                      {ev.live ? (
                        <a className="btn small" href={ev.calendarLink} target="_blank" rel="noreferrer">
                          Open in Google Calendar ↗
                        </a>
                      ) : data.liveConnected ? (
                        <button type="button" className="btn small primary" disabled={busy} onClick={() => addEventToGoogle(ev)}>
                          Add to Google Calendar
                        </button>
                      ) : ev.calendarLink ? (
                        <a className="btn small primary" href={ev.calendarLink} target="_blank" rel="noreferrer">
                          Add to Google Calendar ↗
                        </a>
                      ) : null}
                      {ev.meetUrl ? (
                        <a className="btn small" href={ev.meetUrl} target="_blank" rel="noreferrer">
                          Join Google Meet ↗
                        </a>
                      ) : (
                        <a className="btn ghost small" href="https://meet.google.com/new" target="_blank" rel="noreferrer">
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
            <label className="field">Peer Gmail Addresses <small>(comma-separated, optional)</small>
              <input
                value={calForm.attendeesText}
                onChange={(e) => setCalForm({ ...calForm, attendeesText: e.target.value })}
                placeholder="friend.one@gmail.com, friend.two@gmail.com"
              />
            </label>
            <label className="field">
              <span>
                Google Meet Room Link <small>(optional — <a href="https://meet.google.com/new" target="_blank" rel="noreferrer">start a room at meet.google.com/new ↗</a>)</small>
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
            {data.liveConnected && (
              <Toggle
                checked={calForm.includeMeet}
                label="Create a Google Meet room for this session automatically"
                onChange={(v) => setCalForm({ ...calForm, includeMeet: v })}
              />
            )}
            <div className="actions">
              <button className="btn primary" disabled={busy || !calForm.title.trim()}>
                Schedule Session
              </button>
            </div>
          </form>
        </div>
      )}

      {/* ---- STUDY TASKS ---- */}
      {tab === 'tasks' && (
        <div className="grid2 top">
          <div className="card">
            <div className="ws-section-head">
              <div>
                <div className="eyebrow">Study to-do list</div>
                <h2 className="h2">My study tasks</h2>
              </div>
            </div>
            {(data.tasks || []).length === 0 ? (
              <p className="muted">No tasks yet. Add a task on the right or export a remediation route from a diagnosis result.</p>
            ) : (
              <div className="ws-list">
                {data.tasks.map((t) => (
                  <div key={t.id} className={`ws-item task-row ${t.completed ? 'task-done' : ''}`}>
                    <label className="task-check-label">
                      <input
                        type="checkbox"
                        checked={Boolean(t.completed)}
                        onChange={() => toggleTask(t)}
                      />
                      <div>
                        <b className={t.completed ? 'strike' : ''}>{t.title}</b>
                        {t.notes && <div className="fine">{t.notes}</div>}
                        {t.due && <div className="fine">Due: {t.due}</div>}
                      </div>
                    </label>
                    <button
                      type="button"
                      className="btn ghost small"
                      disabled={busy}
                      onClick={() => act(() => api(`/google/tasks/${t.id}`, { method: 'DELETE' }))}
                    >
                      Delete
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          <form className="card" onSubmit={createTask}>
            <div className="eyebrow">Add a to-do item</div>
            <h2 className="h2">New task</h2>
            <label className="field">Task title
              <input
                value={taskTitle}
                onChange={(e) => setTaskTitle(e.target.value)}
                placeholder="e.g. Complete re-check for Chain Rule"
                required
              />
            </label>
            <label className="field">Due date <small>(optional)</small>
              <input
                type="date"
                value={taskDue}
                onChange={(e) => setTaskDue(e.target.value)}
              />
            </label>
            <label className="field">Notes <small>(optional)</small>
              <textarea
                rows={3}
                value={taskNotes}
                onChange={(e) => setTaskNotes(e.target.value)}
                placeholder="Key steps or lab exercises to finish..."
              />
            </label>
            <div className="actions">
              <button className="btn primary" disabled={busy || !taskTitle.trim()}>
                Add task
              </button>
            </div>
          </form>
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
                      <a className="btn small" href={sp.meetNewUrl || 'https://meet.google.com/new'} target="_blank" rel="noreferrer">
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
              <a href="https://meet.google.com/new" target="_blank" rel="noreferrer">meet.google.com/new ↗</a>{' '}
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
              <a className="btn ghost small" href="https://meet.google.com/new" target="_blank" rel="noreferrer">
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
              <a className="btn ghost small" href="https://docs.google.com/document/create" target="_blank" rel="noreferrer">
                Blank Google Doc ↗
              </a>
            </div>
            {(data.docs || []).map((doc) => (
              <div key={doc.id} className="ws-item">
                <div className="ws-item-main">
                  <div className="eyebrow">Updated {new Date(doc.updatedAt).toLocaleString()}</div>
                  <h3>{doc.title}</h3>
                  <pre className="doc-preview">{doc.content}</pre>
                </div>
                <div className="actions left">
                  <button type="button" className="btn small" onClick={() => setEditingDoc({ ...doc })}>
                    Edit notes
                  </button>
                  <button type="button" className="btn ghost small" onClick={() => copyDocNotes(doc)}>
                    Copy notes
                  </button>
                  {doc.url && (
                    <a className="btn small primary" href={doc.url} target="_blank" rel="noreferrer">
                      Open in Google Docs ↗
                    </a>
                  )}
                  <button
                    type="button"
                    className="btn ghost small"
                    disabled={busy}
                    onClick={() => act(() => api(`/google/docs/${doc.id}`, { method: 'DELETE' }), 'Deleted Google Doc.')}
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
              <div className="actions">
                <button className="btn primary" disabled={busy || !docTitle.trim()}>
                  Create Study Doc
                </button>
              </div>
            </form>
          )}
        </div>
      )}

      {/* ---- CUSTOMIZE & ACCESS ---- */}
      {tab === 'settings' && (
        <div className="grid2 top">
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
                checked={enabled.tasks !== false}
                label="Study tasks (to-do list and remediation steps)"
                onChange={(v) => toggleService('tasks', v)}
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

          <form className="card" onSubmit={saveCustomization}>
            <div className="eyebrow">Account</div>
            <h2 className="h2">Personal Gmail &amp; OAuth Access</h2>
            <label className="field">Connected Personal Gmail Address
              <input
                type="email"
                value={oauthEmail}
                onChange={(e) => setOauthEmail(e.target.value)}
                placeholder={data.email || 'yourname@gmail.com'}
              />
            </label>
            <label className="field">Temporary Google access token <small>(testers only: connects your Google account without the sign-in window)</small>
              <input
                type="password"
                value={oauthToken}
                onChange={(e) => setOauthToken(e.target.value)}
                placeholder="ya29.a0..."
              />
            </label>
            <div className="actions">
              {data.liveAvailable && (
                <button type="button" className="btn ghost" disabled={busy} onClick={handleLiveGoogleConnect}>
                  Connect Google account
                </button>
              )}
              <button className="btn primary" disabled={busy}>
                Save Workspace Settings
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  )
}
