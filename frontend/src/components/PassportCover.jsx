import React from 'react'

export const COVERS = {
  navy: { label: 'Navy', bg: '#1d3446' },
  maroon: { label: 'Maroon', bg: '#5a1f2b' },
  forest: { label: 'Forest', bg: '#1f4a35' },
  teal: { label: 'Teal', bg: '#0b4f4c' },
  plum: { label: 'Plum', bg: '#3d2a4f' },
}

export const EMBLEMS = {
  spring: { label: 'Spring', d: <path d="M12 3c-3 4-6 7-6 11a6 6 0 0 0 12 0c0-4-3-7-6-11z" /> },
  compass: { label: 'Compass', d: <><circle cx="12" cy="12" r="9" /><path d="M15.5 8.5l-2 5-5 2 2-5z" /></> },
  atom: {
    label: 'Atom',
    d: <><ellipse cx="12" cy="12" rx="9.5" ry="3.8" /><ellipse cx="12" cy="12" rx="9.5" ry="3.8" transform="rotate(60 12 12)" />
      <ellipse cx="12" cy="12" rx="9.5" ry="3.8" transform="rotate(120 12 12)" /><circle cx="12" cy="12" r="1.4" /></>,
  },
  leaf: { label: 'Leaf', d: <><path d="M5 19C5 11 11 5 19 5c0 8-6 14-14 14z" /><path d="M5 19l8-8" /></> },
  star: { label: 'Star', d: <path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z" /> },
}

export function Emblem({ name = 'spring', size = 28 }) {
  const e = EMBLEMS[name] || EMBLEMS.spring
  return (
    <svg className="emblem" viewBox="0 0 24 24" width={size} height={size} fill="none" stroke="currentColor"
      strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{e.d}</svg>
  )
}

/** The coloured passport cover used on the passport page and as the live preview while customising. */
export default function PassportCover({ style = {}, holder, holderNo, module, programme, year, focusLabs = [], stamps, endorsed, compact }) {
  const cover = COVERS[style.cover] || COVERS.navy
  return (
    <div className={`pp-cover ${compact ? 'compact' : ''}`} style={{ background: cover.bg }}>
      <div className="pp-brandline">
        <span className="pp-emblem"><Emblem name={style.emblem} size={compact ? 30 : 36} /></span>
        <div>
          <div className="pp-title">PUNCA PASSPORT</div>
          <div className="pp-sub">Pasport Punca · study aid, not a grade or credential</div>
        </div>
      </div>
      <div className="pp-holder">
        <div><span>Holder</span><b>{holder || 'Your name'}</b></div>
        <div><span>No.</span><b>{holderNo || 'Student #A-0000'}</b></div>
        {programme && <div><span>Programme</span><b>{programme}{year ? ` · Year ${year}` : ''}</b></div>}
        <div><span>Module</span><b>{module}</b></div>
        {focusLabs.length > 0 && <div><span>Trips</span><b>{focusLabs.map((l) => l.split(':')[0]).join(', ')}</b></div>}
        {style.motto && <div className="pp-motto">“{style.motto}”</div>}
      </div>
      {stamps !== undefined && (
        <div className="pp-count"><b>{stamps}</b><span>stamps</span><b>{endorsed}</b><span>endorsed</span></div>
      )}
    </div>
  )
}
