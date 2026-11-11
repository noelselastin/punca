import React from 'react'

export const COVERS = {
  navy: { label: 'Navy', bg: '#17374c' },
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

/** Default person portrait image shown on the passport when the student has not uploaded a photo. */
export function DefaultPersonPortrait({ size = 56 }) {
  return (
    <svg
      className="pp-person-svg"
      viewBox="0 0 64 64"
      width={size}
      height={size}
      role="img"
      aria-label="Default student portrait"
    >
      <defs>
        <linearGradient id="ppAvatarBg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#264b66" />
          <stop offset="100%" stopColor="#132c3e" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="12" fill="url(#ppAvatarBg)" />
      <circle cx="32" cy="24" r="11" fill="#f3ead8" opacity="0.92" />
      <path
        d="M14 56c2-11 10-17 18-17s16 6 18 17"
        fill="#f3ead8"
        opacity="0.92"
      />
      <rect
        x="1.5"
        y="1.5"
        width="61"
        height="61"
        rx="10.5"
        fill="none"
        stroke="#e5b65a"
        strokeOpacity="0.65"
        strokeWidth="1.5"
      />
    </svg>
  )
}

export function PassportPhoto({ photoUrl, holder, size = 56 }) {
  if (photoUrl) {
    return (
      <span className="pp-photo-frame" style={{ width: size, height: size }}>
        <img
          src={photoUrl}
          alt={holder ? `${holder}'s passport photo` : 'Passport photo'}
          className="pp-photo-img"
        />
      </span>
    )
  }
  return (
    <span className="pp-photo-frame pp-photo-default" style={{ width: size, height: size }}>
      <DefaultPersonPortrait size={size} />
    </span>
  )
}

/** The coloured passport cover used on the passport page and as the live preview while customising. */
export default function PassportCover({
  style = {},
  holder,
  holderNo,
  university,
  studentId,
  module,
  programme,
  year,
  focusLabs = [],
  stamps,
  compact,
}) {
  const cover = COVERS[style.cover] || COVERS.navy
  const photoSize = compact ? 52 : 64
  return (
    <div className={`pp-cover ${compact ? 'compact' : ''}`} style={{ background: cover.bg }}>
      <div className="pp-brandline">
        <PassportPhoto photoUrl={style.photoUrl} holder={holder} size={photoSize} />
        <div>
          <div className="pp-title">PUNCA PASSPORT</div>
          <div className="pp-sub">Passport Punca · study aid, not a grade or credential</div>
        </div>
      </div>
      <div className="pp-holder">
        <div><span>Holder</span><b>{holder || 'Your name'}</b></div>
        <div><span>No.</span><b>{studentId || holderNo || '—'}</b></div>
        {university && <div><span>University</span><b>{university}</b></div>}
        {programme && <div><span>Course</span><b>{programme}{year ? ` · Year ${year}` : ''}</b></div>}
        <div><span>Module</span><b>{module}</b></div>
        {focusLabs.length > 0 && (
          <div><span>Labs</span><b>{focusLabs.map((l) => l.split(':')[0]).join(', ')}</b></div>
        )}
        {style.motto && <div className="pp-motto">“{style.motto}”</div>}
      </div>
      {stamps !== undefined && (
        <div className="pp-count"><b>{stamps}</b><span>completed stamps</span></div>
      )}
    </div>
  )
}
