import React from 'react'

export function go(page, id) {
  window.location.hash = '/' + page + (id ? '/' + id : '')
}

export function Spinner({ label = 'Loading' }) {
  return <div className="spinner" role="status"><span className="dot" />{label}...</div>
}

export function ErrorNote({ error }) {
  if (!error) return null
  return <div className="error-note" role="alert">{error.message || String(error)}</div>
}

export function Toggle({ checked, onChange, label, hint }) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={!!checked} onChange={(e) => onChange(e.target.checked)} />
      <span className="track"><span className="knob" /></span>
      <span className="toggle-text">{label}{hint && <small>{hint}</small>}</span>
    </label>
  )
}

export const STATE_LABEL = {
  solid: 'Solid', stamped: 'Stamped', endorsed: 'Endorsed', shaky: 'Shaky',
  gap: 'Gap', 'entry-required': 'Entry required', untested: 'Untested',
}

export function StateChip({ state }) {
  return <span className={`chip state-${state}`}>{STATE_LABEL[state] || state}</span>
}

export function useAsync(fn, deps) {
  const [state, setState] = React.useState({ loading: true, data: null, error: null })
  const reload = React.useCallback(() => {
    setState((s) => ({ ...s, loading: true, error: null }))
    return fn().then(
      (data) => setState({ loading: false, data, error: null }),
      (error) => setState({ loading: false, data: null, error }),
    )
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  React.useEffect(() => { reload() }, [reload])
  return [state, reload]
}
