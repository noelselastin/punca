import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import AvailabilityGrid from '../components/AvailabilityGrid.jsx'
import { CircleCard } from '../components/CirclePanel.jsx'
import { ErrorNote, Spinner, Toggle, go, useAsync } from '../components/common.jsx'
import { ensureGoogle, prepareGoogle } from '../googleAuth.js'

/** One suggested study partner: what you have in common, how to reach them, and a circle to join. */
function PeerCard({ peer, busy, onJoin }) {
  const common = peer.commonGaps.length > 0
  const first = peer.name.split(' ')[0]
  return (
    <li className="peer-card">
      <div className="peer-head">
        <div>
          <b>{peer.name}</b>
          <div className="fine">
            {[peer.programme, peer.year ? `Year ${peer.year}` : null, peer.university].filter(Boolean).join(' · ')}
          </div>
        </div>
        {peer.email ? (
          <a className="peer-email" href={`mailto:${peer.email}`}>{peer.email}</a>
        ) : (
          <span className="fine">Email not shared</span>
        )}
      </div>
      <dl className="peer-facts">
        {common ? (
          <div>
            <dt>Same gap as you</dt>
            <dd>{peer.commonGaps.map((g) => <span key={g.id} className="chip state-entry-required">{g.name}</span>)}</dd>
          </div>
        ) : peer.gaps.length > 0 ? (
          <div>
            <dt>Working on</dt>
            <dd>{peer.gaps.map((g) => <span key={g.id} className="chip untested">{g.name}</span>)}</dd>
          </div>
        ) : null}
        {peer.commonModules.length > 0 ? (
          <div><dt>Same modules</dt><dd>{peer.commonModules.join(', ')}</dd></div>
        ) : peer.modules.length > 0 ? (
          <div><dt>Modules</dt><dd>{peer.modules.join(', ')}</dd></div>
        ) : null}
        {peer.sharedHours.length > 0 && (
          <div><dt>Free when you are</dt><dd>{peer.sharedHours.join(', ')}</dd></div>
        )}
      </dl>
      <div className="actions left" style={{ marginTop: '0.5rem' }}>
        {peer.inCircleWithYou ? (
          <span className="chip solid">In a circle with you</span>
        ) : common ? (
          <button type="button" className="btn small primary" disabled={busy} onClick={() => onJoin(peer.commonGaps[0])}>
            Study {peer.commonGaps[0].name} together
          </button>
        ) : null}
        {peer.email && (
          <a className="btn ghost small" href={`mailto:${peer.email}?subject=${encodeURIComponent('Study together on Punca')}`}>
            Email {first}
          </a>
        )}
      </div>
    </li>
  )
}

