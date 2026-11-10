import React, { useEffect, useRef, useState } from 'react'
import Brand from '../components/Brand.jsx'
import './landing.css'

const SOURCES = {
  stem: 'https://pmc.ncbi.nlm.nih.gov/articles/PMC9802213/',
  classes: 'https://www.teaching.unsw.edu.au/assessing-large-classes',
  learning: 'https://www.nationalacademies.org/read/28268/chapter/5',
  ai: 'https://easychair.org/publications/preprint/4C1J',
}

function Arrow({ diagonal = false }) {
  return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d={diagonal ? 'M6 18 18 6M6 6h12v12' : 'M4 12h16m-6-6 6 6-6 6'} stroke="currentColor" strokeWidth="1.6" /></svg>
}

function Emblem() {
  return <svg viewBox="0 0 64 64" fill="none" aria-hidden="true"><circle cx="32" cy="32" r="26" /><ellipse cx="32" cy="32" rx="12" ry="26" /><path d="M6 32h52M11 17h42M11 47h42M32 6v52" /><path d="m18 40 28-21-10 28-5-13Z" className="pn-emblem-plane" /></svg>
}

function jumpTo(id) {
  const section = document.getElementById(id)
  if (!section) return
  section.focus({ preventScroll: true })
  section.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' })
}

function PassportStill() {
  return <div className="pn-still" role="img" aria-label="Illustrative Punca passport and boarding pass: from a missing concept to a clearer next step">
    <div className="pn-orbit pn-orbit-one" /><div className="pn-orbit pn-orbit-two" />
    <div className="pn-cover">
      <div className="pn-cover-top"><span>THE LEARNING PASSPORT</span><span>MY / 01</span></div>
      <Emblem />
      <div className="pn-cover-name">PUNCA</div>
      <div className="pn-cover-sub">A little progress.<br />A world of possibility.</div>
      <div className="pn-cover-bottom"><span>STUDENT EDITION</span><span>✦</span></div>
    </div>
    <div className="pn-boarding">
      <div className="pn-boarding-head"><span>PUNCA AIR / LEARNING JOURNEY</span><span>↗</span></div>
      <div className="pn-boarding-route"><div><small>FROM</small><b>STUCK</b></div><span>⟶</span><div><small>TO</small><b>I GET IT.</b></div></div>
      <div className="pn-boarding-bottom"><div><small>NEXT CHECKPOINT</small><strong>Find the missing piece</strong></div><div className="pn-barcode" /></div>
    </div>
    <span className="pn-still-note">Your journey. Your pace.</span>
  </div>
}

const FLIGHT = [
  { short: 'Check the basics', title: 'Start with what you already know.', text: 'Describe the topic or upload a lab file. Five to ten confidence-weighted questions trace the earlier concepts it depends on.', path: 'M80 220 Q100 150 220 185' },
  { short: 'Find the gap', title: 'One missing connection comes into view.', text: 'In this example, the chain rule needs attention before gradient descent. An unstamped checkpoint shows where to focus.', path: 'M220 185 C320 95 400 105 480 200' },
  { short: 'Meet your people', title: 'Take a detour. Learn together.', text: 'Work through an explanation and practice, or join a peer study circle around the same gap with Google Meet, Chat and Calendar.', path: 'M480 200 C520 245 510 335 655 335' },
  { short: 'Return & re-check', title: 'Come back and show what clicked.', text: 'Return to the missed concept for a re-check. A stamp is earned when the check brings your understanding to Solid; joining a group alone does not earn one.', path: 'M655 335 C770 420 330 420 380 280 Q400 230 480 200' },
  { short: 'Keep moving', title: 'A new stamp. A clearer way forward.', text: 'The earlier gap is cleared. Move on to the next concept and keep building your passport across all six modules.', path: 'M480 200 C590 95 755 100 870 185' },
]

