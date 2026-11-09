import React, { useState } from 'react'
import { api } from '../api.js'
import AvailabilityGrid from '../components/AvailabilityGrid.jsx'
import { CircleCard } from '../components/CirclePanel.jsx'
import { ErrorNote, Spinner, Toggle, go, useAsync } from '../components/common.jsx'

export default function CirclesPage({ user, onUser }) {
  const [circles, reload] = useAsync(() => api('/circles'), [])
  const [avail, setAvail] = useState(user.availability || [])
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  const patch = async (body) => {
    setError(null)
    setSaved(false)
    try { onUser(await api('/me', { method: 'PATCH', body })); setSaved(true) } catch (e) { setError(e) }
  }
  const done = async (id) => {
    try { await api(`/circles/${id}/done`, { method: 'POST' }); reload() } catch (e) { setError(e) }
  }

  return (
    <div className="grid2 top">
      <div className="card">
        <h1 className="h2">My study circles</h1>
        {circles.loading && <Spinner />}
        <ErrorNote error={circles.error} />
        {circles.data && circles.data.length === 0 && (
          <p className="muted">No circles yet. After a diagnosis, Punca proposes a circle of students with the same gap. <a href="#/diagnose">Run a diagnosis</a>.</p>
        )}
        {circles.data && circles.data.map((c) => (
          <CircleCard key={c.id} circle={c}>
            {c.status !== 'done' && (
              <div className="actions left">
                <button className="btn small" onClick={() => done(c.id)}>We met: mark done</button>
                <button className="btn ghost small" onClick={() => go('passport')}>Re-check to earn the stamp</button>
              </div>
            )}
          </CircleCard>
        ))}
      </div>
      <div className="card">
        <h2 className="h2">My weekly free hours</h2>
        <p className="muted">Used only to find a time that works for your circle.</p>
        <AvailabilityGrid value={avail} onChange={(v) => { setAvail(v); setSaved(false) }} />
        <div className="actions left">
          <button className="btn primary" onClick={() => patch({ availability: avail })}>Save free hours</button>
          {saved && <span className="fine">Saved.</span>}
        </div>
        <h3 className="h3">Privacy</h3>
        <div className="consents">
          <Toggle checked={user.consent.joinCircles} label="Suggest me for study circles" hint="Opt-in. Off means you are never grouped."
            onChange={(v) => patch({ consent: { joinCircles: v } })} />
          <Toggle checked={user.consent.shareNameWithCircle} label="Show my name to my circle" onChange={(v) => patch({ consent: { shareNameWithCircle: v } })} />
          <Toggle checked={user.consent.shareNameWithLecturer} label="Show my name to lecturers" onChange={(v) => patch({ consent: { shareNameWithLecturer: v } })} />
        </div>
        <ErrorNote error={error} />
      </div>
    </div>
  )
}
