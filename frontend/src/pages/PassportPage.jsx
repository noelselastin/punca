import React, { useState } from 'react'
import { api } from '../api.js'
import { ErrorNote, Spinner, go, useAsync } from '../components/common.jsx'
import ConceptMap, { MapLegend } from '../components/ConceptMap.jsx'
import PassportCover, { Emblem } from '../components/PassportCover.jsx'
import ProbeCard from '../components/ProbeCard.jsx'

const fmt = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' }) : '')

function Visa({ c, onRecheck }) {
  if (c.state === 'stamped') {
    return (
      <div className="visa stamped">
        <div className="visa-head">
          <span className="visa-code">{c.conceptId}</span>
          {c.topicName && <span className="visa-topic">{c.topicName}</span>}
        </div>
        <div className="visa-name">{c.name}</div>
        <div className="stamp stamped" aria-label="Completed stamp">
          <span className="stamp-top">{c.renewedAt ? 'Renewed' : 'Completed'}</span>
          <span className="stamp-mid">PUNCA</span>
          <span className="stamp-date">{fmt(c.renewedAt || c.earnedAt)}</span>
        </div>
      </div>
    )
  }

  if (c.state === 'reentry') {
    return (
      <div className="visa reentry">
        <div className="visa-head">
          <span className="visa-code">{c.conceptId}</span>
          <span className="visa-badge reentry">Needs re-entry</span>
        </div>
        <div className="visa-name">{c.name}</div>
        <div className="stamp reentry" aria-label="Re-entry required stamp">
          <span className="stamp-top">Re-entry</span>
          <span className="stamp-mid">REQUIRED</span>
          <span className="stamp-date">Issued {fmt(c.earnedAt)}</span>
        </div>
        {c.canRecheck && (
          <button type="button" className="btn small visa-recheck-btn" onClick={() => onRecheck(c)}>
            Re-check to renew
          </button>
        )}
      </div>
    )
  }

  const label = {
    'entry-required': 'Entry required · root gap',
    shaky: 'In progress · 1 re-check away',
    solid: 'Solid · re-check to complete',
    untested: 'Not yet visited',
  }[c.state] || 'Not yet visited'

  const showRecheck = c.canRecheck && (c.state === 'entry-required' || c.state === 'shaky' || c.state === 'solid')

  return (
    <div className={`visa ${c.state}`}>
      <div className="visa-head">
        <span className="visa-code">{c.conceptId}</span>
        {c.topicName && <span className="visa-topic">{c.topicName}</span>}
      </div>
      <div className="visa-name">{c.name}</div>
      <div className="visa-mark">{label}</div>
      {showRecheck && (
        <button type="button" className="btn ghost small visa-recheck-btn" onClick={() => onRecheck(c)}>
          Re-check to stamp
        </button>
      )}
    </div>
  )
}