function Checkpoint({ x, y, name, number, cleared, active, destination }) {
  return <g transform={`translate(${x} ${y})`} className={`pn-checkpoint ${cleared ? 'is-cleared' : active ? 'is-gap' : ''}`}>
    <circle r="55" className="pn-stamp-outer" />
    <circle r="47" className="pn-stamp-inner" />
    <text y="-20" className="pn-svg-micro">{cleared ? 'VERIFIED' : active ? 'ENTRY REQUIRED' : destination ? 'DESTINATION' : 'CHECKPOINT'}</text>
    <text y="9" className="pn-svg-symbol">{cleared ? '✓' : number}</text>
    <text y="31" className="pn-svg-micro">PUNCA PASSPORT</text>
    <text y="83" className="pn-svg-label">{name}</text>
  </g>
}

function FlightJourney() {
  const [stage, setStage] = useState(0)
  const [playing, setPlaying] = useState(true)
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches)
  const [visible, setVisible] = useState(false)
  const [arrived, setArrived] = useState(false)
  const [selection, setSelection] = useState(0)
  const host = useRef(null)
  const artwork = useRef(null)
  const plane = useRef(null)
  const paths = useRef([])
  const elapsed = useRef(0)
  const manual = useRef(false)
  const duration = 3300

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const change = () => { setReduced(query.matches); if (query.matches) setPlaying(false) }
    query.addEventListener('change', change)
    const observer = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.12 })
    observer.observe(host.current)
    return () => { query.removeEventListener('change', change); observer.disconnect() }
  }, [])

  useEffect(() => {
    const path = paths.current[stage]
    const total = path.getTotalLength()
    const draw = (progress) => {
      const distance = total * Math.min(1, progress)
      const point = path.getPointAtLength(distance)
      const before = path.getPointAtLength(Math.max(0, distance - 1))
      const after = path.getPointAtLength(Math.min(total, distance + 1))
      const angle = Math.atan2(after.y - before.y, after.x - before.x) * 180 / Math.PI
      plane.current.setAttribute('transform', `translate(${point.x} ${point.y}) rotate(${angle})`)
      if (artwork.current.scrollWidth > artwork.current.clientWidth) {
        artwork.current.scrollLeft = point.x * artwork.current.scrollWidth / 1080 - artwork.current.clientWidth / 2
      }
    }
    if (reduced || manual.current) { draw(1); setArrived(true) }
    else draw(elapsed.current / duration)
    if (!playing || !visible || reduced) return
    let frame
    let last
    const tick = (time) => {
      if (last !== undefined && !document.hidden) elapsed.current += Math.min(time - last, 60)
      last = time
      draw(elapsed.current / duration)
      if (elapsed.current >= duration) setArrived(true)
      if (elapsed.current >= duration + 1500) {
        if (stage === FLIGHT.length - 1) { setPlaying(false); return }
        elapsed.current = 0
        setArrived(false)
        setStage(stage + 1)
        return
      }
      frame = requestAnimationFrame(tick)
    }
    frame = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(frame)
  }, [stage, playing, visible, reduced, selection])

  const choose = (index) => {
    manual.current = true
    elapsed.current = duration
    setPlaying(false)
    setArrived(true)
    setStage(index)
    setSelection(value => value + 1)
  }
  const replay = () => {
    if (reduced) { choose(0); return }
    manual.current = false
    elapsed.current = 0
    setArrived(false)
    setStage(0)
    setPlaying(true)
    setSelection(value => value + 1)
  }
  const cleared = stage > 3 || (stage === 3 && arrived)

  return <div className="pn-flight" ref={host}>
    <div className="pn-flight-top"><span><i /> AN EXAMPLE LEARNING JOURNEY</span><div>
      {!reduced && <button onClick={() => { if (!playing && stage === 4 && arrived) { replay(); return }; manual.current = false; setPlaying(!playing) }}>{playing ? 'Pause animation' : stage === 4 && arrived ? 'Play again' : 'Play animation'}</button>}
      <button onClick={replay}>{reduced ? 'First checkpoint' : 'Replay'} <span aria-hidden="true">↺</span></button>
    </div></div>
    <div className="pn-flight-art" ref={artwork}>
      <svg viewBox="0 0 1080 440" role="img" aria-labelledby="pn-flight-title pn-flight-desc">
        <title id="pn-flight-title">A flight through your learning passport</title>
        <desc id="pn-flight-desc">An example route from derivatives to a chain-rule gap, a study circle, a return for a re-check, and onward to backpropagation. Choose any of the five steps below to explore.</desc>
        <defs>
          <pattern id="pn-paper-grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0V24" fill="none" stroke="#18354b" strokeOpacity=".045" /></pattern>
          <linearGradient id="pn-fold"><stop stopColor="#18354b" stopOpacity="0" /><stop offset=".5" stopColor="#18354b" stopOpacity=".12" /><stop offset="1" stopColor="#18354b" stopOpacity="0" /></linearGradient>
        </defs>
        <path d="M18 26Q275 9 540 31Q805 9 1062 26V410Q805 393 540 415Q275 393 18 410Z" fill="#f6f1e5" />
        <path d="M18 26Q275 9 540 31Q805 9 1062 26V410Q805 393 540 415Q275 393 18 410Z" fill="url(#pn-paper-grid)" />
        <path d="M34 43Q280 27 524 46M556 46Q800 27 1046 43" fill="none" stroke="#c7c2b7" />
        <rect x="520" y="31" width="40" height="376" fill="url(#pn-fold)" />
        <text x="55" y="74" className="pn-svg-heading">PUNCA / FOUNDATIONS</text><text x="1025" y="74" textAnchor="end" className="pn-svg-heading">VISAS &amp; CHECKPOINTS</text>
        <text x="55" y="385" className="pn-svg-micro">01 / UNDERSTANDING STARTS HERE</text><text x="1025" y="385" textAnchor="end" className="pn-svg-micro">02 / KEEP EXPLORING</text>
        {FLIGHT.map((item, index) => <path key={item.short} d={item.path} ref={el => { paths.current[index] = el }} className={`pn-flight-path ${index === stage ? 'is-current' : ''} ${index < stage ? 'is-travelled' : ''}`} />)}
        <Checkpoint x={220} y={185} name="Derivatives" number="01" cleared={stage > 0 || arrived} />
        <Checkpoint x={480} y={200} name="Chain rule" number="02" cleared={cleared} active={stage >= 1 && !cleared} />
        <Checkpoint x={870} y={185} name="Backpropagation" number="03" cleared={stage === 4 && arrived} destination />
        <g transform="translate(655 335)" className={`pn-peer-stop ${stage === 2 ? 'is-active' : ''}`}>
          <rect x="-85" y="-38" width="170" height="76" rx="8" />
          <g fill="none" stroke="currentColor" strokeWidth="1.6"><circle cx="-17" cy="-13" r="5" /><circle cx="0" cy="-17" r="6" /><circle cx="17" cy="-13" r="5" /><path d="M-25 2q0-13 12-9M-10 2q0-16 20 0M13-7q12-4 12 9" /></g>
          <text y="23" className="pn-svg-micro">STUDY CIRCLE</text>
        </g>
        <g ref={plane} className="pn-airplane"><circle r="25" fill="#e5b65a" fillOpacity=".2" /><path d="M23 0 6-5-5-22-11-22-5-5-18-4-24-11-28-11-23 0-28 11-24 11-18 4-5 5-11 22-5 22 6 5Z" fill="#17374c" stroke="#f6f1e5" strokeWidth="1.8" /></g>
      </svg>
    </div>
    <div className="pn-flight-caption" aria-live={playing ? 'off' : 'polite'}><span className="pn-stage-number">0{stage + 1}<small>/ 05</small></span><div><h3>{FLIGHT[stage].title}</h3><p>{FLIGHT[stage].text}</p></div></div>
    <div className="pn-flight-stages" aria-label="Explore the learning journey">
      {FLIGHT.map((item, i) => <button key={item.short} className={i === stage ? 'is-current' : ''} aria-pressed={i === stage} onClick={() => choose(i)}><span>0{i + 1}</span>{item.short}<Arrow /></button>)}
    </div>
  </div>
}

