import React, { useState } from 'react'
import { api } from '../api.js'
import { CircleCard } from '../components/CirclePanel.jsx'
import { DAYS, HOURS } from '../components/AvailabilityGrid.jsx'
import { ErrorNote, Spinner, useAsync } from '../components/common.jsx'

function SlotForm({ catalog, onCreated }) {
  const [f, setF] = useState({ day: 'Mon', start: 14, end: 15, capacity: 6, kind: 'consultation', linked: [] })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const toggle = (id) => setF({ ...f, linked: f.linked.includes(id) ? f.linked.filter((x) => x !== id) : [...f.linked, id] })
  const submit = async (e) => {
    e.preventDefault()
    setBusy(true); setError(null)
    try {
      await api('/lecturer/slots', { method: 'POST', body: { day: f.day, start: +f.start, end: +f.end, capacity: +f.capacity, kind: f.kind, linkedConceptIds: f.linked } })
      setF({ ...f, linked: [] })
      onCreated()
    } catch (err) { setError(err) } finally { setBusy(false) }
  }
  const areas = [...new Set(catalog.concepts.map((c) => c.area))]
  return (
    <form className="slot-form" onSubmit={submit}>
      <div className="row4">
        <label>Day<select value={f.day} onChange={(e) => setF({ ...f, day: e.target.value })}>{DAYS.map((d) => <option key={d}>{d}</option>)}</select></label>
        <label>From<select value={f.start} onChange={(e) => setF({ ...f, start: e.target.value })}>{HOURS.map((h) => <option key={h} value={h}>{h}:00</option>)}</select></label>
        <label>To<select value={f.end} onChange={(e) => setF({ ...f, end: e.target.value })}>{[...HOURS.slice(1), 18].map((h) => <option key={h} value={h}>{h}:00</option>)}</select></label>
        <label>Seats<input type="number" min="1" max="50" value={f.capacity} onChange={(e) => setF({ ...f, capacity: e.target.value })} /></label>
      </div>
      <label>Type<select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}><option value="consultation">Consultation</option><option value="gap-clinic">Gap clinic</option></select></label>
      <div className="label">Linked concepts ({f.linked.length})</div>
      <div className="concept-pick">
        {areas.map((a) => (
          <div key={a}><span className="fine">{a}</span>
            <div className="examples">{catalog.concepts.filter((c) => c.area === a).map((c) => (
              <button type="button" key={c.id} className={`chip-btn small ${f.linked.includes(c.id) ? 'on' : ''}`} onClick={() => toggle(c.id)}>{c.name}</button>
            ))}</div>
          </div>
        ))}
      </div>
      <ErrorNote error={error} />
      <div className="actions left"><button className="btn primary" disabled={busy}>Publish slot</button></div>
    </form>
  )
}

