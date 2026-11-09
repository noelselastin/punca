import React, { useState } from 'react'
import { api } from '../api.js'
import AvailabilityGrid from './AvailabilityGrid.jsx'
import { ErrorNote, Spinner, Toggle, useAsync } from './common.jsx'

export function CircleCard({ circle, children }) {
  const status = circle.status === 'proposal' ? 'Proposed'
    : circle.status === 'forming' ? `Waiting for ${circle.lecturerName || 'the lecturer'} to confirm`
      : circle.status === 'scheduled' ? (circle.mode === 'lecturer' ? `Confirmed with ${circle.lecturerName}` : 'Scheduled as a peer session')
        : 'Done'
  return (
    <div className="circle-card">
      <div className="circle-head">
        <div>
          <div className="eyebrow">Study circle · travel group</div>
          <h3>{circle.conceptName}</h3>
        </div>
        <span className={`chip circle-${circle.status}`}>{status}</span>
      </div>
      <div className="circle-facts">
        <div><span className="k">When</span><span className="v">{circle.slotLabel} (weekly free hour)</span></div>
        <div><span className="k">With</span><span className="v">{circle.mode === 'lecturer' ? `${circle.lecturerName} · ${circle.slotKind === 'gap-clinic' ? 'gap clinic' : 'consultation slot'}` : 'Peers only'}</span></div>
        <div><span className="k">Members</span><span className="v">{circle.memberCount}: {circle.members.join(', ')}</span></div>
      </div>
      {circle.note && <p className="fine">{circle.note}</p>}
      {children}
    </div>
  )
}

/** The "Connect" step for a diagnosed gap: suggestion, availability, consent and joining. */
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
    try { await fn(); await reload() } catch (e) { setError(e) } finally { setBusy(false) }
  }

  if (state.loading) return <Spinner label="Looking for students with the same gap" />
  if (state.error) return <ErrorNote error={state.error} />
  const s = state.data

  const consent = (
    <div className="consents">
      <Toggle checked={user.consent.shareNameWithCircle} label="Show my name to my circle" hint="Otherwise you appear as 'Anonymous student'."
        onChange={(v) => act(() => patch({ consent: { shareNameWithCircle: v } }))} />
      <Toggle checked={user.consent.shareNameWithLecturer} label="Show my name to the lecturer"
        onChange={(v) => act(() => patch({ consent: { shareNameWithLecturer: v } }))} />
    </div>
  )

  return (
    <div>
      {(s.status === 'need-availability' || s.status === 'not-enough') && (
        <>
          <p className="muted">{s.status === 'need-availability'
            ? 'Mark the hours you are usually free each week. Punca finds the overlap with other students who share this gap.'
            : s.message}</p>
          <AvailabilityGrid value={avail} onChange={setAvail} />
          <div className="actions"><button className="btn primary" disabled={busy} onClick={() => act(() => patch({ availability: avail }))}>Save my free hours</button></div>
        </>
      )}
      {(s.status === 'proposal' || s.status === 'existing') && (
        <CircleCard circle={s.circle}>
          {consent}
          <p className="fine">Joining is opt-in. Other members only see your name if you allow it above.</p>
          <div className="actions"><button className="btn primary" disabled={busy} onClick={() => act(() => api('/circles/join', { method: 'POST', body: { conceptId } }))}>
            {s.status === 'existing' ? 'Join this circle' : 'Join and request this slot'}</button></div>
        </CircleCard>
      )}
      {s.status === 'member' && <CircleCard circle={s.circle}>{consent}</CircleCard>}
      <ErrorNote error={error} />
    </div>
  )
}