const FAQ = [
  ['How is this different from asking an AI chatbot?', <>Punca checks the earlier concepts behind your question or uploaded lab document across 5–10 confidence-weighted checks, then shows the exact hard-prerequisite chain that led to its suggested gap. You get a focused explanation with course-note sources, practice, and a re-check.</>],
  ['What can I study in the prototype?', <>The prototype covers 138 connected concepts across 6 modules and 28 topics: Maths Foundations, Computing Foundations, Computational Mathematics, Introduction to Python, Object Oriented Programming with Java, and Introduction to Databases.</>],
  ['How do I earn a passport stamp?', <>Work on a concept and pass re-checks until your understanding reaches Solid. A diagnosis or a study-circle visit alone does not earn a stamp. These are personal learning aids, not academic grades or qualifications.</>],
  ['Can I study with other students?', <>Yes. Share your free hours to find a peer study circle around a common gap, complete with Google Meet video rooms, Google Chat spaces, and Google Calendar scheduling.</>],
  ['Who can see my gaps and my passport?', <>Your passport is private to you. Sharing your name in a peer study circle is opt-in. This is a local hackathon prototype, so use demo details while exploring it.</>],
  ['Is it free, and what if Punca gets it wrong?', <>The prototype is free to try. Its diagnosis is an estimate. You can challenge a result with “I actually know this” and take a re-check, or save notes and tasks to Google Docs and Google Tasks.</>],
]

