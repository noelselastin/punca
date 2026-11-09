import { reportError } from './logging.js'

const TOKEN_KEY = 'punca.token'
let onUnauthorized = () => {}

export function getToken() {
  try { return localStorage.getItem(TOKEN_KEY) || '' } catch { return '' }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch { /* storage blocked: the session lasts until reload */ }
}

export function setUnauthorizedHandler(fn) { onUnauthorized = fn }

export async function api(path, { method = 'GET', body } = {}) {
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  let res
  try {
    res = await fetch(`/api${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) })
  } catch {
    throw new Error('Cannot reach the Punca server. Is the backend running on port 8000?')
  }
  let data = null
  try { data = await res.json() } catch { /* empty body */ }
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith('/auth/')) onUnauthorized()
    let msg = data && data.error
    if (!msg && data && data.detail) msg = typeof data.detail === 'string' ? data.detail : 'Please check the form fields.'
    msg = msg || `Request failed (${res.status})`
    if (res.status >= 500) reportError(`API ${method} ${path} -> ${res.status}: ${msg}`, null, 'warn')
    const err = new Error(msg)
    err.status = res.status
    throw err
  }
  return data
}
