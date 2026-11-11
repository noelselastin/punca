// Google sign-in in the browser (Google Identity Services token flow), for Calendar and Docs.
// The server supplies the OAuth client ID; without one, live Google features stay off.
import { api } from './api.js'

let gsiPromise = null

function loadGsiScript() {
  if (typeof window !== 'undefined' && window.google?.accounts?.oauth2) {
    return Promise.resolve(window.google.accounts.oauth2)
  }
  if (gsiPromise) return gsiPromise
  gsiPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = () => {
      if (window.google?.accounts?.oauth2) resolve(window.google.accounts.oauth2)
      else reject(new Error('Google sign-in did not load. Refresh the page and try again.'))
    }
    script.onerror = () => {
      gsiPromise = null
      reject(new Error('Could not load Google sign-in. Check your internet connection.'))
    }
    document.head.appendChild(script)
  })
  return gsiPromise
}

export async function requestGoogleAccessToken({ clientId, scopes = [], loginHint = '' }) {
  if (!clientId) {
    throw new Error('Google sign-in is not set up on this Punca server yet.')
  }
  const oauth2 = await loadGsiScript()
  return new Promise((resolve, reject) => {
    const tokenClient = oauth2.initTokenClient({
      client_id: clientId,
      scope: scopes.join(' '),
      hint: loginHint || undefined,
      callback: (resp) => {
        if (resp?.error) {
          reject(new Error(resp.error_description || resp.error || 'Google sign-in was cancelled.'))
          return
        }
        if (!resp?.access_token) {
          reject(new Error('Google did not return an access token.'))
          return
        }
        resolve({
          accessToken: resp.access_token,
          expiresIn: Number(resp.expires_in) || 3600,
        })
      },
      error_callback: (err) => {
        reject(new Error(err?.message || 'The Google sign-in window was closed or blocked.'))
      },
    })
    // '' asks for consent only the first time; later connections are one click.
    tokenClient.requestAccessToken({ prompt: '' })
  })
}

/**
 * Connect the student's Google account (the personal Gmail from sign-up is pre-selected) and
 * return Punca's updated workspace status. `ws` is the object from GET /api/google/status.
 */
export async function connectGoogle(ws) {
  const token = await requestGoogleAccessToken({
    clientId: ws?.oauthClientId,
    scopes: ws?.oauthScopes || [],
    loginHint: ws?.accountEmail || ws?.email || '',
  })
  return api('/google/connect', { method: 'POST', body: token })
}

export const GOOGLE_NOT_SET_UP =
  'Google sign-in is not set up on this Punca server yet, so Punca cannot reach your Google account directly.'

// Google's window must open straight after a click, or the browser blocks it as a pop-up.
// Pages call prepareGoogle() when they load, so the sign-in script is ready before any click.
export function prepareGoogle() {
  return api('/google/status')
    .then((ws) => {
      if (ws && ws.liveAvailable && !ws.liveConnected) loadGsiScript().catch(() => {})
      return ws
    })
    .catch(() => null)
}

/**
 * Call before saving to Google Docs or Google Calendar. If Google sign-in is set up and the student
 * is not connected yet, Google's window opens with their sign-up Gmail already chosen.
 * Returns { state: 'connected' | 'unavailable' | 'cancelled', error? }.
 */
export async function ensureGoogle() {
  let ws
  try {
    ws = await api('/google/status')
  } catch (error) {
    return { state: 'unavailable', error }
  }
  if (!ws.liveAvailable) return { state: 'unavailable' }
  if (ws.liveConnected) return { state: 'connected' }
  try {
    await connectGoogle(ws)
    return { state: 'connected' }
  } catch (error) {
    return { state: 'cancelled', error }
  }
}

/** One line saying where a note ('doc') or session ('event') actually went. */
export function savedWhere(kind, item, google, warning) {
  const name = `"${item.title}"`
  if (item.live) {
    return kind === 'doc' ? `Saved ${name} to your Google Docs.` : `Added ${name} to your Google Calendar.`
  }
  const here =
    kind === 'doc'
      ? `Saved ${name} in your Punca notes (Google Workspace, Google Docs tab)`
      : `Saved ${name} in Punca`
  const next = kind === 'doc' ? '' : ' Use "Add to Google Calendar" on it to put it in your calendar.'
  if (warning) return `${here}. Google did not accept it: ${warning}${next}`
  if (google && google.state === 'cancelled') return `${here}, because Google sign-in did not finish.${next}`
  if (google && google.state === 'unavailable') return `${here}. Google sign-in isn't available on this site yet.${next}`
  return `${here}.${next}`
}
