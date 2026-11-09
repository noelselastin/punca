import React, { useState } from 'react'
import { api } from '../api.js'
import AvailabilityGrid from '../components/AvailabilityGrid.jsx'
import { ErrorNote, Toggle, go } from '../components/common.jsx'
import PassportCover, { COVERS, EMBLEMS, Emblem } from '../components/PassportCover.jsx'

/** Step 2 of joining (and "Customise" later): make the passport yours. */
export default function PassportSetupPage({ user, catalog, onUser }) {
  const first = !(user.passportStyle && user.passportStyle.setupDone)
  const st = user.passportStyle || {}
  const [style, setStyle] = useState({
    cover: st.cover || 'navy', emblem: st.emblem || 'spring', displayName: st.displayName || user.name,
    motto: st.motto || '', focusLabIds: st.focusLabIds || [],
  })
  const [programme, setProgramme] = useState(user.programme || '')
  const [year, setYear] = useState(user.year || '')
  const [consent, setConsent] = useState({ ...user.consent })
  const [avail, setAvail] = useState(user.availability || [])
  const [showHours, setShowHours] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const set = (k, v) => setStyle({ ...style, [k]: v })
  const toggleLab = (id) => set('focusLabIds', style.focusLabIds.includes(id) ? style.focusLabIds.filter((x) => x !== id) : [...style.focusLabIds, id])
  const labs = catalog.labs

  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const body = { passport: { ...style, motto: style.motto || null }, programme, consent, availability: avail }
      if (year) body.year = Number(year)
      const u = await api('/me', { method: 'PATCH', body })
      onUser(u)
      go('passport', first ? 'welcome' : undefined)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="setup">
      <div className="setup-head">
        {first && <div className="eyebrow">Step 2 of 2</div>}
        <h1 className="h1">{first ? 'Make the passport yours' : 'Customise your passport'}</h1>
        <p className="muted">Everything here is optional and can be changed later. Your passport stays private unless you choose to share it.</p>
      </div>
      <div className="setup-grid">
        <form className="card setup-form" onSubmit={save}>
          <label className="field">Name on your passport
            <input value={style.displayName} onChange={(e) => set('displayName', e.target.value)} minLength={2} maxLength={40} required />
          </label>

          <div className="field">
            <span>Cover</span>
            <div className="swatches" role="radiogroup" aria-label="Passport cover colour">
              {Object.entries(COVERS).map(([k, c]) => (
                <button type="button" key={k} role="radio" aria-checked={style.cover === k} aria-label={c.label}
                  className={`swatch ${style.cover === k ? 'on' : ''}`} style={{ background: c.bg }} onClick={() => set('cover', k)}>
                  <span>{c.label}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="field">
            <span>Emblem</span>
            <div className="emblems" role="radiogroup" aria-label="Passport emblem">
              {Object.entries(EMBLEMS).map(([k, e]) => (
                <button type="button" key={k} role="radio" aria-checked={style.emblem === k} aria-label={e.label}
                  className={`emblem-btn ${style.emblem === k ? 'on' : ''}`} onClick={() => set('emblem', k)}>
                  <Emblem name={k} size={26} /><span>{e.label}</span>
                </button>
              ))}
            </div>
          </div>

          <label className="field">My goal this semester <small>(optional, shown on the cover)</small>
            <input value={style.motto} onChange={(e) => set('motto', e.target.value)} maxLength={80} placeholder="e.g. Pass AI Methods without guessing" />
          </label>

          <div className="row2">
            <label className="field">Course <small>(from your account)</small>
              <input value={programme} onChange={(e) => setProgramme(e.target.value)} maxLength={80} placeholder="e.g. BSc (Hons) Computer Science (AI)" />
            </label>
            <label className="field">Year <small>(optional)</small>
              <select value={year} onChange={(e) => setYear(e.target.value)}>
                <option value="">-</option>{[1, 2, 3, 4, 5].map((y) => <option key={y} value={y}>Year {y}</option>)}
              </select>
            </label>
          </div>

          <div className="field">
            <span>Labs I’m working on <small>(your trips)</small></span>
            <div className="examples">
              {labs.map((l) => (
                <button type="button" key={l.id} className={`chip-btn ${style.focusLabIds.includes(l.id) ? 'on' : ''}`} onClick={() => toggleLab(l.id)}>{l.name}</button>
              ))}
            </div>
          </div>

          <div className="field">
            <span>Privacy</span>
            <div className="consents">
              <Toggle checked={consent.sharePassport} label="Share my passport with lecturers" hint="Off by default."
                onChange={(v) => setConsent({ ...consent, sharePassport: v })} />
              <Toggle checked={consent.joinCircles} label="Suggest me for study circles" hint="Opt-in: you are only grouped if this is on."
                onChange={(v) => setConsent({ ...consent, joinCircles: v })} />
              <Toggle checked={consent.shareNameWithCircle} label="Show my name to my circle"
                onChange={(v) => setConsent({ ...consent, shareNameWithCircle: v })} />
              <Toggle checked={consent.shareNameWithLecturer} label="Show my name to lecturers"
                onChange={(v) => setConsent({ ...consent, shareNameWithLecturer: v })} />
            </div>
          </div>

          <div className="field">
            <button type="button" className="linkish" onClick={() => setShowHours(!showHours)}>
              {showHours ? 'Hide' : 'Add'} my weekly free hours <small>(used to find study-circle times)</small>
            </button>
            {showHours && <AvailabilityGrid value={avail} onChange={setAvail} />}
          </div>

          <ErrorNote error={error} />
          <div className="actions">
            {!first && <button type="button" className="btn ghost" onClick={() => go('passport')}>Cancel</button>}
            <button className="btn primary" disabled={busy}>{busy ? 'Saving...' : first ? 'Issue my passport' : 'Save changes'}</button>
          </div>
        </form>

        <aside className="setup-preview">
          <div className="label">Live preview</div>
          <PassportCover style={style} holder={style.displayName} holderNo="Student #A-····" module={catalog.course.name}
            university={user.university} studentId={user.studentId}
            programme={programme} year={year} focusLabs={labs.filter((l) => style.focusLabIds.includes(l.id)).map((l) => l.name)}
            stamps={0} endorsed={0} compact />
          <p className="fine">Your passport number is assigned when the passport is issued.</p>
        </aside>
      </div>
    </div>
  )
}
