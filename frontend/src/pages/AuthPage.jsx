import React, { useState } from 'react'
import { api } from '../api.js'
import { ErrorNote } from '../components/common.jsx'
import { DEMO_ACCOUNTS, DEMO_PASSWORD } from '../demo.js'
import Brand from '../components/Brand.jsx'

/** mode = 'signup' (create a passport) or 'signin'. */
export default function AuthPage({ mode, onAuthed, health }) {
  const [form, setForm] = useState({ name: '', university: '', email: '', studentId: '', programme: '', password: '', confirmPassword: '' })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const set = (k) => (e) => setForm(previous => ({ ...previous, [k]: e.target.value }))
  const signup = mode === 'signup'

  const submit = async (e, creds) => {
    if (e) e.preventDefault()
    if (signup && !creds && form.password !== form.confirmPassword) {
      setError(new Error('Passwords do not match. Please enter the same password in both fields.'))
      return
    }
    setBusy(true)
    setError(null)
    try {
      const r = creds
        ? await api('/auth/login', { method: 'POST', body: creds })
        : signup
          ? await api('/auth/signup', { method: 'POST', body: form })
          : await api('/auth/login', { method: 'POST', body: { email: form.email, password: form.password } })
      const needsSetup = (signup && !creds) || r.user?.passportStyle?.setupDone === false
      onAuthed(r.token, r.user, needsSetup)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className={`auth ${signup ? 'auth-signup' : 'auth-signin'}`}>
      <section className="auth-hero">
        <a className="back-link" href="#/">← Back to Punca</a>
        <Brand large />
        {signup ? (
          <>
            <p className="eyebrow auth-eyebrow">YOUR LEARNING JOURNEY</p>
            <p className="tagline">Your next chapter.<br /><em>Starts here.</em></p>
            <p className="tagline-en">Step 1 of 2: create your student account with your personal Gmail. Next you’ll customise your passport.</p>
            <ol className="apply-steps">
              <li className="on"><b>Your account</b><span>Your personal Gmail (for Google Calendar & Docs), student ID and password</span></li>
              <li><b>Your passport</b><span>Cover, portrait photo, the name on it, your goal and labs</span></li>
              <li><b>Your first stamp</b><span>Tell Punca where you’re stuck; pass a re-check to get stamped</span></li>
            </ol>
          </>
        ) : (
          <>
            <p className="eyebrow auth-eyebrow">READY WHEN YOU ARE</p>
            <p className="tagline">Welcome<br /><em>back.</em></p>
            <p className="tagline-en">Sign in to open your passport and pick up your route.</p>
          </>
        )}
      </section>

      <section className="auth-card card">
        <p className="eyebrow">{signup ? '01 / YOUR ACCOUNT' : 'YOUR PUNCA PASSPORT'}</p>
        <h1 className="h2">{signup ? 'Create your student account' : 'Sign in'}</h1>
        <form onSubmit={submit} className="form">
          <fieldset disabled={busy} className="auth-fields">
            {signup && (
              <>
                <label>Full name<input name="name" value={form.name} onChange={set('name')} autoComplete="name" required minLength={2} maxLength={60} /></label>
                <label>University<input name="university" value={form.university} onChange={set('university')} autoComplete="organization" required minLength={2} maxLength={120} placeholder="e.g. Asia Pacific University" /></label>
              </>
            )}
            <label>
              {signup ? 'Personal Gmail address' : 'Email'}
              <input
                name="email"
                type="email"
                value={form.email}
                onChange={set('email')}
                autoComplete="email"
                placeholder={signup ? 'you@gmail.com' : 'you@gmail.com'}
                required
                maxLength={120}
              />
              {signup && (
                <small>
                  Use your personal <b>@gmail.com</b> address (not your university email) — Punca connects Google Calendar and Google Docs to it.
                </small>
              )}
            </label>
            {signup && (
              <div className="auth-field-row">
                <label>
                  Student ID
                  <input
                    name="studentId"
                    value={form.studentId}
                    onChange={set('studentId')}
                    autoComplete="off"
                    required
                    maxLength={40}
                    placeholder="e.g. TP068421"
                    pattern={String.raw`[A-Za-z0-9][A-Za-z0-9._\/\-]{0,39}`}
                    title="Up to 40 letters or numbers, with dots, hyphens, underscores or slashes."
                  />
                  <small>Used as your Passport No.</small>
                </label>
                <label>Course<input name="programme" value={form.programme} onChange={set('programme')} autoComplete="off" required minLength={2} maxLength={80} placeholder="e.g. BSc Computer Science" /></label>
              </div>
            )}
            <div className={signup ? 'auth-field-row' : undefined}>
              <label>Password
                <input name="password" type="password" value={form.password} onChange={set('password')} required minLength={8} maxLength={128}
                  autoComplete={signup ? 'new-password' : 'current-password'} />
                {signup && <small>At least 8 characters.</small>}
              </label>
              {signup && (
                <label>Confirm password
                  <input name="confirmPassword" type="password" value={form.confirmPassword} onChange={set('confirmPassword')} autoComplete="new-password" required minLength={8} maxLength={128}
                    aria-invalid={form.confirmPassword.length > 0 && form.confirmPassword !== form.password}
                    aria-describedby={form.confirmPassword && form.confirmPassword !== form.password ? 'password-match-note' : undefined} />
                  {form.confirmPassword && form.confirmPassword !== form.password && <small id="password-match-note" className="field-error">Passwords do not match.</small>}
                </label>
              )}
            </div>
            <ErrorNote error={error} />
            <button className="btn primary wide" disabled={busy}>
              {busy ? 'Please wait...' : signup ? 'Continue to my passport' : 'Sign in'}
              <span aria-hidden="true">↗</span>
            </button>
          </fieldset>
        </form>
        <p className="switch">
          {signup
            ? <>Already have a passport? <a href="#/signin">Sign in</a></>
            : <>New to Punca? <a href="#/join">Create your passport</a></>}
        </p>

        <div className="demo-accounts-box">
          <div className="demo-accounts-head">
            <span className="eyebrow">DEMO & TESTING ACCOUNTS (1-CLICK SIGN-IN)</span>
            <span className="fine">Password: <code>{DEMO_PASSWORD}</code></span>
          </div>
          <div className="demo-accounts-grid">
            {DEMO_ACCOUNTS.map(acc => (
              <button
                key={acc.email}
                type="button"
                className="demo-account-btn"
                disabled={busy}
                onClick={() => submit(null, { email: acc.email, password: DEMO_PASSWORD })}
              >
                <div className="demo-account-top">
                  <strong>{acc.label}</strong>
                  <span className="demo-account-id">{acc.studentId}</span>
                </div>
                <span className="demo-account-hint">{acc.hint}</span>
              </button>
            ))}
          </div>
        </div>

        {health && health.llm && health.llm.mode === 'offline' && (
          <p className="fine">Running in offline mode ({health.llm.reason}). Mapping uses keyword search and explanations show the course notes directly.</p>
        )}
      </section>
    </main>
  )
}