export default function LecturerPage({ catalog }) {
  const [ov, reload] = useAsync(() => api('/lecturer/overview'), [])
  const [msg, setMsg] = useState(null)
  const [error, setError] = useState(null)

  const act = async (fn, okMsg) => {
    setError(null); setMsg(null)
    try { const r = await fn(); setMsg(typeof okMsg === 'function' ? okMsg(r) : okMsg); await reload() } catch (e) { setError(e) }
  }

  if (ov.loading) return <Spinner label="Loading cohort overview" />
  if (ov.error) return <ErrorNote error={ov.error} />
  const o = ov.data
  const maxCell = Math.max(1, ...o.heatmap.rows.flatMap((r) => Object.values(r.cells).filter((v) => v != null)))

  return (
    <div className="lecturer">
      {o.syntheticData && <div className="banner">Demo cohort: every figure on this page comes from synthetic students. Counts below {o.minCount} are hidden.</div>}
      {msg && <div className="ok-note">{msg}</div>}
      <ErrorNote error={error} />

      <div className="stats">
        <div className="stat"><b>{o.stats.studentsWithOpenGaps}</b><span>students with an open gap</span></div>
        <div className="stat"><b>{o.stats.diagnosesLast14Days}</b><span>diagnoses in the last 14 days</span></div>
        <div className="stat"><b>{o.requests.length}</b><span>circles waiting for you</span></div>
      </div>

      <div className="grid2 top">
        <div className="card">
          <h2 className="h2">Demand</h2>
          <p className="fine">Counts only. Names appear only when a student opts in.</p>
          <ul className="demand">
            {o.demand.map((d) => (
              <li key={d.conceptId}>
                <div><b>{d.students} students</b> need a <b>{d.conceptName}</b> refresher{d.labName ? <> before <b>{d.labName.split(':')[0]}</b></> : ''}.</div>
                <button className="btn small" onClick={() => act(() => api('/lecturer/clinic', { method: 'POST', body: { conceptId: d.conceptId } }),
                  (r) => `Gap clinic opened for ${d.conceptName}: ${r.slotLabel} (${r.studentsFree} opted-in students are free then).`)}>Open gap clinic</button>
              </li>
            ))}
          </ul>
          {o.hiddenDemandGroups > 0 && <p className="fine">{o.hiddenDemandGroups} smaller gap group(s) hidden (fewer than {o.minCount} students).</p>}
        </div>

        <div className="card">
          <h2 className="h2">Circles requesting your slots</h2>
          {o.requests.length === 0 && <p className="muted">No pending requests.</p>}
          {o.requests.map((c) => (
            <CircleCard key={c.id} circle={c}>
              <div className="actions left">
                <button className="btn primary small" onClick={() => act(() => api(`/lecturer/circles/${c.id}/confirm`, { method: 'POST' }), 'Session confirmed.')}>Confirm</button>
                <button className="btn ghost small" onClick={() => act(() => api(`/lecturer/circles/${c.id}/decline`, { method: 'POST' }), 'Declined: the circle will meet as a peer session.')}>Decline</button>
              </div>
            </CircleCard>
          ))}
          <h3 className="h3">Confirmed sessions</h3>
          {o.scheduled.length === 0 && <p className="muted">None yet.</p>}
          {o.scheduled.map((c) => (
            <CircleCard key={c.id} circle={c}>
              <p className="fine">Passport stamps in this circle: {c.stampsVerified} verified, {c.stampsEndorsed} countersigned.</p>
              <div className="actions left">
                <button className="btn small" disabled={c.stampsVerified === 0} onClick={() => act(() => api(`/lecturer/circles/${c.id}/endorse`, { method: 'POST' }),
                  (r) => `Countersigned ${r.endorsed} stamp(s). ${r.waitingForRecheck} member(s) still need to pass a re-check.`)}>Countersign verified stamps</button>
              </div>
            </CircleCard>
          ))}
        </div>
      </div>

      <div className="card">
        <h2 className="h2">Cohort heatmap: root-cause gaps behind each lab</h2>
        <div className="heat-wrap">
          <table className="heat">
            <thead><tr><th>Root cause</th>{o.heatmap.labs.map((l) => <th key={l.id} title={l.name}>{l.name.split(':')[0]}<small>{l.name.split(':')[1]}</small></th>)}</tr></thead>
            <tbody>
              {o.heatmap.rows.map((r) => (
                <tr key={r.conceptId}>
                  <th>{r.conceptName}</th>
                  {o.heatmap.labs.map((l) => {
                    const v = r.cells[l.id]
                    return <td key={l.id} style={v != null ? { '--h': v / maxCell } : undefined} className={v != null ? (v / maxCell > 0.45 ? 'v strong' : 'v') : 'hidden'}>{v != null ? v : '·'}</td>
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="fine">· = fewer than {o.minCount} (hidden for privacy). Exportable to BigQuery: backend/analytics/export_events.py.</p>
      </div>

      <div className="grid2 top">
        <div className="card">
          <h2 className="h2">My consultation slots</h2>
          {o.slots.length === 0 && <p className="muted">No slots yet.</p>}
          <ul className="slots">
            {o.slots.map((s) => (
              <li key={s.id}>
                <div><b>{s.label}</b> · {s.kind === 'gap-clinic' ? 'Gap clinic' : 'Consultation'} · {s.booked}/{s.capacity} seats requested</div>
                <div className="fine">{s.linkedNames.join(', ')}</div>
              </li>
            ))}
          </ul>
          <h3 className="h3">Publish a slot</h3>
          <SlotForm catalog={catalog} onCreated={() => { setMsg('Slot published.'); reload() }} />
        </div>
        <div className="card">
          <h2 className="h2">Shared passports</h2>
          <p className="fine">Only students who switched on "Share my passport with lecturers" appear here.</p>
          {o.sharedPassports.length === 0 && <p className="muted">No student has shared a passport yet.</p>}
          {o.sharedPassports.map((sp) => (
            <div key={sp.name} className="shared-pp">
              <b>{sp.name}</b>
              <div className="examples">{sp.stamps.map((s) => <span key={s.conceptName} className={`chip state-${s.tier === 'endorsed' ? 'endorsed' : 'stamped'}`}>{s.conceptName}</span>)}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
