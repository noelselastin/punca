import React, { useState } from 'react'
import { api } from '../api.js'
import { ErrorNote, Spinner, Toggle, go, useAsync } from '../components/common.jsx'
import ConceptMap, { MapLegend } from '../components/ConceptMap.jsx'

const fmt = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' }) : '')

function Visa({ c }) {
  if (c.state === 'stamped' || c.state === 'endorsed') {
    return (
      <div className={`visa stamped ${c.state}`}>
        <div className="visa-name">{c.name}</div>
        <div className={`stamp ${c.state}`} aria-label={c.state === 'endorsed' ? 'Endorsed stamp' : 'Verified stamp'}>
          <span className="stamp-top">{c.state === 'endorsed' ? 'Endorsed' : 'Verified'}</span>
          <span className="stamp-mid">PUNCA</span>
          <span className="stamp-date">{fmt(c.endorsedAt || c.earnedAt)}</span>
        </div>
        {c.endorsedBy && <div className="countersign">Countersigned by {c.endorsedBy}</div>}
      </div>
    )
  }
  const label = {
    'entry-required': 'Entry required', shaky: 'Shaky · re-check to stamp', solid: 'Solid · re-check to stamp', untested: 'Not yet visited',
  }[c.state]
  return (
    <div className={`visa ${c.state}`}>
      <div className="visa-name">{c.name}</div>
      <div className="visa-mark">{label}</div>
    </div>
  )
}

export default function PassportPage({ catalog, user, onUser }) {
  const [pp, reload] = useAsync(() => api('/me/passport'), [])
  const [view, setView] = useState('pages')
  const [error, setError] = useState(null)

  if (pp.loading) return <Spinner label="Opening your passport" />
  if (pp.error) return <ErrorNote error={pp.error} />
  const p = pp.data
  const stateById = Object.fromEntries(p.regions.flatMap((r) => r.concepts.map((c) => [c.id || c.conceptId, c.state])))
  const mapState = (id) => {
    const s = stateById[id]
    return s === 'entry-required' ? 'gap' : s === 'stamped' || s === 'endorsed' ? 'solid' : s || 'untested'
  }

  const share = async (v) => {
    setError(null)
    try { onUser(await api('/me', { method: 'PATCH', body: { consent: { sharePassport: v } } })); reload() } catch (e) { setError(e) }
  }

  return (
    <div className="passport-page">
      <div className="passport">
        <div className="pp-cover">
          <div>
            <div className="pp-title">PUNCA PASSPORT</div>
            <div className="pp-sub">Pasport Punca · study aid, not a grade or credential</div>
          </div>
          <div className="pp-holder">
            <div><span>Holder</span><b>{p.holder}</b></div>
            <div><span>No.</span><b>{p.holderNo}</b></div>
            <div><span>Module</span><b>{p.module}</b></div>
          </div>
          <div className="pp-count"><b>{p.stamps}</b><span>stamps</span><b>{p.endorsed}</b><span>endorsed</span></div>
        </div>

        {p.next ? (
          <div className="pp-next">
            <div><span className="label">Next destination</span><b>{p.next.targetName}</b></div>
            <div><span className="label">Entry required</span><b className="gap-text">{p.next.entryRequired}</b></div>
            <div className="route">
              <span className="label">Route</span>
              {p.next.route.map((s, i) => (
                <React.Fragment key={s.id}>{i > 0 && <span className="arrow">→</span>}<span className={`route-stop ${s.stamped ? 'stamped' : ''}`}>{s.name}</span></React.Fragment>
              ))}
            </div>
            <button className="btn small" onClick={() => go('diagnosis', p.next.diagnosisId)}>Open this route</button>
          </div>
        ) : (
          <div className="pp-next empty">No open route. Run a diagnosis when you get stuck and your next destination will appear here.</div>
        )}

        <div className="pp-tabs">
          <button className={view === 'pages' ? 'on' : ''} onClick={() => setView('pages')}>Passport pages</button>
          <button className={view === 'map' ? 'on' : ''} onClick={() => setView('map')}>Map view</button>
        </div>

        {view === 'pages' && p.regions.map((r) => (
          <section key={r.name} className="pp-region">
            <h3>Region: {r.name}</h3>
            <div className="visas">{r.concepts.map((c) => <Visa key={c.conceptId} c={c} />)}</div>
          </section>
        ))}
        {view === 'map' && (
          <div className="pp-map">
            <ConceptMap concepts={catalog.concepts} stateOf={mapState} highlight={p.next ? p.next.route.map((s) => s.id) : []}
              root={p.next && p.next.entryRequiredId} target={p.next && p.next.targetConceptId} />
            <MapLegend />
          </div>
        )}
      </div>

      <div className="card share-card">
        <Toggle checked={user.consent.sharePassport} onChange={share} label="Share my passport with lecturers"
          hint="Off by default. When on, lecturers see your stamps with your name. No leaderboards, ever." />
        <ErrorNote error={error} />
        <p className="fine">Stamps come only from passed re-checks. A lecturer can countersign a stamp after a circle session or consultation.</p>
      </div>
    </div>
  )
}
