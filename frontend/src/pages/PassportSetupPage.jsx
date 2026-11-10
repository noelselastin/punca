import React, { useRef, useState } from 'react'
import { api } from '../api.js'
import AvailabilityGrid from '../components/AvailabilityGrid.jsx'
import { ErrorNote, Toggle, go } from '../components/common.jsx'
import PassportCover, { COVERS, PassportPhoto } from '../components/PassportCover.jsx'

function resizeImageToDataUrl(file, maxSide = 180) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Could not read the selected image file.'))
    reader.onload = () => {
      const img = new Image()
      img.onerror = () => reject(new Error('Selected file is not a valid image.'))
      img.onload = () => {
        const canvas = document.createElement('canvas')
        canvas.width = maxSide
        canvas.height = maxSide
        const ctx = canvas.getContext('2d')
        const side = Math.min(img.width, img.height)
        const sx = Math.floor((img.width - side) / 2)
        const sy = Math.floor((img.height - side) / 2)
        ctx.drawImage(img, sx, sy, side, side, 0, 0, maxSide, maxSide)
        resolve(canvas.toDataURL('image/jpeg', 0.86))
      }
      img.src = reader.result
    }
    reader.readAsDataURL(file)
  })
}

/** Step 2 of joining (and "Customise" later): make the passport yours. */
export default function PassportSetupPage({ user, catalog, onUser }) {
  const first = !(user.passportStyle && user.passportStyle.setupDone)
  const st = user.passportStyle || {}
  const [style, setStyle] = useState({
    cover: st.cover || 'navy',
    displayName: st.displayName || user.name,
    photoUrl: st.photoUrl || null,
    motto: st.motto || '',
    focusLabIds: st.focusLabIds || [],
    customLabs: st.customLabs || [],
  })
  const [customLabInput, setCustomLabInput] = useState('')
  const [programme, setProgramme] = useState(user.programme || '')
  const [year, setYear] = useState(user.year || '')
  const [consent, setConsent] = useState({ ...user.consent })
  const [avail, setAvail] = useState(user.availability || [])
  const [showHours, setShowHours] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const photoInputRef = useRef(null)

  const set = (k, v) => setStyle((prev) => ({ ...prev, [k]: v }))
  const toggleLab = (id) =>
    set(
      'focusLabIds',
      style.focusLabIds.includes(id)
        ? style.focusLabIds.filter((x) => x !== id)
        : [...style.focusLabIds, id]
    )

  const addCustomLab = () => {
    const trimmed = customLabInput.trim()
    if (!trimmed) return
    if (!style.customLabs.includes(trimmed)) {
      set('customLabs', [...style.customLabs, trimmed.slice(0, 80)])
    }
    setCustomLabInput('')
  }

  const removeCustomLab = (labName) => {
    set('customLabs', style.customLabs.filter((x) => x !== labName))
  }

  const handlePhotoUpload = async (e) => {
    const file = e.target.files && e.target.files[0]
    if (!file) return
    setError(null)
    try {
      const dataUrl = await resizeImageToDataUrl(file, 180)
      set('photoUrl', dataUrl)
    } catch (err) {
      setError(err)
    } finally {
      if (photoInputRef.current) photoInputRef.current.value = ''
    }
  }

  const labs = catalog.labs

  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const body = {
        passport: {
          ...style,
          motto: style.motto || null,
        },
        programme,
        consent,
        availability: avail,
      }
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

  const previewLabs = [
    ...labs.filter((l) => style.focusLabIds.includes(l.id)).map((l) => l.name),
    ...style.customLabs,
  ]

  return (
    <div className="setup">
      <div className="setup-head">
        {first && <div className="eyebrow">Step 2 of 2</div>}
        <h1 className="h1">{first ? 'Make the passport yours' : 'Customise your passport'}</h1>
        <p className="muted">Everything here is optional and can be changed later. Upload your passport portrait or keep the default person image.</p>
      </div>
      <div className="setup-grid">
        <form className="card setup-form" onSubmit={save}>
          <label className="field">Name on your passport
            <input value={style.displayName} onChange={(e) => set('displayName', e.target.value)} minLength={2} maxLength={40} required />
          </label>

          <div className="field">
            <span>Passport photo <small>(upload from PC or use default person portrait)</small></span>
            <div className="pp-photo-UploadRow">
              <PassportPhoto photoUrl={style.photoUrl} holder={style.displayName} size={68} />
              <div className="pp-photo-controls">
                <input
                  ref={photoInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handlePhotoUpload}
                  style={{ display: 'none' }}
                />
                <div className="actions left" style={{ marginTop: 0 }}>
                  <button
                    type="button"
                    className="btn small"
                    onClick={() => photoInputRef.current && photoInputRef.current.click()}
                  >
                    Upload photo from PC
                  </button>
                  {style.photoUrl && (
                    <button
                      type="button"
                      className="btn ghost small"
                      onClick={() => set('photoUrl', null)}
                    >
                      Use default person image
                    </button>
                  )}
                </div>
                <small className="fine">Square-cropped automatically. Stored with your passport profile.</small>
              </div>
            </div>
          </div>

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

          <label className="field">My goal this semester <small>(optional, shown on the cover)</small>
            <input value={style.motto} onChange={(e) => set('motto', e.target.value)} maxLength={80} placeholder="e.g. Master CS & AI foundations without guessing" />
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
            <span>Labs I’m working on <small>(select modules below or add your own)</small></span>
            <div className="examples">
              {labs.map((l) => (
                <button
                  type="button"
                  key={l.id}
                  className={`chip-btn ${style.focusLabIds.includes(l.id) ? 'on' : ''}`}
                  onClick={() => toggleLab(l.id)}
                >
                  {l.name}
                </button>
              ))}
              {style.customLabs.map((custom) => (
                <button
                  type="button"
                  key={custom}
                  className="chip-btn on"
                  onClick={() => removeCustomLab(custom)}
                  title="Click to remove custom lab"
                >
                  {custom} <span aria-hidden="true">×</span>
                </button>
              ))}
            </div>
            <div className="lab-add-row">
              <input
                type="text"
                value={customLabInput}
                onChange={(e) => setCustomLabInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    addCustomLab()
                  }
                }}
                maxLength={80}
                placeholder="Add another lab or module (e.g. CS205 Operating Systems Lab 3)"
              />
              <button
                type="button"
                className="btn small"
                onClick={addCustomLab}
                disabled={!customLabInput.trim()}
              >
                + Add
              </button>
            </div>
          </div>

          <div className="field">
            <span>Peer Study Circle Preferences</span>
            <div className="consents">
              <Toggle checked={consent.joinCircles} label="Suggest me for peer study circles" hint="Opt-in: you are only grouped with peers sharing a gap if this is on."
                onChange={(v) => setConsent({ ...consent, joinCircles: v })} />
              <Toggle checked={consent.shareNameWithCircle} label="Show my name to my study circle"
                onChange={(v) => setConsent({ ...consent, shareNameWithCircle: v })} />
            </div>
          </div>

          <div className="field">
            <button type="button" className="linkish" onClick={() => setShowHours(!showHours)}>
              {showHours ? 'Hide' : 'Add'} my weekly free hours <small>(used to find peer study-circle times)</small>
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
          <PassportCover
            style={style}
            holder={style.displayName}
            holderNo={user.studentId || 'TP000000'}
            module={catalog.course.name}
            university={user.university}
            studentId={user.studentId}
            programme={programme}
            year={year}
            focusLabs={previewLabs}
            stamps={0}
            compact
          />
          <p className="fine">Your student ID serves as your Punca Passport number.</p>
        </aside>
      </div>
    </div>
  )
}