export default function LandingPage({ user, onStart, onSignIn }) {
  const startLabel = user ? 'Open my passport' : 'Create my passport'
  return <div className="pn-landing">
    <a className="pn-skip" href="#pn-main" onClick={e => { e.preventDefault(); jumpTo('pn-main') }}>Skip to content</a>
    <header className="pn-nav">
      <Brand />
      <nav aria-label="Page sections"><button onClick={() => jumpTo('pn-why')}>Why Punca</button><button onClick={() => jumpTo('pn-journey')}>The journey</button><button onClick={() => jumpTo('pn-faq')}>Questions</button></nav>
      <div className="pn-nav-actions">{!user && <button className="pn-text-button" onClick={onSignIn}>Sign in</button>}<button className="pn-button pn-button-small" onClick={onStart}>{startLabel}<Arrow diagonal /></button></div>
    </header>

    <main id="pn-main" tabIndex={-1}>
      <section className="pn-hero pn-container">
        <div className="pn-hero-copy"><p className="pn-eyebrow pn-hero-eyebrow"><span />Identify knowledge gaps. Strengthen your foundations.</p>
          <h1>Learn with<br /><em>confidence.</em></h1>
          <p className="pn-hero-lead">For the concepts that never quite clicked.<br />Learn, Without the blind spots<br />Identify knowledge gaps. Strengthen your foundations. Learn with confidence.</p>
          <div className="pn-hero-actions"><button className="pn-button" onClick={onStart}>{startLabel}<Arrow diagonal /></button><button className="pn-link-button" onClick={() => jumpTo('pn-journey')}>See the journey <span aria-hidden="true">↓</span></button></div>
          <p className="pn-hero-foot">5–10 foundation questions to pinpoint your starting point.<br /><span>Free prototype · Made for university students</span></p>
        </div>
        <PassportStill />
      </section>

      <div className="pn-route-strip" aria-label="Find the gap, build understanding, learn together, earn your stamp"><span>FIND THE GAP</span><i>↗</i><span>BUILD UNDERSTANDING</span><i>↗</i><span>LEARN TOGETHER</span><i>↗</i><span>EARN YOUR STAMP</span><i>✦</i></div>

      <section className="pn-evidence pn-container" id="pn-why" tabIndex={-1}>
        <div className="pn-section-intro"><div><p className="pn-eyebrow">01 / WHY THIS MATTERS</p><h2>Small gaps.<br /><em>Long shadows.</em></h2></div><p>A new topic can depend on something you never quite understood. Re-reading the new slides may leave that earlier gap untouched. Punca helps you find a place to start.</p></div>
        <div className="pn-evidence-grid">
          <article className="pn-research-main"><div className="pn-stat-line"><span>48%</span><span className="pn-stat-arrow">↘</span><span>33%</span></div><h3>Foundations can shape the whole degree.</h3><p>A study of nearly 110,000 records across six US public research universities linked lower introductory STEM grades to lower chances of completing a STEM degree.</p><p className="pn-study-context">The figures show one modelled comparison: STEM-intending white men with average preparation, with C-or-better grades in every introductory course versus below C in at least one. Association, not proof of cause.</p><a className="pn-source" href={SOURCES.stem} target="_blank" rel="noreferrer">Hatfield, Brown &amp; Topaz · PNAS Nexus, 2022 <Arrow diagonal /></a></article>
          <article className="pn-research-side"><div className="pn-stat-line pn-class-size">1,000–2,000</div><h3>Students in a single class.</h3><p>UNSW teaching guidance describes classes of this size as increasingly common, and identifies individual feedback as a challenge.</p><a className="pn-source" href={SOURCES.classes} target="_blank" rel="noreferrer">UNSW · Assessing Large Classes <Arrow diagonal /></a><div className="pn-research-note">Published research and teaching guidance.<br />These are not APU statistics or measured Punca outcomes.</div></article>
        </div>
      </section>

      <section className="pn-journey-section" id="pn-journey" tabIndex={-1}><div className="pn-container">
        <div className="pn-section-intro"><div><p className="pn-eyebrow">02 / YOUR PUNCA PASSPORT</p><h2>A way forward.<br /><em>Detours included.</em></h2></div><p>Find the checkpoint you missed. Learn on your own or with people on the same route. Come back, re-check, and let your progress leave a mark.</p></div>
        <FlightJourney />
        <div className="pn-journey-note"><span>ILLUSTRATION, NOT A LIVE STUDENT RECORD</span><p>Your passport is yours to customise. Stamps record passed re-checks; they are not grades.</p></div>
      </div></section>

      <section className="pn-quote-section pn-container">
        <div><p className="pn-eyebrow">03 / THE IDEA BEHIND IT</p><h2>Built on<br /><em>what you know.</em></h2></div>
        <figure><div className="pn-quote-mark" aria-hidden="true">“</div><blockquote>New knowledge is generated when the brain actively connects information to <em>prior knowledge and experience.</em></blockquote><figcaption><span>National Academies of Sciences, Engineering, and Medicine<br /><small>Transforming Undergraduate STEM Education, 2025 · Chapter 3</small></span><a href={SOURCES.learning} target="_blank" rel="noreferrer" aria-label="Read the National Academies research"><Arrow diagonal /></a></figcaption></figure>
      </section>

      <section className="pn-faq-section pn-container" id="pn-faq" tabIndex={-1}>
        <div><p className="pn-eyebrow">04 / BEFORE YOU TAKE OFF</p><h2>Questions,<br /><em>answered.</em></h2><p className="pn-faq-intro">A few things to know<br />before your first checkpoint.</p></div>
        <div className="pn-faq-list">{FAQ.map(([question, answer], index) => <details key={question} open={index === 0 ? true : undefined}><summary>{question}<span className="pn-faq-toggle" aria-hidden="true" /></summary><div className="pn-faq-answer">{answer}</div></details>)}</div>
      </section>

      <section className="pn-final"><div className="pn-container"><div><p className="pn-eyebrow">YOUR NEXT CHAPTER</p><h2>Find your footing.<br /><em>Then take flight.</em></h2></div><div><p>Make a passport that feels like you.<br />Start with one concept. See where it takes you.</p><button className="pn-button pn-button-gold" onClick={onStart}>{startLabel}<Arrow diagonal /></button><small>Create an account → Customise → Explore</small></div></div></section>
    </main>
    <footer className="pn-footer pn-container"><div className="pn-footer-top"><a className="pn-brand" href="#/">punca.</a><p>Cari puncanya.<br /><span>Find the cause. Find your way.</span></p><span>APU CLOUD INNOVATION HACKATHON 2026<br />SMART CAMPUS &amp; STUDENT EXPERIENCE</span></div>
      <div className="pn-footer-bottom"><span>A learning companion. A work in progress.</span><button className="pn-text-button" onClick={() => jumpTo('pn-main')}>Back to top ↑</button></div>
    </footer>
  </div>
}
