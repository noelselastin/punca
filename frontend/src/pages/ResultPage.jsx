import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../api.js'
import CirclePanel from '../components/CirclePanel.jsx'
import { ErrorNote, Spinner, StateChip, go, useAsync } from '../components/common.jsx'
import ConceptMap, { MapLegend } from '../components/ConceptMap.jsx'
import ProbeCard from '../components/ProbeCard.jsx'
import { ensureGoogle, prepareGoogle, savedWhere } from '../googleAuth.js'

const CONF_LABELS = {
  low: 'Guessing / Unsure',
  medium: 'Somewhat sure',
  high: 'Confident',
}

function Practice({ items }) {
  const [picked, setPicked] = useState({})
  return (
    <div className="practice">
      {items.map((p, n) => {
        const chosen = picked[p.probeId]
        const fb = chosen === undefined ? null : { correct: chosen === p.correctIndex, correctIndex: p.correctIndex, explanation: p.explanation }
        return (
          <div key={p.probeId} className="practice-item">
            <ProbeCard
              probe={p}
              chosen={chosen}
              feedback={fb}
              onAnswer={(i) => setPicked({ ...picked, [p.probeId]: i })}
              eyebrow={`Practice ${n + 1} · ${p.conceptName}`}
            />
          </div>
        )
      })}
    </div>
  )
}

function Recheck({ conceptId, conceptName, onDone }) {
  const [probe, setProbe] = useState(null)
  const [chosen, setChosen] = useState(null)
  const [result, setResult] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const begin = async () => {
    setBusy(true); setError(null); setResult(null); setChosen(null)
    try { setProbe(await api('/recheck', { method: 'POST', body: { conceptId } })) } catch (e) { setError(e) } finally { setBusy(false) }
  }
  const answer = async (i) => {
    setBusy(true); setChosen(i)
    try {
      const r = await api('/recheck/answer', { method: 'POST', body: { probeId: probe.probeId, choiceIndex: i } })
      setResult(r)
      onDone()
    } catch (e) { setError(e) } finally { setBusy(false) }
  }
  return (
    <div>
      {!probe && <button className="btn primary" disabled={busy} onClick={begin}>Re-check {conceptName}</button>}
      {probe && (
        <ProbeCard
          probe={probe}
          chosen={chosen}
          busy={busy}
          onAnswer={answer}
          feedback={result ? { correct: result.correct, correctIndex: result.correctIndex, explanation: result.explanation } : null}
          eyebrow={`Re-check · ${conceptName}`}
        />
      )}
      {result && (
        <div className="recheck-result">
          {result.stampEarned || result.stampRenewed ? (
            <div className="stamp-toast">
              <span className="mini-stamp">COP</span>
              <div>
                <b>{result.stampRenewed ? 'Stamp renewed.' : 'Stamp completed.'}</b> {conceptName} is now stamped in your passport.
              </div>
            </div>
          ) : (
            <p>
              Now: <StateChip state={result.status} /> {result.status !== 'solid' && '· one more passed re-check should get you there.'}
            </p>
          )}
          <div className="actions">
            {result.stampEarned || result.stampRenewed ? (
              <button className="btn" onClick={() => go('passport')}>Open my passport</button>
            ) : (
              <button className="btn" onClick={begin}>Another re-check</button>
            )}
          </div>
        </div>
      )}
      <ErrorNote error={error} />
    </div>
  )
}

