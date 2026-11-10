import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import AvailabilityGrid from './AvailabilityGrid.jsx'
import { ErrorNote, Spinner, Toggle, useAsync } from './common.jsx'

export function CircleCard({ circle, onSendChat, onAddCalendar, onCircleUpdated, children }) {
  const [chatText, setChatText] = useState('')
  const [chatBusy, setChatBusy] = useState(false)
  const [calEvent, setCalEvent] = useState(null)
  const [meetUrl, setMeetUrl] = useState(circle.meetUrl || '')
  const [meetLive, setMeetLive] = useState(Boolean(circle.meetLive || circle.meetUrl))
  const [meetInput, setMeetInput] = useState('')
  const [editingMeet, setEditingMeet] = useState(false)
  const [meetBusy, setMeetBusy] = useState(false)
  const [meetError, setMeetError] = useState(null)

  useEffect(() => {
    setMeetUrl(circle.meetUrl || '')
    setMeetLive(Boolean(circle.meetLive || circle.meetUrl))
  }, [circle.meetUrl, circle.meetLive])

  const status =
    circle.status === 'proposal'
      ? 'Proposed peer circle'
      : circle.status === 'scheduled'
        ? 'Scheduled peer session'
        : 'Done'

  const submitChat = async (e) => {
    e.preventDefault()
    if (!chatText.trim() || !onSendChat) return
    setChatBusy(true)
    try {
      await onSendChat(circle.id, chatText.trim())
      setChatText('')
    } finally {
      setChatBusy(false)
    }
  }

  const handleCalendar = async () => {
    if (!onAddCalendar) return
    const ev = await onAddCalendar(circle.id)
    if (ev) {
      setCalEvent(ev)
      if (ev.meetUrl && !meetUrl) {
        setMeetUrl(ev.meetUrl)
        setMeetLive(true)
      }
    }
  }

  const saveMeetRoom = async (e) => {
    e.preventDefault()
    if (!meetInput.trim()) return
    setMeetBusy(true)
    setMeetError(null)
    try {
      const res = await api(`/circles/${circle.id}/meet`, {
        method: 'POST',
        body: { meetUrl: meetInput.trim() },
      })
      const updated = res.circle || res || {}
      setMeetUrl(updated.meetUrl || meetInput.trim())
      setMeetLive(true)
      setMeetInput('')
      setEditingMeet(false)
      if (onCircleUpdated) onCircleUpdated(updated)
    } catch (err) {
      setMeetError(err)
    } finally {
      setMeetBusy(false)
    }
  }

  const startMeetHref = circle.meetNewUrl || 'https://meet.google.com/new'

  return (
    <div className="circle-card">
      <div className="circle-head">
        <div>
          <div className="eyebrow">Peer study circle · Google Meet &amp; Chat</div>
          <h3>{circle.conceptName}</h3>
        </div>
        <span className={`chip circle-${circle.status}`}>{status}</span>
      </div>
      <div className="circle-facts">
        <div><span className="k">When</span><span className="v">{circle.slotLabel} (weekly shared free hour)</span></div>
        <div><span className="k">Format</span><span className="v">Student peer study circle</span></div>
        <div><span className="k">Members</span><span className="v">{circle.memberCount}: {(circle.members || []).join(', ')}</span></div>
        <div>
          <span className="k">Google Meet</span>
          <span className="v">
            {meetLive && meetUrl ? (
              <a href={meetUrl} target="_blank" rel="noreferrer">{meetUrl} ↗</a>
            ) : (
              <span className="muted">
                No room pinned yet — start one via{' '}
                <a href={startMeetHref} target="_blank" rel="noreferrer">meet.google.com/new ↗</a>{' '}
                and paste the room link below so all members share it.
              </span>
            )}
          </span>
        </div>
      </div>

      {circle.id !== 'proposal' && (
        <div className="actions left" style={{ marginTop: '0.6rem' }}>
          {meetLive && meetUrl ? (
            <>
              <a className="btn small primary" href={meetUrl} target="_blank" rel="noreferrer">
                📹 Join Google Meet ↗
              </a>
              <button
                type="button"
                className="btn ghost small"
                onClick={() => {
                  setMeetInput(meetUrl)
                  setEditingMeet(!editingMeet)
                }}
              >
                {editingMeet ? 'Cancel' : 'Change room link'}
              </button>
            </>
          ) : (
            <a className="btn small" href={startMeetHref} target="_blank" rel="noreferrer">
              📹 Start a Google Meet room ↗
            </a>
          )}
          {onAddCalendar && (
            <button type="button" className="btn ghost small" onClick={handleCalendar}>
              📅 + Add to Google Calendar
            </button>
          )}
          {calEvent && (calEvent.htmlLink || calEvent.calendarLink) && (
            <a
              className="btn small"
              href={calEvent.htmlLink || calEvent.calendarLink}
              target="_blank"
              rel="noreferrer"
            >
              Open in Google Calendar ↗
            </a>
          )}
        </div>
      )}

      {circle.id !== 'proposal' && (!meetLive || editingMeet) && (
        <form className="chat-input-row" style={{ marginTop: '0.55rem' }} onSubmit={saveMeetRoom}>
          <input
            type="url"
            value={meetInput}
            onChange={(e) => setMeetInput(e.target.value)}
            placeholder="Paste shared Google Meet room link (https://meet.google.com/abc-defg-hij)"
          />
          <button type="submit" className="btn small" disabled={meetBusy || !meetInput.trim()}>
            {meetBusy ? 'Saving…' : 'Save room link'}
          </button>
        </form>
      )}
      {meetError && <ErrorNote error={meetError} />}

      {calEvent && (
        <p className="fine" style={{ marginTop: '0.45rem' }}>
          <b>Added &ldquo;{calEvent.title}&rdquo; to your study calendar.</b>{' '}
          {(calEvent.htmlLink || calEvent.calendarLink) && (
            <a href={calEvent.htmlLink || calEvent.calendarLink} target="_blank" rel="noreferrer">
              Save to your Google Calendar ↗
            </a>
          )}
        </p>
      )}

      {circle.id !== 'proposal' && onSendChat && (
        <div className="circle-chat-box">
          <div className="label">Google Chat · Peer Circle Discussion (shared with all circle members)</div>
          <div className="circle-chat-messages">
            {(circle.messages || []).length === 0 ? (
              <p className="fine">No messages yet. Say hello to your study circle!</p>
            ) : (
              circle.messages.map((m) => (
                <div key={m.id} className="chat-msg">
                  <b>{m.sender}:</b> <span>{m.text}</span>
                </div>
              ))
            )}
          </div>
          <form className="chat-input-row" onSubmit={submitChat}>
            <input
              type="text"
              value={chatText}
              onChange={(e) => setChatText(e.target.value)}
              placeholder="Message your peer group in Google Chat..."
              maxLength={500}
            />
            <button type="submit" className="btn small" disabled={chatBusy || !chatText.trim()}>
              Send
            </button>
          </form>
        </div>
      )}

      {circle.note && <p className="fine">{circle.note}</p>}
      {children}
    </div>
  )
}

