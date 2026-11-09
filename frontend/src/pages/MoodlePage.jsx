import React, { useState } from 'react'
import { api } from '../api.js'
import { ErrorNote, Spinner, StateChip, go, useAsync } from '../components/common.jsx'

const fmtDate = (iso) => {
  if (!iso) return 'No due date'
  const d = new Date(iso)
  const diffDays = Math.ceil((d.getTime() - Date.now()) / (1000 * 60 * 60 * 24))
  const dateStr = d.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' })
  if (diffDays < 0) return `Closed · ${dateStr}`
  if (diffDays === 0) return `Due today · ${dateStr}`
  if (diffDays === 1) return `Due tomorrow · ${dateStr}`
  return `Due in ${diffDays} days · ${dateStr}`
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result || ''))
    reader.onerror = () => reject(new Error('Could not read the selected file.'))
    reader.readAsDataURL(file)
  })
}

export default function MoodlePage({ user, onUser, onDiagnosePrompt }) {
  const [statusState, reload] = useAsync(() => api('/moodle/status'), [])
  const [baseUrl, setBaseUrl] = useState('https://lms2.apiit.edu.my')
  const [token, setToken] = useState('')
  const [showTokenForm, setShowTokenForm] = useState(false)
  const [courseFilter, setCourseFilter] = useState('all')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [notice, setNotice] = useState(null)

  const [importTitle, setImportTitle] = useState('')
  const [importCourse, setImportCourse] = useState('')
  const [importText, setImportText] = useState('')
  const [importFile, setImportFile] = useState(null)
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState(null)

  if (statusState.loading && !statusState.data) return <Spinner label="Checking APU Moodle connectivity" />
  if (statusState.error && !statusState.data) return <ErrorNote error={statusState.error} />

  const data = statusState.data || {}
  const pub = data.publicConfig || {}
  const conn = data.connection
  const courses = data.courses || []
  const materials = data.materials || []
  const deadlines = data.deadlines || []

  const refreshMe = async () => {
    try {
      const me = await api('/me')
      if (onUser) onUser(me)
    } catch (_) {}
  }

  const connectDemo = async () => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await api('/moodle/connect', { method: 'POST', body: { mode: 'apu-demo', baseUrl } })
      await refreshMe()
      await reload()
      setNotice('Synced APU Moodle modules, lecture slide folders, and upcoming assignment deadlines.')
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  const connectToken = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await api('/moodle/connect', { method: 'POST', body: { mode: 'token', baseUrl, token } })
      setToken('')
      setShowTokenForm(false)
      await refreshMe()
      await reload()
      setNotice('Connected to Moodle with your Web Service Security Key.')
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  const syncNow = async () => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await api('/moodle/sync', { method: 'POST' })
      await reload()
      setNotice('Refreshed courses, lecture slides, and assignment deadlines from Moodle.')
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  const disconnect = async () => {
    setBusy(true)
    setError(null)
    setNotice(null)
    try {
      await api('/moodle/connection', { method: 'DELETE' })
      await refreshMe()
      await reload()
      setNotice('Disconnected from Moodle.')
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  const handleImport = async (e) => {
    e.preventDefault()
    setImporting(true)
    setImportError(null)
    setNotice(null)
    try {
      let contentBase64 = null
      let filename = null
      if (importFile) {
        filename = importFile.name
        contentBase64 = await fileToBase64(importFile)
      }
      const res = await api('/moodle/import', {
        method: 'POST',
        body: {
          title: importTitle,
          courseName: importCourse,
          filename,
          contentBase64,
          text: importText,
        },
      })
      setImportTitle('')
      setImportCourse('')
      setImportText('')
      setImportFile(null)
      await refreshMe()
      await reload()
      setNotice(`Imported "${res.imported.title}" and mapped its prerequisite concepts.`)
    } catch (err) {
      setImportError(err)
    } finally {
      setImporting(false)
    }
  }

  const startDiagnosisFromItem = (item) => {
    if (onDiagnosePrompt) {
      onDiagnosePrompt({
        stuckInput: item.stuckPrompt || `${item.courseName}: ${item.title} — ${item.summary}`,
        targetConceptId: item.primaryConceptId,
        sourceTitle: `${item.courseName} · ${item.title}`,
      })
    }
    go('diagnose')
  }

  const filteredMaterials = courseFilter === 'all'
    ? materials
    : materials.filter((m) => m.courseId === courseFilter || m.courseName === courseFilter)

  const filteredDeadlines = courseFilter === 'all'
    ? deadlines
    : deadlines.filter((d) => d.courseId === courseFilter || d.courseName === courseFilter)

  return (
    <div className="moodle-page">
      <div className="card moodle-hero">
        <div className="moodle-hero-top">
          <div>
            <div className="eyebrow">LMS Integration · APU Moodle</div>
            <h1 className="h1">Connect your modules, lecture slides & deadlines.</h1>
            <p className="muted">
              Punca checks each Moodle lecture deck and assignment brief against the prerequisite graph so you can spot missing foundations before a deadline hits.
            </p>
          </div>
          <div className="moodle-badges">
            <span className={`chip ${pub.enableWebServices ? 'state-stamped' : 'state-untested'}`}>
              Web services: {pub.enableWebServices ? 'Enabled' : 'Unverified'}
            </span>
            <span className={`chip ${pub.enableMobileWebService ? 'state-stamped' : 'state-untested'}`}>
              Mobile API: {pub.enableMobileWebService ? 'Enabled' : 'Unverified'}
            </span>
            <span className="chip state-endorsed">
              SSO: {(pub.identityProviders && pub.identityProviders[0] && pub.identityProviders[0].name) || 'Microsoft'}
            </span>
          </div>
        </div>

        {notice && <div className="ok-note" role="status">{notice}</div>}
        <ErrorNote error={error} />

        {!data.connected ? (
          <div className="moodle-connect-panel">
            <div className="moodle-connect-actions">
              <button type="button" className="btn primary" disabled={busy} onClick={connectDemo}>
                {busy ? 'Syncing APU Moodle...' : 'Sync APU Moodle courses & slides'}
              </button>
              <button type="button" className="btn ghost" disabled={busy} onClick={() => setShowTokenForm((v) => !v)}>
                {showTokenForm ? 'Hide Security Key form' : 'Connect with Moodle Security Key'}
              </button>
              <a className="btn ghost small" href="https://lms2.apiit.edu.my" target="_blank" rel="noreferrer">
                Open lms2.apiit.edu.my ↗
              </a>
            </div>
            <p className="fine">
              APU Moodle (<code>lms2.apiit.edu.my</code>) has <code>enablewebservices: 1</code> and <code>enablemobilewebservice: 1</code> active. Use instant APU sync for the hackathon demo, or connect a personal Moodle Security Key.
            </p>

            {showTokenForm && (
              <form className="moodle-token-form" onSubmit={connectToken}>
                <div className="row2">
                  <label className="field">
                    Moodle URL
                    <input
                      value={baseUrl}
                      onChange={(e) => setBaseUrl(e.target.value)}
                      placeholder="https://lms2.apiit.edu.my"
                      required
                    />
                    <small>Defaults to APU Online Learning (lms2.apiit.edu.my).</small>
                  </label>
                  <label className="field">
                    Moodle Security Key (Web service token)
                    <input
                      type="password"
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                      placeholder="Paste your Moodle mobile web service key"
                      required
                      minLength={8}
                    />
                    <small>
                      Found in Moodle under <b>Preferences → Security keys</b> (requires institutional permission under APU ICT guidelines).
                    </small>
                  </label>
                </div>
                <div className="actions">
                  <button type="submit" className="btn primary" disabled={busy || token.trim().length < 8}>
                    {busy ? 'Verifying token...' : 'Verify & sync Moodle'}
                  </button>
                </div>
              </form>
            )}
          </div>
        ) : (
          <div className="moodle-connected-bar">
            <div className="moodle-conn-meta">
              <div>
                <span className="label">Connected LMS</span>
                <b>{conn.siteName}</b>
              </div>
              <div>
                <span className="label">Student account</span>
                <b>{conn.accountName}</b>
              </div>
              <div>
                <span className="label">Access mode</span>
                <b>{conn.mode === 'token' ? `Live API (${conn.tokenMasked})` : 'APU Moodle Sync'}</b>
              </div>
              <div>
                <span className="label">Synced modules</span>
                <b>{courses.length} courses · {materials.length} resources · {deadlines.length} deadlines</b>
              </div>
            </div>
            <div className="moodle-conn-buttons">
              <button type="button" className="btn small" disabled={busy} onClick={syncNow}>
                {busy ? 'Refreshing...' : 'Refresh sync'}
              </button>
              <button type="button" className="btn ghost small" onClick={() => setShowTokenForm((v) => !v)}>
                {showTokenForm ? 'Hide key settings' : 'Switch to Security Key'}
              </button>
              <button type="button" className="btn ghost small" disabled={busy} onClick={disconnect}>
                Disconnect
              </button>
            </div>
            {showTokenForm && (
              <form className="moodle-token-form" onSubmit={connectToken}>
                <div className="row2">
                  <label className="field">
                    Moodle URL
                    <input value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} required />
                  </label>
                  <label className="field">
                    Moodle Security Key
                    <input
                      type="password"
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                      placeholder="Paste Moodle web service token"
                      required
                      minLength={8}
                    />
                  </label>
                </div>
                <div className="actions">
                  <button type="submit" className="btn primary small" disabled={busy || token.trim().length < 8}>
                    Save & sync live token
                  </button>
                </div>
              </form>
            )}
          </div>
        )}
      </div>

      {courses.length > 0 && (
        <section className="moodle-section">
          <div className="moodle-section-head">
            <div>
              <div className="eyebrow">Enrolled Modules</div>
              <h2 className="h2">Filter by APU Moodle course</h2>
            </div>
            <div className="examples">
              <button
                type="button"
                className={`chip-btn ${courseFilter === 'all' ? 'on' : ''}`}
                onClick={() => setCourseFilter('all')}
              >
                All modules ({courses.length})
              </button>
              {courses.map((c) => (
                <button
                  key={c.id}
                  type="button"
                  className={`chip-btn ${courseFilter === c.id ? 'on' : ''}`}
                  onClick={() => setCourseFilter(c.id)}
                >
                  {c.code || c.name}
                </button>
              ))}
            </div>
          </div>
        </section>
      )}

      <div className="grid2 moodle-columns">
        <section className="card moodle-col">
          <div className="eyebrow">Upcoming Assessments</div>
          <h2 className="h2">Assignment & quiz deadlines</h2>
          <p className="muted">Check the prerequisite concepts behind each assessment before you start coding or writing.</p>

          {filteredDeadlines.length === 0 ? (
            <p className="muted">Connect APU Moodle above to load your upcoming assignment deadlines.</p>
          ) : (
            <div className="moodle-list">
              {filteredDeadlines.map((d) => (
                <article key={d.id} className="moodle-item">
                  <div className="moodle-item-top">
                    <span className="moodle-course-tag">{d.courseName}</span>
                    <span className="moodle-due">{fmtDate(d.dueAt)}</span>
                  </div>
                  <h3 className="h3">{d.title}</h3>
                  <p className="muted">{d.summary}</p>
                  {d.concepts && d.concepts.length > 0 && (
                    <div className="moodle-concepts">
                      <div className="label">Mapped foundations ({d.readiness})</div>
                      <div className="moodle-chip-row">
                        {d.concepts.map((c) => (
                          <span key={c.conceptId} className="moodle-concept-pill">
                            <b>{c.name}</b> <StateChip state={c.state} />
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="moodle-item-actions">
                    <button type="button" className="btn primary small" onClick={() => startDiagnosisFromItem(d)}>
                      Check foundations for this deadline
                    </button>
                    {d.url && (
                      <a className="btn ghost small" href={d.url} target="_blank" rel="noreferrer">
                        View in Moodle ↗
                      </a>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="card moodle-col">
          <div className="eyebrow">Course Content & Slides</div>
          <h2 className="h2">Lecture folders & imported decks</h2>
          <p className="muted">Synced from your Moodle course folders or uploaded directly from downloaded slide decks.</p>

          {filteredMaterials.length === 0 ? (
            <p className="muted">No lecture materials synced yet. Connect APU Moodle or upload a downloaded slide deck below.</p>
          ) : (
            <div className="moodle-list">
              {filteredMaterials.map((m) => (
                <article key={m.id} className="moodle-item">
                  <div className="moodle-item-top">
                    <span className="moodle-course-tag">{m.courseName}</span>
                    <span className="moodle-section-tag">{m.section}</span>
                  </div>
                  <h3 className="h3">{m.title}</h3>
                  <p className="muted">{m.summary}</p>
                  {m.files && m.files.length > 0 && (
                    <div className="moodle-files">
                      {m.files.map((f) => <code key={f} className="moodle-file-badge">{f}</code>)}
                    </div>
                  )}
                  {m.concepts && m.concepts.length > 0 && (
                    <div className="moodle-concepts">
                      <div className="label">Prerequisite checkpoints ({m.readiness})</div>
                      <div className="moodle-chip-row">
                        {m.concepts.map((c) => (
                          <span key={c.conceptId} className="moodle-concept-pill">
                            <b>{c.name}</b> <StateChip state={c.state} />
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  <div className="moodle-item-actions">
                    <button type="button" className="btn primary small" onClick={() => startDiagnosisFromItem(m)}>
                      Diagnose this lecture
                    </button>
                    {m.url && (
                      <a className="btn ghost small" href={m.url} target="_blank" rel="noreferrer">
                        Moodle folder ↗
                      </a>
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      </div>

      <section className="card moodle-import-card">
        <div className="eyebrow">Direct Slide & Material Import</div>
        <h2 className="h2">Upload a downloaded Moodle slide deck (.pptx) or paste lecture notes</h2>
        <p className="muted">
          Downloaded a <code>.pptx</code> deck from APU Moodle’s <em>Lecture Slides Folder</em>? Upload it here—Punca extracts the slide text, maps the concepts, and checks your prerequisite foundations.
        </p>
        <form className="moodle-import-form" onSubmit={handleImport}>
          <div className="row2">
            <label className="field">
              Lecture or assignment title <small>(optional)</small>
              <input
                value={importTitle}
                onChange={(e) => setImportTitle(e.target.value)}
                maxLength={120}
                placeholder="e.g. PFDA Lecture 05B — Logistic Regression & Cross-Entropy"
              />
            </label>
            <label className="field">
              Course / module <small>(optional)</small>
              <input
                value={importCourse}
                onChange={(e) => setImportCourse(e.target.value)}
                maxLength={120}
                placeholder="e.g. Programming for Data Analysis (092026-KLT)"
              />
            </label>
          </div>
          <label className="field">
            Moodle slide file (<code>.pptx</code>, <code>.txt</code>, <code>.md</code>)
            <input
              type="file"
              accept=".pptx,.txt,.md,.csv"
              onChange={(e) => setImportFile(e.target.files && e.target.files[0] ? e.target.files[0] : null)}
            />
          </label>
          <label className="field">
            Or paste slide / assignment excerpt
            <textarea
              rows={3}
              maxLength={2000}
              value={importText}
              onChange={(e) => setImportText(e.target.value)}
              placeholder="Paste text from a Moodle lecture slide, lab sheet, or assignment brief..."
            />
          </label>
          <ErrorNote error={importError} />
          <div className="actions">
            <button
              type="submit"
              className="btn primary"
              disabled={importing || (!importFile && importText.trim().length < 5)}
            >
              {importing ? 'Extracting & mapping...' : 'Import & map to Punca concepts'}
            </button>
          </div>
        </form>
      </section>
    </div>
  )
}
