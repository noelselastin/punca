import React from 'react'
import { api } from '../api.js'
import { ErrorNote, Spinner, useAsync } from '../components/common.jsx'

export default function HistoryPage() {
  const [list] = useAsync(() => api('/diagnoses'), [])
  return (
    <div className="card narrow-card">
      <h1 className="h2">My diagnoses</h1>
      {list.loading && <Spinner />}
      <ErrorNote error={list.error} />
      {list.data && list.data.length === 0 && <p className="muted">Nothing yet. <a href="#/diagnose">Run your first diagnosis</a>.</p>}
      {list.data && list.data.length > 0 && (
        <ul className="history">
          {list.data.map((d) => (
            <li key={d.id}>
              <a href={d.status === 'done' ? `#/diagnosis/${d.id}` : '#/diagnose'}>
                <div className="h-top"><b>{d.targetName}</b><span>{new Date(d.createdAt).toLocaleString()}</span></div>
                <div className="h-q">"{d.stuckInput}"</div>
                <div className="h-r">{d.status !== 'done' ? 'Not finished' : d.rootCauseName ? `Root cause: ${d.rootCauseName}` : 'No gap found'}</div>
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