function InlinePassportRecheck({ concept, onClose, onUpdated }) {
  const [probe, setProbe] = useState(null)
  const [choice, setChoice] = useState(null)
  const [outcome, setOutcome] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const loadQuestion = async () => {
    setBusy(true)
    setError(null)
    setOutcome(null)
    setChoice(null)
    try {
      setProbe(await api('/recheck', { method: 'POST', body: { conceptId: concept.conceptId } }))
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  React.useEffect(() => {
    loadQuestion()
  }, [concept.conceptId])

  const submit = async (i) => {
    setBusy(true)
    setError(null)
    setChoice(i)
    try {
      const r = await api('/recheck/answer', {
        method: 'POST',
        body: { probeId: probe.probeId, choiceIndex: i },
      })
      setOutcome(r)
      onUpdated()
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="pp-recheck-drawer card">
      <div className="row between" style={{ marginBottom: '0.5rem' }}>
        <div>
          <span className="eyebrow">PASSPORT STAMP CHECK · {concept.conceptId}</span>
          <h3 className="h3" style={{ margin: '0.15rem 0 0' }}>
            {concept.state === 'reentry' ? `Renew stamp: ${concept.name}` : `Complete stamp: ${concept.name}`}
          </h3>
        </div>
        <button type="button" className="btn ghost small" onClick={onClose}>Close ×</button>
      </div>
      <p className="muted" style={{ marginTop: 0 }}>
        {concept.state === 'reentry'
          ? 'This stamp slipped below solid mastery. Pass a quick re-check to renew your completed stamp.'
          : 'Answer two short re-check questions in a row to turn this concept solid and earn your completed stamp.'}
      </p>
      <ErrorNote error={error} />
      {busy && !probe && <Spinner label="Loading re-check question" />}
      {probe && (
        <ProbeCard
          probe={probe}
          chosen={choice}
          busy={busy}
          onAnswer={submit}
          feedback={outcome ? { correct: outcome.correct, correctIndex: outcome.correctIndex, explanation: outcome.explanation } : null}
          eyebrow={`Re-check · ${concept.name}`}
        />
      )}
      {outcome && (
        <div className="recheck-result" style={{ marginTop: '0.75rem' }}>
          {outcome.stampEarned && (
            <div className="stamp-toast">
              <span className="mini-stamp">COP</span>
              <div><b>Stamp completed!</b> {outcome.conceptName} is now stamped in your Passport.</div>
            </div>
          )}
          {outcome.stampRenewed && (
            <div className="stamp-toast">
              <span className="mini-stamp">COP</span>
              <div><b>Stamp renewed!</b> {outcome.conceptName} is back in good standing in your Passport.</div>
            </div>
          )}
          <div className="row" style={{ marginTop: '0.6rem', gap: '0.5rem' }}>
            {!outcome.stampEarned && !outcome.stampRenewed && (
              <button type="button" className="btn primary small" onClick={loadQuestion} disabled={busy}>
                Another re-check question
              </button>
            )}
            <button type="button" className="btn ghost small" onClick={onClose}>
              Done
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function PassportPage({ catalog, welcome }) {
  const [pp, reloadPassport] = useAsync(() => api('/me/passport'), [])
  const [view, setView] = useState('pages')
  const [regionFilter, setRegionFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [recheckConcept, setRecheckConcept] = useState(null)

  if (pp.loading) return <Spinner label="Opening your passport" />
  if (pp.error) return <ErrorNote error={pp.error} />
  const p = pp.data
  const allConcepts = p.regions.flatMap((r) => r.concepts)
  const stateById = Object.fromEntries(allConcepts.map((c) => [c.id || c.conceptId, c.state]))
  const mapState = (id) => {
    const s = stateById[id]
    if (s === 'entry-required' || s === 'reentry') return 'gap'
    if (s === 'stamped') return 'solid'
    return s || 'untested'
  }
  const ws = p.googleWorkspace || {}
  const summary = p.stampSummary || {
    completed: allConcepts.filter((c) => c.state === 'stamped').length,
    reentry: allConcepts.filter((c) => c.state === 'reentry').length,
    entryRequired: allConcepts.filter((c) => c.state === 'entry-required').length,
    inProgress: allConcepts.filter((c) => c.state === 'shaky' || c.state === 'solid').length,
  }
  const untestedCount = allConcepts.filter((c) => c.state === 'untested').length

  const matchesStatus = (c) => {
    if (statusFilter === 'all') return true
    if (statusFilter === 'completed') return c.state === 'stamped'
    if (statusFilter === 'reentry') return c.state === 'reentry'
    if (statusFilter === 'entry-required') return c.state === 'entry-required'
    if (statusFilter === 'in-progress') return c.state === 'shaky' || c.state === 'solid'
    if (statusFilter === 'untested') return c.state === 'untested'
    return true
  }

  const baseRegions = regionFilter === 'all' ? p.regions : p.regions.filter((r) => r.name === regionFilter)
  const visibleRegions = baseRegions
    .map((r) => ({ ...r, concepts: r.concepts.filter(matchesStatus) }))
    .filter((r) => r.concepts.length > 0)

  return (
    <div className="passport-page">
      {welcome && (
        <div className="welcome card">
          <div>
            <div className="eyebrow">Passport issued</div>
            <h2 className="h2">Welcome aboard, {p.holder}. Your first completed stamp is 5–10 questions away.</h2>
            <p className="muted">Tell Punca where you’re stuck or upload your lab file from PC or Google Drive. It assesses your foundations and helps you fix the exact root gap.</p>
          </div>
          <button className="btn primary" onClick={() => go('diagnose')}>Find my first gap</button>
        </div>
      )}
      <div className="passport">
        <PassportCover
          style={p.style}
          holder={p.holder}
          holderNo={p.holderNo}
          module={p.module}
          programme={p.programme}
          university={p.university}
          studentId={p.studentId}
          year={p.year}
          focusLabs={p.focusLabs}
          stamps={p.stamps}
        />
        <div className="pp-actions">
          <button className="btn small" onClick={() => go('setup')}>Customise passport & photo</button>
          <button className="btn ghost small" onClick={() => go('workspace')}>
            Google Workspace ({ws.driveCount || 0} Drive files · {ws.openTasksCount || 0} Tasks · {ws.docsCount || 0} Docs)
          </button>
          <button className="btn ghost small" onClick={() => go('diagnose')}>Diagnose a lab or question</button>
        </div>

        <div className="pp-stamp-summary">
          <button
            type="button"
            className={`pp-stat-tile completed ${statusFilter === 'completed' ? 'active' : ''}`}
            onClick={() => setStatusFilter(statusFilter === 'completed' ? 'all' : 'completed')}
          >
            <span className="pp-stat-num">{summary.completed}</span>
            <span className="pp-stat-label">Completed by you</span>
            <span className="pp-stat-sub">Passed re-check stamps</span>
          </button>
          <button
            type="button"
            className={`pp-stat-tile reentry ${statusFilter === 'reentry' ? 'active' : ''}`}
            onClick={() => setStatusFilter(statusFilter === 'reentry' ? 'all' : 'reentry')}
          >
            <span className="pp-stat-num">{summary.reentry}</span>
            <span className="pp-stat-label">Needs re-entry</span>
            <span className="pp-stat-sub">Slipped stamps to renew</span>
          </button>
          <button
            type="button"
            className={`pp-stat-tile entry-required ${statusFilter === 'entry-required' ? 'active' : ''}`}
            onClick={() => setStatusFilter(statusFilter === 'entry-required' ? 'all' : 'entry-required')}
          >
            <span className="pp-stat-num">{summary.entryRequired}</span>
            <span className="pp-stat-label">Entry required</span>
            <span className="pp-stat-sub">Diagnosed root-cause gaps</span>
          </button>
          <button
            type="button"
            className={`pp-stat-tile in-progress ${statusFilter === 'in-progress' ? 'active' : ''}`}
            onClick={() => setStatusFilter(statusFilter === 'in-progress' ? 'all' : 'in-progress')}
          >
            <span className="pp-stat-num">{summary.inProgress}</span>
            <span className="pp-stat-label">In progress</span>
            <span className="pp-stat-sub">Shaky · 1 re-check away</span>
          </button>
          <button
            type="button"
            className={`pp-stat-tile untested ${statusFilter === 'untested' ? 'active' : ''}`}
            onClick={() => setStatusFilter(statusFilter === 'untested' ? 'all' : 'untested')}
          >
            <span className="pp-stat-num">{untestedCount}</span>
            <span className="pp-stat-label">Not visited yet</span>
            <span className="pp-stat-sub">Out of {allConcepts.length} concepts</span>
          </button>
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

        {recheckConcept && (
          <InlinePassportRecheck
            concept={recheckConcept}
            onClose={() => setRecheckConcept(null)}
            onUpdated={reloadPassport}
          />
        )}

        <div className="pp-tabs">
          <button className={view === 'pages' ? 'on' : ''} onClick={() => setView('pages')}>Passport visa pages ({p.regions.length} modules)</button>
          <button className={view === 'map' ? 'on' : ''} onClick={() => setView('map')}>Concept map view</button>
        </div>

        {view === 'pages' && (
          <>
            <div className="examples" style={{ marginBottom: '0.85rem' }}>
              <button
                type="button"
                className={`chip-btn ${regionFilter === 'all' && statusFilter === 'all' ? 'on' : ''}`}
                onClick={() => { setRegionFilter('all'); setStatusFilter('all') }}
              >
                All modules ({allConcepts.length})
              </button>
              {p.regions.map((r) => (
                <button
                  key={r.name}
                  type="button"
                  className={`chip-btn ${regionFilter === r.name ? 'on' : ''}`}
                  onClick={() => setRegionFilter(r.name)}
                >
                  {r.name} ({r.concepts.length})
                </button>
              ))}
              {statusFilter !== 'all' && (
                <button type="button" className="chip-btn" onClick={() => setStatusFilter('all')}>
                  Clear status filter ({statusFilter}) ×
                </button>
              )}
            </div>
            {visibleRegions.length === 0 ? (
              <div className="pp-next empty">No concepts match the selected filter.</div>
            ) : (
              visibleRegions.map((r, idx) => (
                <section key={r.name} className="pp-region pp-backpage">
                  <div className="pp-backpage-watermark" aria-hidden="true">
                    <Emblem name={p.style?.emblem || 'compass'} size={140} />
                  </div>
                  <header className="pp-backpage-header">
                    <div>
                      <span className="pp-backpage-code">VISAS · COMPLETED STAMPS & RE-ENTRY RECORD</span>
                      <h3>Region: {r.name}</h3>
                    </div>
                    <span className="pp-backpage-num">
                      PAGE {String(idx + 1).padStart(2, '0')} / {String(visibleRegions.length).padStart(2, '0')}
                    </span>
                  </header>
                  <div className="visas">
                    {r.concepts.map((c) => (
                      <Visa key={c.conceptId} c={c} onRecheck={(target) => setRecheckConcept(target)} />
                    ))}
                  </div>
                </section>
              ))
            )}
          </>
        )}
        {view === 'map' && (
          <div className="pp-map">
            <ConceptMap
              concepts={catalog.concepts}
              stateOf={mapState}
              highlight={p.next ? p.next.route.map((s) => s.id) : []}
              root={p.next && p.next.entryRequiredId}
              target={p.next && p.next.targetConceptId}
            />
            <MapLegend />
          </div>
        )}
      </div>
    </div>
  )
}
