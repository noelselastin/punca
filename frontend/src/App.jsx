import React, { useEffect, useState } from 'react'
import { api, getToken, setToken, setUnauthorizedHandler } from './api.js'
import { go, Spinner } from './components/common.jsx'
import AuthPage from './pages/AuthPage.jsx'
import DiagnosePage from './pages/DiagnosePage.jsx'
import ResultPage from './pages/ResultPage.jsx'
import PassportPage from './pages/PassportPage.jsx'
import CirclesPage from './pages/CirclesPage.jsx'
import HistoryPage from './pages/HistoryPage.jsx'
import LandingPage from './pages/LandingPage.jsx'
import PassportSetupPage from './pages/PassportSetupPage.jsx'
import ProfilePage from './pages/ProfilePage.jsx'
import GoogleWorkspacePage from './pages/GoogleWorkspacePage.jsx'
import Brand from './components/Brand.jsx'

function parseHash() {
  const [page = '', id] = window.location.hash.replace(/^#\/?/, '').split('/')
  return { page, id }
}

const STUDENT_NAV = [
  ['passport', 'Passport'],
  ['diagnose', 'Diagnose'],
  ['circles', 'Study circles'],
  ['workspace', 'Google Workspace'],
  ['history', 'History'],
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

  const onAuthed = (token, u, isNew) => {
    setToken(token)
    setUser(u)
    if (isNew || !(u.passportStyle && u.passportStyle.setupDone)) go('setup')
    else go('passport')
  }

  const signOut = () => {
    api('/auth/logout', { method: 'POST' }).catch(() => {})
    setToken('')
    setUser(null)
    go('')
  }

  if (booting) return <div className="boot"><Spinner label="Starting Punca" /></div>
  if (!user) {
    if (route.page === 'signin') return <AuthPage key="signin" mode="signin" onAuthed={onAuthed} health={health} />
    if (route.page === 'join') return <AuthPage key="join" mode="signup" onAuthed={onAuthed} health={health} />
    return <LandingPage onStart={() => go('join')} onSignIn={() => go('signin')} />
  }

  if (route.page === 'home') {
    return <LandingPage user={user} onStart={() => go('passport')} onSignIn={() => {}} />
  }
  const page = route.page || 'passport'

  let body
  if (!catalog) body = <div className="card"><p>Loading the concept catalog. If this stays here, check that the backend is running.</p></div>
  else if (page === 'setup') body = <PassportSetupPage user={user} catalog={catalog} onUser={setUser} />
  else if (page === 'diagnosis') body = <ResultPage id={route.id} catalog={catalog} user={user} onUser={setUser} />
  else if (page === 'passport') body = <PassportPage key={route.id || 'pp'} catalog={catalog} user={user} onUser={setUser} welcome={route.id === 'welcome'} />
  else if (page === 'workspace') body = <GoogleWorkspacePage user={user} onUser={setUser} />
  else if (page === 'circles') body = <CirclesPage user={user} onUser={setUser} />
  else if (page === 'history') body = <HistoryPage />
  else if (page === 'profile') body = <ProfilePage user={user} onUser={setUser} />
  else body = <DiagnosePage />

  const llm = health && health.llm
  return (
    <div className="shell">
      <header className="topbar">
        <Brand href="#/home" title="About Punca" />
        <nav>
          {STUDENT_NAV.map(([p, label]) => (
            <a key={p} href={`#/${p}`} className={page === p || (p === 'diagnose' && page === 'diagnosis') || (p === 'passport' && page === 'setup') ? 'active' : ''}>{label}</a>
          ))}
        </nav>
        <div className="topbar-right">
          {llm && (
            <span className={`llm-badge ${llm.mode === 'offline' ? 'off' : 'on'}`} title={llm.reason || llm.model}>
              {llm.mode === 'offline' ? 'Offline mode' : `Gemini · ${llm.model}`}
            </span>
          )}
          <a className={`who ${page === 'profile' ? 'active' : ''}`} href="#/profile" title="Edit your profile">{user.name}<small>Edit profile</small></a>
          <button className="btn ghost small" onClick={signOut}>Sign out</button>
        </div>
      </header>
      <main className="page">{body}</main>
      <footer className="foot">Punca • APU Cloud Innovation Hackathon 2026</footer>
    </div>
  )
}