export default function ResultPage({ id, catalog, user, onUser }) {
  const [d] = useAsync(() => api(`/diagnoses/${id}`), [id])
  const [m, reloadMastery] = useAsync(() => api('/me/mastery'), [id])
  const root = d.data && d.data.result && d.data.result.rootCauseConceptId
  const [rem] = useAsync(() => (root ? api(`/diagnoses/${id}/remediation`) : Promise.resolve(null)), [id, root])
  const [knownBusy, setKnownBusy] = useState(false)
  const [wsNotice, setWsNotice] = useState(null)
  const [wsBusy, setWsBusy] = useState(false)

  useEffect(() => {
    prepareGoogle()
  }, [])

  const sub = useMemo(() => {
    if (!d.data) return null
    const byId = Object.fromEntries(catalog.concepts.map((c) => [c.id, c]))
    if (!byId[d.data.targetConceptId]) return null
    const set = new Set([d.data.targetConceptId])
    const stack = [d.data.targetConceptId]
    while (stack.length) {
      const n = stack.pop()
      const node = byId[n]
      if (!node) continue
      node.prerequisites.forEach((p) => {
        if (!set.has(p) && byId[p]) {
          set.add(p)
          stack.push(p)
        }
      })
    }
    return set
  }, [d.data, catalog])

  if (d.loading) return <Spinner label="Loading your result" />
  if (d.error) return <ErrorNote error={d.error} />
  const diag = d.data
  if (diag.status !== 'done') {
    return (
      <div className="card">
        <p>This diagnosis is still in progress.</p>
        <button className="btn" onClick={() => go('diagnose')}>Start a new one</button>
      </div>
    )
  }
  const r = diag.result
  const mastery = m.data || {}
  const stateOf = (cid) => (mastery[cid] ? mastery[cid].status : 'untested')
  const ca = r.confidenceAssessment

  const markKnown = async () => {
    setKnownBusy(true)
    try {
      await api(`/me/mastery/${root}/known`, { method: 'POST' })
      await reloadMastery()
    } finally {
      setKnownBusy(false)
    }
  }

  const saveToGoogleDocs = async () => {
    setWsBusy(true)
    setWsNotice(null)
    try {
      const google = await ensureGoogle()
      const res = await api(`/google/docs/from-diagnosis/${id}`, { method: 'POST' })
      setWsNotice({
        text: savedWhere('doc', res.doc, google, res.warning),
        link: res.doc.live ? res.doc.url : null,
        linkLabel: 'Open in Google Docs ↗',
      })
    } catch (e) {
      setWsNotice({ text: `Could not save the notes: ${e.message}` })
    } finally {
      setWsBusy(false)
    }
  }

  const addToGoogleTasks = async () => {
    setWsBusy(true)
    setWsNotice(null)
    try {
      const res = await api(`/google/tasks/from-diagnosis/${id}`, { method: 'POST' })
      setWsNotice({ text: `Added ${res.created.length} step(s) to your study tasks in Google Workspace.` })
    } catch (e) {
      setWsNotice({ text: `Could not add the tasks: ${e.message}` })
    } finally {
      setWsBusy(false)
    }
  }

  return (
    <div className="result">
      <div className="card hero-card">
        <div className="eyebrow">Your diagnosis · {new Date(diag.createdAt).toLocaleString()}</div>
        {!root && <h1 className="h1">No foundational gap found in {diag.targetName}</h1>}
        {root && root !== r.targetConceptId && (
          <h1 className="h1">
            Your gap isn't <span className="strike">{r.targetName}</span>. It's <span className="accent">{r.rootCauseName}</span>.
          </h1>
        )}
        {root && root === r.targetConceptId && (
          <h1 className="h1">
            The gap is <span className="accent">{r.rootCauseName}</span> itself. Its prerequisites look solid.
          </h1>
        )}
        <p className="muted">"{diag.stuckInput}"</p>

        {ca && (
          <div className="conf-summary-box">
            <div>
              <span className="label">Student Confidence Assessment ({ca.total} foundation questions)</span>
              <b>{ca.label}</b>
            </div>
            <div className="conf-stats">
              <span>Calibrated certainty: <b>{Math.round((ca.score || 0) * 100)}%</b></span>
              <span>Confident & right: <b>{ca.highConfidenceCorrect}</b></span>
              {ca.lowConfidenceCorrect > 0 && <span>Lucky guesses verified: <b>{ca.lowConfidenceCorrect}</b></span>}
              {ca.highConfidenceWrong > 0 && <span>High-confidence slips: <b>{ca.highConfidenceWrong}</b></span>}
            </div>
          </div>
        )}

        {root && (
          <>
            <div className="conf">
              <span>Diagnosis certainty</span>
              <div className="bar"><i style={{ width: `${Math.round(r.confidence * 100)}%` }} /></div>
              <b>{Math.round(r.confidence * 100)}%</b>
            </div>
            <div className="route">
              <span className="label">Hard-edge prerequisite route</span>
              {r.path.map((p, i) => (
                <React.Fragment key={p.id}>
                  {i > 0 && <span className="arrow">→</span>}
                  <span className={`route-stop ${p.id === root ? 'root' : ''}`}>{p.name}</span>
                </React.Fragment>
              ))}
            </div>
            {r.relatedNamed && r.relatedNamed.length > 0 && (
              <p className="fine">
                Related cross-links (soft edges, for suggestion only): {r.relatedNamed.map((x) => x.name).join(', ')}.
              </p>
            )}
            {r.untestedNamed.length > 0 && (
              <p className="fine">
                Not checked ({diag.maxProbes}-question limit): {r.untestedNamed.map((x) => x.name).join(', ')}. If something feels off, re-run from there.
              </p>
            )}
            {r.otherGapsNamed.length > 0 && (
              <p className="fine">Also weak: {r.otherGapsNamed.map((x) => x.name).join(', ')}.</p>
            )}
            <div className="actions left">
              <button className="btn ghost small" disabled={knownBusy} onClick={markKnown}>
                I actually know {r.rootCauseName}
              </button>
              {mastery[root] && mastery[root].selfReported && (
                <span className="fine">Marked as known. Re-check to earn a stamp.</span>
              )}
            </div>
          </>
        )}
        {!root && <p>{r.message}</p>}
      </div>

      {/* The questions fill the full width in columns, so there is never an empty strip beside
          them, however many were asked. The map and the explanation then sit side by side. */}
      <div className="card">
        <h2 className="h2">How Punca got there ({diag.asked.length} questions)</h2>
        <ol className="evidence">
          {diag.asked.map((a) => (
            <li key={a.probeId} className={a.correct ? 'ok' : 'no'}>
              <div className="ev-head">
                <b>{a.conceptName}</b>
                <span>
                  {a.correct ? 'correct' : 'incorrect'} · {CONF_LABELS[a.confidence] || 'Somewhat sure'}
                </span>
              </div>
              <div className="ev-q">{a.question}</div>
              {!a.correct && (
                <div className="ev-a">
                  You chose "{a.yourAnswer}". Answer: "{a.correctAnswer}".
                  {a.misconceptionLabel && <em> Slip: {a.misconceptionLabel.toLowerCase()}.</em>}
                </div>
              )}
            </li>
          ))}
        </ol>
        {r.skippedSolidNamed.length > 0 && (
          <p className="fine">
            Skipped because you already showed them: {r.skippedSolidNamed.map((x) => x.name).join(', ')}.
          </p>
        )}
      </div>

      <div className={root ? 'grid2' : undefined}>
        <div className="card">
          <h2 className="h2">Where it sits</h2>
          <p className="fine">Everything {r.targetName} depends on via hard prerequisite edges. Prerequisites are on the left; your route is outlined.</p>
          {sub && (
            <ConceptMap
              concepts={catalog.concepts}
              include={sub}
              stateOf={stateOf}
              highlight={r.remediationPath}
              root={root}
              target={r.targetConceptId}
            />
          )}
          <MapLegend />
        </div>

        {root && (
          <div className="card">
            <div className="eyebrow">Step 5 · Rebuild and save to Google Workspace</div>
            <h2 className="h2">Rebuild {r.rootCauseName}</h2>
            {rem.loading && <Spinner label="Preparing an explanation from the course notes" />}
            <ErrorNote error={rem.error} />
            {rem.data && !rem.data.found && <div className="notfound">{rem.data.message}</div>}
            {rem.data && rem.data.found && (
              <>
                <p className="explain">{rem.data.explanation}</p>
                {rem.data.keyPoints.length > 0 && (
                  <ul className="keypoints">
                    {rem.data.keyPoints.map((k) => <li key={k}>{k}</li>)}
                  </ul>
                )}
                <div className="cites">
                  <span className="label">Sources</span>
                  {rem.data.citations.map((c) => (
                    <span key={c.sourceId} className="cite" title={c.title}>{c.sourceId}</span>
                  ))}
                  <span className="fine">
                    {rem.data.source === 'gemini'
                      ? `Written by Gemini (${rem.data.model}) from these notes only.`
                      : 'Shown straight from the course notes.'}
                    {rem.data.llmError ? ' (Gemini was busy.)' : ''}
                  </span>
                </div>
                <div className="actions left" style={{ marginTop: '1rem' }}>
                  <button type="button" className="btn small" disabled={wsBusy} onClick={saveToGoogleDocs}>
                    Save notes to Google Docs
                  </button>
                  <button type="button" className="btn ghost small" disabled={wsBusy} onClick={addToGoogleTasks}>
                    Add route to my study tasks
                  </button>
                  <button type="button" className="btn ghost small" onClick={() => go('workspace')}>
                    Open Google Workspace →
                  </button>
                </div>
                {wsNotice && (
                  <p className="fine" style={{ marginTop: '0.5rem' }}>
                    <b>{wsNotice.text}</b>
                    {wsNotice.link && (
                      <>
                        {' '}
                        <a href={wsNotice.link} target="_blank" rel="noreferrer">{wsNotice.linkLabel}</a>
                      </>
                    )}
                  </p>
                )}
              </>
            )}
          </div>
        )}
      </div>

      {root && (
        <>
          {rem.data && rem.data.practice && rem.data.practice.length > 0 && (
            <div className="card">
              <div className="eyebrow">Step 6 · Practice</div>
              <h2 className="h2">Try {r.rootCauseName} yourself</h2>
              <p className="muted">These do not count towards your stamp. Use them to check the explanation has landed.</p>
              <Practice items={rem.data.practice} />
            </div>
          )}

          <div className="grid2">
            <div className="card">
              <div className="eyebrow">Step 7 · Re-check</div>
              <h2 className="h2">Prove it and earn a stamp</h2>
              <p className="muted">A stamp needs a passed re-check after remediation. Your first diagnosis never earns one.</p>
              <p>Now: <StateChip state={stateOf(root)} /></p>
              <Recheck conceptId={root} conceptName={r.rootCauseName} onDone={reloadMastery} />
            </div>
            <div className="card">
              <div className="eyebrow">Step 8 · Study with peers</div>
              <h2 className="h2">Close it with a peer study circle</h2>
              <CirclePanel conceptId={root} user={user} onUser={onUser} />
            </div>
          </div>
        </>
      )}
    </div>
  )
}
