import React, { useEffect, useRef, useState } from 'react'
import { api } from '../api.js'
import { ErrorNote, StateChip, go } from '../components/common.jsx'
import ProbeCard from '../components/ProbeCard.jsx'
import { requestGoogleAccessToken } from '../googleAuth.js'

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

export default function DiagnosePage({ prefill, onClearPrefill }) {
  const [stage, setStage] = useState('input')
  const [text, setText] = useState(prefill ? prefill.stuckInput || '' : '')
  const [pcFile, setPcFile] = useState(null) // { fileName, fileBase64, sizeBytes, mimeType }
  const [saveToDrive, setSaveToDrive] = useState(true)
  const [driveFile, setDriveFile] = useState(null) // { id, name, summary, webViewLink, live }
  const [showDrivePicker, setShowDrivePicker] = useState(false)
  const [driveFiles, setDriveFiles] = useState([])
  const [driveLoading, setDriveLoading] = useState(false)
  const [driveUploading, setDriveUploading] = useState(false)
  const [driveNotice, setDriveNotice] = useState('')
  const [wsStatus, setWsStatus] = useState(null)

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
  const directDriveInputRef = useRef(null)

  const loadWorkspaceStatus = async () => {
    try {
      const ws = await api('/google/status')
      setWsStatus(ws)
      setDriveFiles(ws.driveFiles || [])
      return ws
    } catch {
      return null
    }
  }

  useEffect(() => {
    loadWorkspaceStatus()
  }, [])

  useEffect(() => {
    if (prefill) {
      if (prefill.stuckInput) setText(prefill.stuckInput)
      if (prefill.driveFile) {
        setDriveFile(prefill.driveFile)
        setPcFile(null)
      }
      setStage('input')
      if (onClearPrefill) onClearPrefill()
    }
  }, [prefill, onClearPrefill])

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
    setDriveNotice('')
    try {
      const b64 = await readFileAsBase64(file)
      setPcFile({
        fileName: file.name,
        fileBase64: b64,
        sizeBytes: file.size,
        mimeType: file.type || undefined,
      })
      setDriveFile(null)
      setShowDrivePicker(false)
      if (stage !== 'input') setStage('input')
    } catch (err) {
      setError(err)
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const uploadFileDirectlyToDrive = async (fileObj) => {
    setDriveUploading(true)
    setError(null)
    setDriveNotice('')
    try {
      const res = await api('/google/drive/upload', {
        method: 'POST',
        body: {
          fileName: fileObj.fileName,
          fileBase64: fileObj.fileBase64,
          mimeType: fileObj.mimeType,
        },
      })
      const saved = res.file
      if (res.workspace) {
        setWsStatus(res.workspace)
        setDriveFiles(res.workspace.driveFiles || [])
      }
      setDriveFile(saved)
      setPcFile(null)
      setShowDrivePicker(false)
      setDriveNotice(
        res.warning
          ? `Saved '${saved.name}' to your Punca Drive folder (${res.warning})`
          : saved.live
            ? `Uploaded '${saved.name}' directly to your Google Drive (${saved.folder}) and attached it below.`
            : `Uploaded '${saved.name}' to your Google Drive study folder (${saved.folder}) and attached it below.`
      )
      if (!text.trim() && saved.summary) {
        setText(`Struggling with ${saved.name}: ${saved.summary}`.slice(0, 400))
      }
      if (stage !== 'input') setStage('input')
    } catch (err) {
      setError(err)
    } finally {
      setDriveUploading(false)
    }
  }

  const handleDirectDriveInput = async (e) => {
    const file = e.target.files && e.target.files[0]
    if (!file) return
    try {
      const b64 = await readFileAsBase64(file)
      await uploadFileDirectlyToDrive({
        fileName: file.name,
        fileBase64: b64,
        sizeBytes: file.size,
        mimeType: file.type || undefined,
      })
    } catch (err) {
      setError(err)
    } finally {
      if (directDriveInputRef.current) directDriveInputRef.current.value = ''
    }
  }

  const connectLiveGoogle = async () => {
    if (!wsStatus?.oauthClientId) {
      go('workspace')
      return
    }
    setDriveUploading(true)
    setError(null)
    try {
      const tok = await requestGoogleAccessToken({
        clientId: wsStatus.oauthClientId,
        scopes: wsStatus.oauthScopes || [],
        loginHint: wsStatus.accountEmail || wsStatus.email || '',
      })
      const updated = await api('/google/connect', { method: 'POST', body: tok })
      setWsStatus(updated)
      setDriveFiles(updated.driveFiles || [])
      setDriveNotice(`Connected live Google Drive for ${updated.email}.`)
    } catch (err) {
      setError(err)
    } finally {
      setDriveUploading(false)
    }
  }

  const openDrivePicker = async () => {
    if (showDrivePicker) {
      setShowDrivePicker(false)
      return
    }
    setShowDrivePicker(true)
    setDriveLoading(true)
    setError(null)
    try {
      const ws = await api('/google/status')
      setWsStatus(ws)
      setDriveFiles(ws.driveFiles || [])
    } catch (err) {
      setError(err)
    } finally {
      setDriveLoading(false)
    }
  }

  const selectDriveFile = (f) => {
    setDriveFile(f)
    setPcFile(null)
    setShowDrivePicker(false)
    setDriveNotice(`Attached '${f.name}' from Google Drive.`)
    if (!text.trim()) {
      setText(`Struggling with ${f.name}: ${f.summary || ''}`.slice(0, 400))
    }
    if (stage !== 'input') setStage('input')
  }

  const canSubmit = text.trim().length >= 3 || pcFile != null || driveFile != null

  const findGap = (e) => {
    e.preventDefault()
    run(async () => {
      const body = {
        stuckInput: text.trim() || (pcFile ? `Lab file: ${pcFile.fileName}` : driveFile ? `Drive file: ${driveFile.name}` : ''),
      }
      if (pcFile) {
        body.fileName = pcFile.fileName
        body.fileBase64 = pcFile.fileBase64
        body.mimeType = pcFile.mimeType
        body.saveToDrive = saveToDrive
      } else if (driveFile) {
        body.driveFileId = driveFile.id
      }
      const m = await api('/map', { method: 'POST', body })
      setMapping(m)
      setTarget(m.targetConceptId)
      setStage('mapped')
      loadWorkspaceStatus()
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
          Write your question or lab brief below, or upload the lab/question file directly to Google Drive or from your PC so Punca can read the document and assess every required foundation.
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
            ref={directDriveInputRef}
            type="file"
            accept=".txt,.md,.py,.java,.c,.cpp,.js,.jsx,.ts,.sql,.csv,.json,.ipynb,.docx,.pptx,.pdf"
            onChange={handleDirectDriveInput}
            style={{ display: 'none' }}
          />
          <input
            ref={fileInputRef}
            type="file"
            accept=".txt,.md,.py,.java,.c,.cpp,.js,.jsx,.ts,.sql,.csv,.json,.ipynb,.docx,.pptx,.pdf"
            onChange={handlePcFileSelect}
            style={{ display: 'none' }}
          />

          <div className="drive-conn-strip">
            <div className="drive-conn-info">
              <span className={`ws-dot ${wsStatus?.connected !== false ? 'on' : 'off'}`} />
              <span>
                <b>Google Drive:</b>{' '}
                {wsStatus
                  ? wsStatus.connected === false
                    ? 'Switched off in Workspace settings'
                    : `${wsStatus.email} · Folder: ${wsStatus.preferences?.driveFolderName || 'Punca Study Materials'} (${(wsStatus.driveFiles || []).length} files)`
                  : 'Connected'}
              </span>
              {wsStatus?.liveConnected && <span className="chip solid">Live Google Drive</span>}
            </div>
            <div className="drive-conn-actions">
              {wsStatus?.liveAvailable && !wsStatus?.liveConnected && (
                <button
                  type="button"
                  className="btn ghost small"
                  disabled={driveUploading}
                  onClick={connectLiveGoogle}
                >
                  Connect live Google account
                </button>
              )}
              <button type="button" className="linkish fine" onClick={() => go('workspace')}>
                Open Drive in Workspace →
              </button>
            </div>
          </div>

          <div className="doc-upload-buttons">
            <button
              type="button"
              className="btn small"
              disabled={driveUploading}
              onClick={() => directDriveInputRef.current && directDriveInputRef.current.click()}
            >
              {driveUploading ? 'Uploading to Google Drive...' : '☁️ Upload directly to Google Drive'}
            </button>
            <button
              type="button"
              className="btn ghost small"
              onClick={openDrivePicker}
            >
              {showDrivePicker ? 'Hide Google Drive files' : `📂 Pick from Google Drive (${driveFiles.length})`}
            </button>
            <button
              type="button"
              className="btn ghost small"
              onClick={() => fileInputRef.current && fileInputRef.current.click()}
            >
              💻 Attach file from PC
            </button>
          </div>
          <span className="fine">Supports .pdf, .docx, .pptx, .ipynb, .py, .java, .sql, .md, .txt, .csv</span>
        </div>

        {driveNotice && (
          <div className="ws-banner" style={{ marginBottom: '0.75rem' }}>
            <span>{driveNotice}</span>
            <button type="button" className="linkish" onClick={() => setDriveNotice('')}>Dismiss</button>
          </div>
        )}

        {pcFile && (
          <div className="attached-file-card">
            <div>
              <div className="eyebrow">Attached from PC</div>
              <b>{pcFile.fileName}</b>{' '}
              <span className="fine">({Math.max(1, Math.round(pcFile.sizeBytes / 1024))} KB)</span>
              <label className="inline-check">
                <input
                  type="checkbox"
                  checked={saveToDrive}
                  onChange={(e) => setSaveToDrive(e.target.checked)}
                />
                <span>Also save to my Google Drive study folder when assessing</span>
              </label>
            </div>
            <div className="row" style={{ gap: '0.4rem' }}>
              <button
                type="button"
                className="btn small"
                disabled={driveUploading}
                onClick={() => uploadFileDirectlyToDrive(pcFile)}
              >
                {driveUploading ? 'Uploading...' : '☁️ Upload to Drive now'}
              </button>
              <button type="button" className="btn ghost small" onClick={() => setPcFile(null)}>
                Remove
              </button>
            </div>
          </div>
        )}

        {driveFile && (
          <div className="attached-file-card">
            <div>
              <div className="eyebrow">
                Attached from Google Drive {driveFile.live ? '· Live Google Drive' : `· ${driveFile.folder || 'Study Folder'}`}
              </div>
              <b>{driveFile.name}</b>
              {driveFile.summary && <p className="fine" style={{ margin: '0.25rem 0 0' }}>{driveFile.summary}</p>}
              {driveFile.webViewLink && (
                <a className="fine" href={driveFile.webViewLink} target="_blank" rel="noreferrer">
                  Open in Google Drive ↗
                </a>
              )}
            </div>
            <button type="button" className="btn ghost small" onClick={() => setDriveFile(null)}>
              Remove
            </button>
          </div>
        )}

        {showDrivePicker && (
          <div className="drive-picker-panel">
            <div className="drive-picker-head">
              <b>Google Drive · Study & Lab Files ({driveFiles.length})</b>
              <div className="row" style={{ gap: '0.6rem' }}>
                <button
                  type="button"
                  className="btn small"
                  disabled={driveUploading}
                  onClick={() => directDriveInputRef.current && directDriveInputRef.current.click()}
                >
                  + Upload new file to Drive
                </button>
                <button type="button" className="linkish" onClick={() => go('workspace')}>
                  Manage Google Drive →
                </button>
              </div>
            </div>
            {driveLoading ? (
              <p className="fine">Loading your Google Drive files...</p>
            ) : driveFiles.length === 0 ? (
              <p className="fine">No files in your Google Drive yet. Click “Upload directly to Google Drive” above.</p>
            ) : (
              <div className="drive-file-list">
                {driveFiles.map((df) => (
                  <div key={df.id} className="drive-file-item">
                    <div>
                      <div className="row" style={{ gap: '0.4rem' }}>
                        <b>{df.name}</b>
                        {df.starter ? (
                          <span className="chip untested">Course sample</span>
                        ) : (
                          <span className="chip solid">{df.live ? 'Live Drive' : 'Uploaded'}</span>
                        )}
                      </div>
                      <div className="fine">{df.summary}</div>
                    </div>
                    <button type="button" className="btn small" onClick={() => selectDriveFile(df)}>
                      Attach
                    </button>
                  </div>
                ))}
              </div>
            )}
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
                <div className="eyebrow">
                  Document read ({mapping.documentSummary.source === 'google-drive' ? 'Google Drive' : 'Uploaded to Google Drive'})
                </div>
                <b>{mapping.documentSummary.fileName}</b>{' '}
                <span className="fine">({mapping.documentSummary.wordCount} words extracted)</span>
                <p className="fine" style={{ marginTop: '0.25rem' }}>{mapping.documentSummary.summary}</p>
                {mapping.documentSummary.webViewLink && (
                  <a className="fine" href={mapping.documentSummary.webViewLink} target="_blank" rel="noreferrer">
                    View in Google Drive ↗
                  </a>
                )}
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
