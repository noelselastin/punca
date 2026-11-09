import React from 'react'

export const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
export const HOURS = [9, 10, 11, 12, 13, 14, 15, 16, 17]

/** Weekly one-hour availability grid. value: ["Tue-14", ...] */
export default function AvailabilityGrid({ value, onChange, readOnly }) {
  const set = new Set(value || [])
  const toggle = (slot) => {
    if (readOnly) return
    const next = new Set(set)
    if (next.has(slot)) next.delete(slot)
    else next.add(slot)
    onChange([...next])
  }
  return (
    <div className="avail" role="grid" aria-label="Weekly free hours">
      <div className="avail-row head"><span />{DAYS.map((d) => <span key={d}>{d}</span>)}</div>
      {HOURS.map((h) => (
        <div key={h} className="avail-row">
          <span className="hour">{String(h).padStart(2, '0')}:00</span>
          {DAYS.map((d) => {
            const slot = `${d}-${h}`
            const on = set.has(slot)
            return (
              <button key={slot} type="button" className={on ? 'cell on' : 'cell'} aria-pressed={on}
                aria-label={`${d} ${h}:00 ${on ? 'free' : 'busy'}`} onClick={() => toggle(slot)} disabled={readOnly} />
            )
          })}
        </div>
      ))}
    </div>
  )
}
