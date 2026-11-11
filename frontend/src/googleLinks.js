// Plain links into the student's own Google apps. Punca keeps its own copy of study sessions and
// notes and opens Google in a new tab when the student wants them there; it never signs in to Google.

export const GOOGLE_TASKS_URL = 'https://tasks.google.com/'
export const NEW_GOOGLE_DOC_URL = 'https://docs.google.com/document/create'
export const NEW_MEET_URL = 'https://meet.google.com/new'

/** Open a link in a new tab. Returns false when the browser blocked the tab. */
export function openInNewTab(url) {
  if (!url) return false
  const tab = window.open(url, '_blank')
  if (tab) tab.opener = null
  return Boolean(tab)
}

/** Copy text to the clipboard. Returns false when the browser does not allow it. */
export async function copyText(text) {
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    // Fall back to the older copy command below.
  }
  try {
    const box = document.createElement('textarea')
    box.value = text
    box.setAttribute('readonly', '')
    box.style.position = 'fixed'
    box.style.opacity = '0'
    document.body.appendChild(box)
    box.select()
    const ok = document.execCommand('copy')
    box.remove()
    return ok
  } catch {
    return false
  }
}

/**
 * Copy a note and open a new Google Doc to paste it into. Call it from a click handler, so the
 * browser allows the new tab. Returns { copied, opened }.
 */
export async function copyToNewGoogleDoc(title, content) {
  const copied = await copyText(`${title}\n\n${content || ''}`)
  return { copied, opened: openInNewTab(NEW_GOOGLE_DOC_URL) }
}

/** One line saying what happened after copyToNewGoogleDoc. */
export function googleDocNote(title, { copied, opened }) {
  const name = `"${title}"`
  if (copied && opened) return `Copied ${name}. Paste it into the new Google Doc (Ctrl+V, or ⌘V on a Mac).`
  if (copied) return `Copied ${name}. Open a new Google Doc and paste it in.`
  const doc = opened ? 'the new Google Doc' : 'a new Google Doc'
  return `Your browser did not let Punca copy ${name}. Copy it from Google Workspace → Google Docs in Punca and paste it into ${doc}.`
}
