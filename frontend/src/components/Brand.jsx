import React from 'react'

export default function Brand({ href = '#/', large = false, title = 'Punca home' }) {
  return <a className={`punca-brand${large ? ' large' : ''}`} href={href} title={title} aria-label={title}>
    <span className="punca-brand-mark" aria-hidden="true">p<span>↗</span></span>
    <span>punca<span className="punca-brand-dot">.</span></span>
  </a>
}
