import React, { useState } from 'react'
import { api } from '../api.js'
import { ErrorNote, go } from '../components/common.jsx'
import ProbeCard from '../components/ProbeCard.jsx'

const EXAMPLES = [
  "I don't get how backprop computes the gradients for the hidden layer weights",
  'My matmul keeps throwing a shape mismatch error in the forward pass',
  'Why do we use cross-entropy instead of MSE for logistic regression?',
  'How do I get the posterior with Bayes theorem in lab 4?',
]

export default function DiagnosePage() {
  const [stage, setStage] = useState('input')
  const [text, setText] = useState('')
  const [mapping, setMapping] = useState(null)
  const [target, setTarget] = useState(null)
  const [diag, setDiag] = useState(null)
  const [next, setNext] = useState(null)
  const [chosen, setChosen] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const run = async (fn) => {
    setBusy(true)
    setError(null)
    try { await fn() } catch (e) { setError(e) } finally { setBusy(false) }
  }

  const findGap = (e) => {
    e.preventDefault()
    run(async () => {
      const m = await api('/map', { method: 'POST', body: { stuckInput: text } })
      setMapping(m)
      setTarget(m.targetConceptId)
      setStage('mapped')
    })
  }

  const start = () => run(async () => {
    const d = await api('/diagnoses', { method: 'POST', body: { stuckInput: text, targetConceptId: target, mapping } })
    if (d.status === 'done') go('diagnosis', d.id)
    else { setDiag(d); setStage('probing') }
  })

  const answer = (i) => run(async () => {
    setChosen(i)
    const r = await api(`/diagnoses/${diag.id}/answer`, { method: 'POST', body: { probeId: diag.pending.probeId, choiceIndex: i } })
    setFeedback(r.feedback)
    setNext(r.diagnosis)
  })

  const proceed = () => {
    if (next.status === 'done') { go('diagnosis', next.id); return }
    setDiag(next)
    setNext(null)
    setFeedback(null)
    setChosen(null)
  }

  if (stage === 'probing' && diag) {
    const asked = diag.probesAsked + (feedback ? 1 : 0)
    return (
      <div className="narrow">
        <div className="steps">
          <span className="done">1 Describe</span><span className="done">2 Map</span><span className="cur">3 Quick checks</span><span>4 Your gap</span>
        </div>
        <div className="card">
          <div className="probe-meta">
            <span>Stuck on <b>{diag.targetName}</b></span>
            <span className="dots" aria-label={`Question ${asked} of up to ${diag.maxProbes}`}>
              {Array.from({ length: diag.maxProbes }).map((_, i) => <i key={i} className={i < asked ? 'on' : ''} />)}
            </span>
          </div>
          <ProbeCard probe={diag.pending} chosen={chosen} feedback={feedback} busy={busy} onAnswer={answer}
            eyebrow={`Checking: ${diag.pending.conceptName}`} />
          <ErrorNote error={error} />
          {feedback && (
            <div className="actions">
              <button className="btn primary" onClick={proceed}>{next && next.status === 'done' ? 'See my gap' : 'Next question'}</button>
            </div>
          )}
        </div>
        <p className="fine center">Each answer updates your mastery estimate. Wrong answers lead Punca one step further back through the prerequisites.</p>
      </div>
    )
  }

  return (
    <div className="narrow">
      <div className="steps">
        <span className={stage === 'input' ? 'cur' : 'done'}>1 Describe</span><span className={stage === 'mapped' ? 'cur' : ''}>2 Map</span><span>3 Quick checks</span><span>4 Your gap</span>
      </div>
      <form className="card" onSubmit={findGap}>
        <h1 className="h1">Where are you stuck?</h1>
        <p className="muted">Paste a lab question, an assignment brief or a slide, or just describe it in your own words.</p>
        <textarea value={text} onChange={(e) => { setText(e.target.value); if (stage !== 'input') setStage('input') }} rows={4} maxLength={2000}
          placeholder="e.g. I don't understand how backpropagation updates the hidden layer weights" required minLength={3} />
        <div className="examples">
          {EXAMPLES.map((ex) => <button type="button" key={ex} className="chip-btn" onClick={() => { setText(ex); setStage('input') }}>{ex}</button>)}
        </div>
        <ErrorNote error={stage === 'input' ? error : null} />
        {stage === 'input' && <div className="actions"><button className="btn primary" disabled={busy || text.trim().length < 3}>{busy ? 'Mapping...' : 'Find my gap'}</button></div>}
      </form>

      {stage === 'mapped' && mapping && (
        <div className="card mapped">
          <div className="eyebrow">Step 2 · What this is about</div>
          {target ? (
            <h2 className="h2">This sounds like <span className="accent">{(mapping.candidates.find((c) => c.conceptId === target) || {}).name || mapping.targetName}</span></h2>
          ) : <h2 className="h2">Pick the closest concept</h2>}
          {target === mapping.targetConceptId && <p className="muted">{mapping.justification}</p>}
          <p className="fine">Matched by {mapping.source === 'gemini' ? `Gemini (${mapping.model})` : 'keyword search'}{mapping.llmError ? ' (Gemini was busy, so keyword search was used)' : ''}.</p>
          {mapping.candidates.length > 1 && (
            <>
              <div className="label">Not quite? Choose another:</div>
              <div className="examples">
                {mapping.candidates.map((c) => (
                  <button key={c.conceptId} type="button" className={`chip-btn ${c.conceptId === target ? 'on' : ''}`} onClick={() => setTarget(c.conceptId)}>{c.name}</button>
                ))}
              </div>
            </>
          )}
          <ErrorNote error={error} />
          <div className="actions">
            <button className="btn ghost" onClick={() => setStage('input')}>Edit description</button>
            <button className="btn primary" disabled={!target || busy} onClick={start}>{busy ? 'Starting...' : 'Start quick checks (up to 5)'}</button>
          </div>
        </div>
      )}
    </div>
  )
}