export default function CirclesPage({ user, onUser }) {
  const [circles, reloadCircles] = useAsync(() => api('/circles'), [])
  const [peers, reloadPeers] = useAsync(() => api('/circles/peers'), [])
  useEffect(() => {
    prepareGoogle()
  }, [])
  const [avail, setAvail] = useState(user.availability || [])
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const reload = () => Promise.all([reloadCircles(), reloadPeers()])

  const patch = async (body) => {
    setError(null)
    setSaved(false)
    try {
      onUser(await api('/me', { method: 'PATCH', body }))
      setSaved(true)
      reloadPeers()
    } catch (e) {
      setError(e)
    }
  }

  const act = async (fn) => {
    setBusy(true)
    setError(null)
    try {
      await fn()
      await reload()
    } catch (e) {
      setError(e)
    } finally {
      setBusy(false)
    }
  }

  const done = (id) => act(() => api(`/circles/${id}/done`, { method: 'POST' }))
  const sendChat = (circleId, text) => act(() => api(`/circles/${circleId}/chat`, { method: 'POST', body: { text } }))
  const joinConcept = (gap) => act(() => api('/circles/join', { method: 'POST', body: { conceptId: gap.id } }))
  const joinCircle = (id) => act(() => api(`/circles/${id}/join`, { method: 'POST' }))

  const addCalendar = async (circleId) => {
    try {
      await ensureGoogle()
      const res = await api(`/circles/${circleId}/calendar`, { method: 'POST' })
      return res.event
    } catch (e) {
      setError(e)
      return null
    }
  }

  const mine = (circles.data || []).filter((c) => c.status !== 'done')
  const finished = (circles.data || []).filter((c) => c.status === 'done')
  const p = peers.data

  return (
    <div className="grid2 wide-left top">
      <div className="circles-main">
        <div className="card">
          <div className="eyebrow">Study with peers · circle chat, Google Meet and Calendar</div>
          <h1 className="h2">My peer study circles</h1>
          {circles.loading && !circles.data && <Spinner />}
          <ErrorNote error={circles.error} />
          {circles.data && mine.length === 0 && (
            <p className="muted">
              You are not in a circle yet. Pick a study partner or an open circle below, or{' '}
              <a href="#/diagnose">run a diagnosis</a> to be matched on your own gap.
            </p>
          )}
          {mine.map((c) => (
            <CircleCard key={c.id} circle={c} onSendChat={sendChat} onAddCalendar={addCalendar} onCircleUpdated={reload}>
              <div className="actions left">
                <button className="btn small" disabled={busy} onClick={() => done(c.id)}>
                  We met: mark done
                </button>
                <button className="btn ghost small" onClick={() => go('passport')}>
                  Re-check to earn the stamp
                </button>
              </div>
            </CircleCard>
          ))}
          {finished.length > 0 && (
            <p className="fine">Finished circles: {finished.map((c) => c.conceptName).join(', ')}.</p>
          )}
        </div>

        <div className="card">
          <div className="eyebrow">Suggested for you</div>
          <h2 className="h2">Study partners</h2>
          {peers.loading && !p && <Spinner label="Finding students to study with" />}
          <ErrorNote error={peers.error} />
          {p && (
            <>
              <p className="muted">
                {p.me.gaps.length > 0
                  ? <>Ranked by what you share. Your open gaps: <b>{p.me.gaps.map((g) => g.name).join(', ')}</b>.</>
                  : 'Students on Punca who are open to studying together. Run a diagnosis and the ones who share your gap move to the top.'}
              </p>
              {p.peers.length === 0 ? (
                <p className="muted">No other students have opted in yet. Check back soon.</p>
              ) : (
                <ul className="peer-list">
                  {p.peers.map((peer) => <PeerCard key={peer.uid} peer={peer} busy={busy} onJoin={joinConcept} />)}
                </ul>
              )}
            </>
          )}
        </div>

        {p && p.openCircles.length > 0 && (
          <div className="card">
            <div className="eyebrow">Open circles</div>
            <h2 className="h2">Circles you can join</h2>
            <p className="muted">These circles still have room. You do not need a matching free hour to join.</p>
            {p.openCircles.map((c) => (
              <CircleCard key={c.id} circle={c}>
                <div className="actions left">
                  {c.reason === 'common-gap' && <span className="chip state-entry-required">Your gap</span>}
                  {c.reason === 'common-module' && <span className="chip untested">Your module</span>}
                  <button className="btn small primary" disabled={busy} onClick={() => joinCircle(c.id)}>
                    Join this circle
                  </button>
                </div>
              </CircleCard>
            ))}
          </div>
        )}
        <ErrorNote error={error} />
      </div>

      <div className="card">
        <h2 className="h2">My weekly free hours</h2>
        <p className="muted">
          Optional. Punca points out study partners who are free at the same time as you. A match is a bonus, not a requirement.
        </p>
        <AvailabilityGrid
          value={avail}
          onChange={(v) => {
            setAvail(v)
            setSaved(false)
          }}
        />
        <div className="actions left">
          <button className="btn primary" onClick={() => patch({ availability: avail })}>
            Save free hours
          </button>
          {saved && <span className="fine">Saved.</span>}
        </div>
        <h3 className="h3">Peer privacy</h3>
        <div className="consents">
          <Toggle
            checked={user.consent.joinCircles}
            label="Suggest me as a study partner"
            hint="Opt-in. Off means other students never see you."
            onChange={(v) => patch({ consent: { joinCircles: v } })}
          />
          <Toggle
            checked={user.consent.shareNameWithCircle}
            label="Show my name"
            hint="Otherwise you appear as 'Anonymous peer'."
            onChange={(v) => patch({ consent: { shareNameWithCircle: v } })}
          />
          <Toggle
            checked={user.consent.shareContact}
            label="Share my contact email"
            hint="Lets study partners email you."
            onChange={(v) => patch({ consent: { shareContact: v } })}
          />
        </div>
      </div>
    </div>
  )
}
