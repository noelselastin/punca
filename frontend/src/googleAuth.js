// Browser helper for Google Identity Services OAuth token flow.
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
      else reject(new Error('Google Identity Services failed to initialize.'))
    }
    script.onerror = () => {
      gsiPromise = null
      reject(new Error('Could not load Google Sign-In script. Check your internet connection.'))
    }
    document.head.appendChild(script)
  })
  return gsiPromise
}

export async function requestGoogleAccessToken({ clientId, scopes = [], loginHint = '' }) {
  if (!clientId) {
    throw new Error('GOOGLE_OAUTH_CLIENT_ID is not configured on the server.')
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
        reject(new Error(err?.message || 'Google sign-in popup was closed or blocked.'))
      },
    })
    tokenClient.requestAccessToken({ prompt: 'consent' })
  })
}
