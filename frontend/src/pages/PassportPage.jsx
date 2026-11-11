import React, { useState } from 'react'
import { api } from '../api.js'
import { ErrorNote, Spinner, go, useAsync } from '../components/common.jsx'
import ConceptMap, { MapLegend } from '../components/ConceptMap.jsx'
import PassportCover, { Emblem } from '../components/PassportCover.jsx'
import ProbeCard from '../components/ProbeCard.jsx'

const fmt = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' }) : '')

// What each passport state shows on its visa: the ink mark, the line under it, and the action.
const VISA_STATES = {
  stamped: { action: null },
  reentry: { action: 'Re-check to renew' },
  'entry-required': { mark: 'Entry required', sub: 'Gap found', action: 'Re-check to stamp' },
  shaky: { mark: 'In progress', sub: '1 re-check away', action: 'Re-check to stamp' },
  solid: { mark: 'Solid', sub: 'Re-check to complete', action: 'Re-check to stamp' },
  untested: { action: null },
}

function Visa({ c, onRecheck }) {
  const meta = VISA_STATES[c.state] || VISA_STATES.untested
  return (
    <div className={`visa ${c.state}`}>
      <div className="visa-head">
        <span className="visa-code">{c.conceptId}</span>
        {c.topicName && <span className="visa-topic">{c.topicName}</span>}
      </div>
      <div className="visa-name">{c.name}</div>
      <div className="visa-body">
        {c.state === 'stamped' && (
          <div className="stamp stamped" aria-label="Completed stamp">
            <span className="stamp-top">{c.renewedAt ? 'Renewed' : 'Completed'}</span>
            <span className="stamp-mid">PUNCA</span>
            <span className="stamp-date">{fmt(c.renewedAt || c.earnedAt)}</span>
          </div>
        )}
        {c.state === 'reentry' && (
          <div className="stamp reentry" aria-label="Re-entry required stamp">
            <span className="stamp-top">Re-entry</span>
            <span className="stamp-mid">REQUIRED</span>
            <span className="stamp-date">Issued {fmt(c.earnedAt)}</span>
          </div>
        )}
        {meta.mark && (
          <div className={`visa-mark ${c.state}`}>
            <b>{meta.mark}</b>
            <small>{meta.sub}</small>
          </div>
        )}
        {c.state === 'untested' && <span className="visa-untested">Not yet visited</span>}
      </div>
      {meta.action && c.canRecheck && (
        <button type="button" className="visa-recheck-btn" onClick={() => onRecheck(c)}>
          {meta.action}
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
  // Counted from the same list the filters use, so a tile's number always matches what it shows.
  const countOf = (...states) => allConcepts.filter((c) => states.includes(c.state)).length
  const summary = {
    completed: countOf('stamped'),
    reentry: countOf('reentry'),
    entryRequired: countOf('entry-required'),
    inProgress: countOf('shaky', 'solid'),
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
            <p className="muted">Tell Punca where you’re stuck or upload your lab file from your PC. It assesses your foundations and helps you fix the exact root gap.</p>
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
          <button className="btn ghost small" onClick={() => go('profile')}>Edit profile</button>
          <button className="btn ghost small" onClick={() => go('workspace')}>
            Google Workspace ({ws.calendarCount || 0} sessions · {ws.openTasksCount || 0} tasks · {ws.docsCount || 0} docs)
          </button>
          <button className="btn ghost small" onClick={() => go('diagnose')}>Diagnose a lab or question</button>
        </div>

        <div className="pp-stamp-summary">
          {[
            ['completed', 'completed', summary.completed, 'Completed by you', 'Stamps you earned'],
            ['reentry', 'reentry', summary.reentry, 'Needs re-entry', 'Slipped stamps to renew'],
            ['entry-required', 'entry', summary.entryRequired, 'Entry required', 'Gaps to close'],
            ['in-progress', 'progress', summary.inProgress, 'In progress', 'Re-check to complete'],
            ['untested', 'untested', untestedCount, 'Not visited yet', `Out of ${allConcepts.length} concepts`],
          ].map(([key, cls, count, label, sub]) => (
            <button
              key={key}
              type="button"
              className={`pp-stat-tile ${cls} ${statusFilter === key ? 'on' : ''}`}
              aria-pressed={statusFilter === key}
              onClick={() => setStatusFilter(statusFilter === key ? 'all' : key)}
            >
              <b>{count}</b>
              <span>{label}</span>
              <small>{sub}</small>
            </button>
          ))}
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
                  Clear filter ×
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
