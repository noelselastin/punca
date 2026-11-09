import React, { useState } from 'react'
import { api } from '../api.js'
import { ErrorNote } from '../components/common.jsx'
import { DEMO_STAFF, DEMO_STUDENT } from '../demo.js'

export default function AuthPage({ onAuthed, health }) {
  const [mode, setMode] = useState('signin')
  const [form, setForm] = useState({ name: '', email: '', password: '', programme: '', year: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const submit = async (e, creds) => {
    if (e) e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const r = creds
        ? await api('/auth/login', { method: 'POST', body: creds })
        : mode === 'signin'
          ? await api('/auth/login', { method: 'POST', body: { email: form.email, password: form.password } })
          : await api('/auth/signup', { method: 'POST', body: { ...form, year: form.year || null } })
      onAuthed(r.token, r.user)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <section className="auth-hero">
        <div className="brand big">
          <svg viewBox="0 0 64 64" aria-hidden="true"><path d="M32 8c-8 10-16 18-16 28a16 16 0 0 0 32 0c0-10-8-18-16-28z" /><circle cx="32" cy="38" r="5" /></svg>
          <span>Punca</span>
        </div>
        <p className="tagline">Cari puncanya, bukan sekadar jawapannya.</p>
        <p className="tagline-en">Find the cause, not just the answer.</p>
        <ul className="hero-points">
          <li><b>Tell us where you are stuck.</b> A lab question, a slide, or a sentence.</li>
          <li><b>Answer up to 5 quick checks.</b> Punca traces the gap back through the prerequisites.</li>
          <li><b>Fix the real gap.</b> Cited notes, practice, a study circle and a lecturer slot.</li>
          <li><b>Earn passport stamps</b> when a re-check proves you have closed it.</li>
        </ul>
      </section>

      <section className="auth-card card">
        <div className="tabs">
          <button className={mode === 'signin' ? 'on' : ''} onClick={() => { setMode('signin'); setError(null) }}>Sign in</button>
          <button className={mode === 'signup' ? 'on' : ''} onClick={() => { setMode('signup'); setError(null) }}>Create student account</button>
        </div>
        <form onSubmit={submit} className="form">
          {mode === 'signup' && (
            <label>Full name<input value={form.name} onChange={set('name')} autoComplete="name" required minLength={2} maxLength={60} /></label>
          )}
          <label>Email<input type="email" value={form.email} onChange={set('email')} autoComplete="email" required /></label>
          <label>Password
            <input type="password" value={form.password} onChange={set('password')} required minLength={8}
              autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} />
            {mode === 'signup' && <small>At least 8 characters.</small>}
          </label>
          {mode === 'signup' && (
            <div className="row2">
              <label>Programme <small>(optional)</small><input value={form.programme} onChange={set('programme')} placeholder="e.g. BSc (Hons) Computer Science" maxLength={80} /></label>
              <label>Year <small>(optional)</small>
                <select value={form.year} onChange={set('year')}>
                  <option value="">-</option>{[1, 2, 3, 4, 5].map((y) => <option key={y} value={y}>Year {y}</option>)}
                </select>
              </label>
            </div>
          )}
          <ErrorNote error={error} />
          <button className="btn primary wide" disabled={busy}>{busy ? 'Please wait...' : mode === 'signin' ? 'Sign in' : 'Create my student account'}</button>
        </form>
        <div className="demo-box">
          <span>Hackathon demo</span>
          <button className="btn ghost small" disabled={busy} onClick={() => submit(null, DEMO_STUDENT)}>Try the demo student</button>
          <button className="btn ghost small" disabled={busy} onClick={() => submit(null, DEMO_STAFF)}>Lecturer view (demo staff)</button>
        </div>
        {health && health.llm && health.llm.mode === 'offline' && (
          <p className="fine">Running in offline mode ({health.llm.reason}). Mapping uses keyword search and explanations show the course notes directly.</p>
        )}
      </section>
    </div>
  )
}
