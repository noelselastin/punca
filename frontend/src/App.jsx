import React, { useEffect, useState } from 'react'
import { api, getToken, setToken, setUnauthorizedHandler } from './api.js'
import { go, Spinner } from './components/common.jsx'
import AuthPage from './pages/AuthPage.jsx'
import DiagnosePage from './pages/DiagnosePage.jsx'
import ResultPage from './pages/ResultPage.jsx'
import PassportPage from './pages/PassportPage.jsx'
import CirclesPage from './pages/CirclesPage.jsx'
import HistoryPage from './pages/HistoryPage.jsx'
import LecturerPage from './pages/LecturerPage.jsx'

function parseHash() {
  const [page = '', id] = window.location.hash.replace(/^#\/?/, '').split('/')
  return { page, id }
}

const STUDENT_NAV = [
  ['diagnose', 'Diagnose'], ['passport', 'Passport'], ['circles', 'Study circles'], ['history', 'History'],
]

export default function App() {
  const [user, setUser] = useState(null)
  const [booting, setBooting] = useState(true)
  const [health, setHealth] = useState(null)
  const [catalog, setCatalog] = useState(null)
  const [route, setRoute] = useState(parseHash())

  useEffect(() => {
    const onHash = () => setRoute(parseHash())
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  useEffect(() => {
    setUnauthorizedHandler(() => { setToken(''); setUser(null) })
    api('/health').then(setHealth).catch(() => setHealth(null))
    api('/catalog').then(setCatalog).catch(() => setCatalog(null))
    if (getToken()) {
      api('/me').then(setUser).catch(() => setToken('')).finally(() => setBooting(false))
    } else {
      setBooting(false)
    }
  }, [])

  const onAuthed = (token, u) => {
    setToken(token)
    setUser(u)
    go(u.role === 'lecturer' ? 'lecturer' : 'diagnose')
  }

  const signOut = () => {
    api('/auth/logout', { method: 'POST' }).catch(() => {})
    setToken('')
    setUser(null)
    go('')
  }

  if (booting) return <div className="boot"><Spinner label="Starting Punca" /></div>
  if (!user) return <AuthPage onAuthed={onAuthed} health={health} />

  const isLecturer = user.role === 'lecturer'
  let page = route.page || (isLecturer ? 'lecturer' : 'diagnose')
  if (isLecturer) page = 'lecturer'

  let body
  if (!catalog) body = <div className="card"><p>Loading the concept catalog. If this stays here, check that the backend is running.</p></div>
  else if (isLecturer) body = <LecturerPage catalog={catalog} />
  else if (page === 'diagnosis') body = <ResultPage id={route.id} catalog={catalog} user={user} onUser={setUser} />
  else if (page === 'passport') body = <PassportPage catalog={catalog} user={user} onUser={setUser} />
  else if (page === 'circles') body = <CirclesPage user={user} onUser={setUser} />
  else if (page === 'history') body = <HistoryPage />
  else body = <DiagnosePage />

  const llm = health && health.llm
  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="#/">
          <svg viewBox="0 0 64 64" aria-hidden="true"><path d="M32 8c-8 10-16 18-16 28a16 16 0 0 0 32 0c0-10-8-18-16-28z" /><circle cx="32" cy="38" r="5" /></svg>
          <span>Punca</span>
        </a>
        <nav>
          {isLecturer
            ? <a className="active" href="#/lecturer">Lecturer dashboard</a>
            : STUDENT_NAV.map(([p, label]) => (
              <a key={p} href={`#/${p}`} className={page === p || (p === 'diagnose' && page === 'diagnosis') ? 'active' : ''}>{label}</a>
            ))}
        </nav>
        <div className="topbar-right">
          {llm && (
            <span className={`llm-badge ${llm.mode === 'offline' ? 'off' : 'on'}`} title={llm.reason || llm.model}>
              {llm.mode === 'offline' ? 'Offline mode' : `Gemini · ${llm.model}`}
            </span>
          )}
          <span className="who">{user.name}<small>{isLecturer ? 'Lecturer' : 'Student'}</small></span>
          <button className="btn ghost small" onClick={signOut}>Sign out</button>
        </div>
      </header>
      <main className="page">{body}</main>
      <footer className="foot">Punca prototype · APU Cloud Innovation Hackathon 2026 · cohort data in this demo is synthetic</footer>
    </div>
  )
}
