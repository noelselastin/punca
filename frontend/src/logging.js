// Browser errors are sent to the backend and written to logs/punca.log.
export function reportError(message, stack, level = 'error') {
  try {
    fetch('/api/log/client', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        level,
        message: String(message).slice(0, 1000),
        stack: stack ? String(stack).slice(0, 3000) : null,
        url: window.location.href,
      }),
    }).catch(() => {})
  } catch { /* never let logging break the app */ }
}

export function installErrorLogging() {
  window.addEventListener('error', (e) => reportError(e.message, e.error && e.error.stack))
  window.addEventListener('unhandledrejection', (e) => {
    const r = e.reason
    reportError((r && r.message) || String(r), r && r.stack)
  })
}
