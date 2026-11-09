import React, { useState } from 'react'
import { api } from '../api.js'
import { ErrorNote } from '../components/common.jsx'
import { DEMO_STAFF, DEMO_STUDENT } from '../demo.js'

/** mode = 'signup' (create a passport) or 'signin'. */
export default function AuthPage({ mode, onAuthed, health }) {
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value })
  const signup = mode === 'signup'

  const submit = async (e, creds) => {
    if (e) e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const r = creds
        ? await api('/auth/login', { method: 'POST', body: creds })
        : signup
          ? await api('/auth/signup', { method: 'POST', body: form })
          : await api('/auth/login', { method: 'POST', body: { email: form.email, password: form.password } })
      onAuthed(r.token, r.user, signup && !creds)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth">
      <section className="auth-hero">
        <a className="back-link" href="#/">← Back to Punca</a>
        <div className="brand big">
          <svg viewBox="0 0 64 64" aria-hidden="true"><path d="M32 8c-8 10-16 18-16 28a16 16 0 0 0 32 0c0-10-8-18-16-28z" /><circle cx="32" cy="38" r="5" /></svg>
          <span>Punca</span>
        </div>
        {signup ? (
          <>
            <p className="tagline">Apply for your Punca Passport</p>
            <p className="tagline-en">Step 1 of 2: create your student account. Next you’ll customise your passport.</p>
            <ol className="apply-steps">
              <li className="on"><b>Your account</b><span>Name, email and a password</span></li>
              <li><b>Your passport</b><span>Cover, emblem, the name on it, your goal and labs</span></li>
              <li><b>Your first stamp</b><span>Tell Punca where you’re stuck; pass a re-check to get stamped</span></li>
            </ol>
          </>
        ) : (
          <>
            <p className="tagline">Welcome back</p>
            <p className="tagline-en">Sign in to open your passport and pick up your route.</p>
          </>
        )}
      </section>

      <section className="auth-card card">
        <h1 className="h2">{signup ? 'Create your student account' : 'Sign in'}</h1>
        <form onSubmit={submit} className="form">
          {signup && (
            <label>Full name<input value={form.name} onChange={set('name')} autoComplete="name" required minLength={2} maxLength={60} /></label>
          )}
          <label>Email<input type="email" value={form.email} onChange={set('email')} autoComplete="email" required /></label>
          <label>Password
            <input type="password" value={form.password} onChange={set('password')} required minLength={8}
              autoComplete={signup ? 'new-password' : 'current-password'} />
            {signup && <small>At least 8 characters.</small>}
          </label>
          <ErrorNote error={error} />
          <button className="btn primary wide" disabled={busy}>{busy ? 'Please wait...' : signup ? 'Continue to my passport' : 'Sign in'}</button>
        </form>
        <p className="switch">
          {signup
            ? <>Already have a passport? <a href="#/signin">Sign in</a></>
            : <>New to Punca? <a href="#/join">Create your passport</a></>}
        </p>
        {!signup && (
          <div className="demo-box">
            <span>Hackathon demo</span>
            <button className="btn ghost small" disabled={busy} onClick={() => submit(null, DEMO_STUDENT)}>Try the demo student</button>
            <button className="btn ghost small" disabled={busy} onClick={() => submit(null, DEMO_STAFF)}>Lecturer view (demo staff)</button>
          </div>
        )}
        {health && health.llm && health.llm.mode === 'offline' && (
          <p className="fine">Running in offline mode ({health.llm.reason}). Mapping uses keyword search and explanations show the course notes directly.</p>
        )}
      </section>
    </div>
  )
}