/** The "Connect" step for a diagnosed gap: peer suggestion, availability, consent and joining. */
export default function CirclePanel({ conceptId, user, onUser }) {
  const [state, reload] = useAsync(() => api(`/circles/suggestion?conceptId=${encodeURIComponent(conceptId)}`), [conceptId])
  const [avail, setAvail] = useState(user.availability || [])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const patch = async (body) => {
    const u = await api('/me', { method: 'PATCH', body })
    onUser(u)
    return u
  }
  const act = async (fn) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
      await reload()
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  const sendChat = async (circleId, text) => {
    await api(`/circles/${circleId}/chat`, { method: 'POST', body: { text } })
    await reload()
  }

  const addCalendar = async (circleId) => {
    const res = await api(`/circles/${circleId}/calendar`, { method: 'POST' })
    await reload()
    return res.event
  }

  if (state.loading) return <Spinner label="Looking for peers with the same gap" />
  if (state.error) return <ErrorNote error={state.error} />
  const s = state.data

  const consent = (
    <div className="consents">
      <Toggle
        checked={user.consent.shareNameWithCircle}
        label="Show my name to my study circle"
        hint="Otherwise you appear as 'Anonymous peer'."
        onChange={(v) => act(() => patch({ consent: { shareNameWithCircle: v } }))}
      />
    </div>
  )

  return (
    <div>
      {(s.status === 'need-availability' || s.status === 'not-enough') && (
        <>
          <p className="muted">
            {s.status === 'need-availability'
              ? 'Mark the hours you are usually free each week. Punca finds the overlap with other students who share this gap.'
              : s.message}
          </p>
          <AvailabilityGrid value={avail} onChange={setAvail} />
          <div className="actions">
            <button className="btn primary" disabled={busy} onClick={() => act(() => patch({ availability: avail }))}>
              Save my free hours
            </button>
          </div>
        </>
      )}
      {(s.status === 'proposal' || s.status === 'existing') && (
        <CircleCard circle={s.circle}>
          {consent}
          <p className="fine">Joining is opt-in and sets up a shared Google Chat space and Google Meet room for your group.</p>
          <div className="actions">
            <button
              className="btn primary"
              disabled={busy}
              onClick={() => act(() => api('/circles/join', { method: 'POST', body: { conceptId } }))}
            >
              {s.status === 'existing' ? 'Join this peer circle' : 'Create & join this peer circle'}
            </button>
          </div>
        </CircleCard>
      )}
      {s.status === 'member' && (
        <CircleCard circle={s.circle} onSendChat={sendChat} onAddCalendar={addCalendar} onCircleUpdated={() => reload()}>
          {consent}
        </CircleCard>
      )}
      <ErrorNote error={error} />
    </div>
  )
}
