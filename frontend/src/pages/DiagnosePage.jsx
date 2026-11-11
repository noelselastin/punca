import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { ErrorNote, StateChip, go } from '../components/common.jsx'
import ProbeCard from '../components/ProbeCard.jsx'

const EXAMPLES = [
  'Minimising f(x, y) = (x - 3)^2 + (2y + 1)^2 with gradient descent and partial derivatives',
  'My recursive factorial and nested-list sum functions in Python keep hitting RecursionError',
  'My SQL query drops students with 0 enrolments when I use INNER JOIN with COUNT and GROUP BY',
  'I do not understand how a Shape variable in Java calls Circle.area() via polymorphism',
  'When multiplying two matrices A (2x3) and B (3x4), why is BA undefined and how do inner dimensions match?',
]

function readFileAsBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Could not read the selected file.'))
    reader.onload = () => resolve(reader.result)
    reader.readAsDataURL(file)
  })
}

export default function DiagnosePage() {
  const [stage, setStage] = useState('input')
  const [text, setText] = useState('')
  const [pcFile, setPcFile] = useState(null) // { fileName, fileBase64, sizeBytes, mimeType }

  const [mapping, setMapping] = useState(null)
  const [target, setTarget] = useState(null)
  const [diag, setDiag] = useState(null)
  const [next, setNext] = useState(null)
  const [chosen, setChosen] = useState(null)
  const [confidence, setConfidence] = useState('medium')
  const [feedback, setFeedback] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const fileInputRef = useRef(null)

  const run = async (fn) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  const handlePcFileSelect = async (e) => {
    const file = e.target.files && e.target.files[0]
    if (!file) return
    setError(null)
    try {
      const b64 = await readFileAsBase64(file)
      setPcFile({
        fileName: file.name,
        fileBase64: b64,
        sizeBytes: file.size,
        mimeType: file.type || undefined,
      })
      if (stage !== 'input') setStage('input')
    } catch (err) {
      setError(err)
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const canSubmit = text.trim().length >= 3 || pcFile != null

  const findGap = (e) => {
    e.preventDefault()
    run(async () => {
      const body = {
        stuckInput: text.trim() || (pcFile ? `Lab file: ${pcFile.fileName}` : ''),
      }
      if (pcFile) {
        body.fileName = pcFile.fileName
        body.fileBase64 = pcFile.fileBase64
        body.mimeType = pcFile.mimeType
      }
      const m = await api('/map', { method: 'POST', body })
      setMapping(m)
      setTarget(m.targetConceptId)
      setStage('mapped')
    })
  }

  const start = () =>
    run(async () => {
      const promptText =
        text.trim() ||
        (mapping && mapping.documentSummary
          ? `${mapping.documentSummary.fileName}: ${mapping.documentSummary.summary}`
          : 'Uploaded lab brief')
      const d = await api('/diagnoses', {
        method: 'POST',
        body: { stuckInput: promptText, targetConceptId: target, mapping },
      })
      if (d.status === 'done') go('diagnosis', d.id)
      else {
        setDiag(d)
        setConfidence('medium')
        setStage('probing')
      }
    })

  const answer = (i) =>
    run(async () => {
      setChosen(i)
      const r = await api(`/diagnoses/${diag.id}/answer`, {
        method: 'POST',
        body: {
          probeId: diag.pending.probeId,
          choiceIndex: i,
          confidence,
        },
      })
      setFeedback(r.feedback)
      setNext(r.diagnosis)
    })

  const proceed = () => {
    if (next.status === 'done') {
      go('diagnosis', next.id)
      return
    }
    setDiag(next)
    setNext(null)
    setFeedback(null)
    setChosen(null)
    setConfidence('medium')
  }

  if (stage === 'probing' && diag) {
    const asked = diag.probesAsked + (feedback ? 1 : 0)
    const minProbes = diag.minProbes || 5
    const maxProbes = diag.maxProbes || 10
    return (
      <div className="narrow">
        <div className="steps">
          <span className="done">1 Describe & Upload</span>
          <span className="done">2 Foundations</span>
          <span className="cur">3 Foundation checks (5–10)</span>
          <span>4 Your gap</span>
        </div>
        <div className="card">
          <div className="probe-meta">
            <span>
              Assessing <b>{diag.targetName}</b> · Question <b>{asked}</b> (5–10 foundation checks)
            </span>
            <span className="dots" aria-label={`Question ${asked} of ${minProbes} to ${maxProbes}`}>
              {Array.from({ length: maxProbes }).map((_, i) => (
                <i key={i} className={i < asked ? 'on' : i < minProbes ? 'min-req' : ''} />
              ))}
            </span>
          </div>
          <ProbeCard
            probe={diag.pending}
            chosen={chosen}
            feedback={feedback}
            busy={busy}
            onAnswer={answer}
            confidence={confidence}
            onConfidenceChange={setConfidence}
            eyebrow={`Foundation check ${asked} · ${diag.pending.conceptName}`}
          />
          <ErrorNote error={error} />
          {feedback && (
            <div className="actions">
              <button className="btn primary" onClick={proceed}>
                {next && next.status === 'done' ? 'See my foundation diagnosis' : 'Next foundation question'}
              </button>
            </div>
          )}
        </div>
        <p className="fine center">
          Punca asks 5–10 questions across the required foundations and weights your confidence so a lucky guess is never mistaken for solid mastery.
        </p>
      </div>
    )
  }

  return (
    <div className="narrow">
      <div className="steps">
        <span className={stage === 'input' ? 'cur' : 'done'}>1 Describe & Upload</span>
        <span className={stage === 'mapped' ? 'cur' : ''}>2 Foundations</span>
        <span>3 Foundation checks (5–10)</span>
        <span>4 Your gap</span>
      </div>
      <form className="card" onSubmit={findGap}>
        <h1 className="h1">Where are you stuck?</h1>
        <p className="muted">
          Write your question or lab brief below, or upload the lab or question file from your PC so Punca can read it and assess every required foundation.
        </p>
        <textarea
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            if (stage !== 'input') setStage('input')
          }}
          rows={4}
          maxLength={2500}
          placeholder="e.g. Describe the lab or question you are struggling with, or attach the worksheet/code file below..."
        />

        <div className="doc-upload-bar">
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.py,.java,.c,.cpp,.js,.jsx,.ts,.sql,.csv,.json,.ipynb,.docx,.pptx,.pdf"
            onChange={handlePcFileSelect}
            style={{ display: 'none' }}
          />
          <div className="doc-upload-buttons">
            <button
              type="button"
              className="btn small"
              onClick={() => fileInputRef.current && fileInputRef.current.click()}
            >
              Upload from PC
            </button>
          </div>
          <span className="fine">
            Reads .pdf, .docx, .pptx, .ipynb, .py, .java, .sql, .md, .txt and .csv files.
          </span>
        </div>

        {pcFile && (
          <div className="attached-file-card">
            <div>
              <div className="eyebrow">Uploaded from PC</div>
              <b>{pcFile.fileName}</b>{' '}
              <span className="fine">({Math.max(1, Math.round(pcFile.sizeBytes / 1024))} KB)</span>
            </div>
            <button type="button" className="btn ghost small" onClick={() => setPcFile(null)}>
              Remove
            </button>
          </div>
        )}

        <div className="examples">
          {EXAMPLES.map((ex) => (
            <button
              type="button"
              key={ex}
              className="chip-btn"
              onClick={() => {
                setText(ex)
                setStage('input')
              }}
            >
              {ex}
            </button>
          ))}
        </div>
        <ErrorNote error={stage === 'input' ? error : null} />
        {stage === 'input' && (
          <div className="actions">
            <button className="btn primary" disabled={busy || !canSubmit}>
              {busy ? 'Reading & assessing foundations...' : 'Assess required foundations'}
            </button>
          </div>
        )}
      </form>

      {stage === 'mapped' && mapping && (
        <div className="card mapped">
          <div className="eyebrow">Step 2 · Foundations assessed from your brief & document</div>

          {mapping.documentSummary && (
            <div className="attached-file-card" style={{ marginBottom: '1rem' }}>
              <div>
                <div className="eyebrow">Document read (uploaded from PC)</div>
                <b>{mapping.documentSummary.fileName}</b>{' '}
                <span className="fine">({mapping.documentSummary.wordCount} words extracted)</span>
                <p className="fine" style={{ marginTop: '0.25rem' }}>{mapping.documentSummary.summary}</p>
              </div>
            </div>
          )}

          {target ? (
            <h2 className="h2">
              Primary concept:{' '}
              <span className="accent">
                {(mapping.candidates.find((c) => c.conceptId === target) || {}).name || mapping.targetName}
              </span>
            </h2>
          ) : (
            <h2 className="h2">Pick the primary concept</h2>
          )}
          {target === mapping.targetConceptId && <p className="muted">{mapping.justification}</p>}

          {mapping.requiredFoundations && mapping.requiredFoundations.length > 0 && (
            <div className="foundations-box">
              <div className="label">
                Required foundations identified ({mapping.requiredFoundations.length} concepts to verify across 5–10 questions):
              </div>
              <div className="foundations-grid">
                {mapping.requiredFoundations.map((f) => (
                  <button
                    type="button"
                    key={f.conceptId}
                    className={`foundation-item ${f.conceptId === target ? 'on' : ''}`}
                    onClick={() => setTarget(f.conceptId)}
                  >
                    <div className="foundation-top">
                      <b>{f.name}</b>
                      <StateChip state={f.state === 'entry-required' || f.state === 'reentry' ? 'gap' : f.state === 'stamped' ? 'solid' : f.state} />
                    </div>
                    <small className="fine">{f.area}</small>
                  </button>
                ))}
              </div>
            </div>
          )}

          {mapping.candidates.length > 1 && (
            <>
              <div className="label" style={{ marginTop: '0.75rem' }}>Or switch primary target concept:</div>
              <div className="examples">
                {mapping.candidates.map((c) => (
                  <button
                    key={c.conceptId}
                    type="button"
                    className={`chip-btn ${c.conceptId === target ? 'on' : ''}`}
                    onClick={() => setTarget(c.conceptId)}
                  >
                    {c.name}
                  </button>
                ))}
              </div>
            </>
          )}
          <ErrorNote error={error} />
          <div className="actions">
            <button className="btn ghost" onClick={() => setStage('input')}>
              Edit brief / file
            </button>
            <button className="btn primary" disabled={!target || busy} onClick={start}>
              {busy ? 'Starting...' : 'Start foundation checks (5–10 questions)'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
