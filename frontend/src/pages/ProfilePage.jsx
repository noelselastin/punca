import React, { useState } from 'react'
import { api } from '../api.js'
import { ErrorNote, go } from '../components/common.jsx'

/** Edit profile: the personal details given at sign-up can be changed here at any time. */
export default function ProfilePage({ user, onUser }) {
  const [form, setForm] = useState({
    name: user.name || '',
    email: user.email || '',
    university: user.university || '',
    studentId: user.studentId || '',
    programme: user.programme || '',
    year: user.year || '',
  })
  const [busy, setBusy] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)
  const set = (k) => (e) => {
    setForm({ ...form, [k]: e.target.value })
    setSaved(false)
  }
  const demo = Boolean(user.demoAccount)

  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setSaved(false)
    try {
      const body = {
        name: form.name,
        university: form.university,
        programme: form.programme,
        year: form.year === '' ? '' : Number(form.year),
      }
      // Demo accounts keep their sign-in email and student ID, so those are not sent.
      if (!demo) {
        body.email = form.email
        body.studentId = form.studentId
      }
      const updated = await api('/me', { method: 'PATCH', body })
      onUser(updated)
      setForm({
        name: updated.name || '',
        email: updated.email || '',
        university: updated.university || '',
        studentId: updated.studentId || '',
        programme: updated.programme || '',
        year: updated.year || '',
      })
      setSaved(true)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="narrow">
      <form className="card" onSubmit={save}>
        <div className="eyebrow">Your account</div>
        <h1 className="h1">Edit profile</h1>
        <p className="muted">
          Change the details you gave when you signed up. Your student ID is also your passport number.
        </p>

        <label className="field">Full name
          <input value={form.name} onChange={set('name')} required minLength={2} maxLength={60} autoComplete="name" />
        </label>
        <label className="field">Personal email address
          <input
            type="email"
            value={form.email}
            onChange={set('email')}
            required
            disabled={demo}
            placeholder="you@example.com"
            autoComplete="email"
          />
          <small>
            {demo
              ? 'Demo accounts keep their sign-in email.'
              : 'You sign in with this address. Study partners see it only if you choose to share it.'}
          </small>
        </label>
        <div className="row2">
          <label className="field">University
            <input value={form.university} onChange={set('university')} required minLength={2} maxLength={120} />
          </label>
          <label className="field">Student ID
            <input
              value={form.studentId}
              onChange={set('studentId')}
              required
              disabled={demo}
              maxLength={40}
              pattern={String.raw`[A-Za-z0-9][A-Za-z0-9._\/\-]{0,39}`}
              title="Up to 40 letters or numbers, with dots, hyphens, underscores or slashes."
            />
          </label>
        </div>
        <div className="row2">
          <label className="field">Course
            <input value={form.programme} onChange={set('programme')} maxLength={80} placeholder="e.g. BSc (Hons) Computer Science" />
          </label>
          <label className="field">Year of study
            <select value={form.year} onChange={set('year')}>
              <option value="">Not set</option>
              {[1, 2, 3, 4, 5].map((y) => <option key={y} value={y}>Year {y}</option>)}
            </select>
          </label>
        </div>

        <ErrorNote error={error} />
        <div className="actions">
          {saved && <span className="fine"><b>Profile saved.</b></span>}
          <button type="button" className="btn ghost" onClick={() => go('passport')}>Back to passport</button>
          <button className="btn primary" disabled={busy}>{busy ? 'Saving...' : 'Save changes'}</button>
        </div>
        <p className="fine">
          To change your passport cover, photo, display name or motto, use{' '}
          <a href="#/setup">Customise passport</a>.
        </p>
      </form>
    </div>
  )
}
