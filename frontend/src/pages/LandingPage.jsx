import React from 'react'

const scrollTo = (id) => {
  const el = document.getElementById(id)
  if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

// Published research only. Each figure links to its source in the list at the bottom of the page.
const STATS = [
  { big: '48%', text: 'of US students who started a STEM degree left STEM within 6 years. 28% changed course and 20% dropped out.', src: 1 },
  { big: '34% vs 22%', text: 'fail rate in lecture-only classes compared with classes that include hands-on practice (225 studies).', src: 2 },
  { big: '31% → 39%', text: 'of teenagers in OECD countries get very nervous doing maths problems, and the number is rising (2012 to 2022).', src: 3 },
  { big: '98%', text: 'of students in a normal class scored lower than the average student who had a personal tutor.', src: 4 },
]

const SOURCES = [
  { n: 1, text: 'NCES (2013). STEM Attrition: College Students’ Paths Into and Out of STEM Fields (NCES 2014-001).', url: 'https://nces.ed.gov/pubs2014/2014001rev.pdf' },
  { n: 2, text: 'Freeman, S. et al. (2014). Active learning increases student performance in science, engineering, and mathematics. PNAS 111(23).', url: 'https://www.pnas.org/doi/10.1073/pnas.1319030111' },
  { n: 3, text: 'OECD (2024). PISA 2022 Results, Volume V: Learning Strategies and Attitudes for Life, as reported by ACER Teacher magazine.', url: 'https://www.teachermagazine.com/au_en/articles/pisa-2022-insights-student-questions-mathematics-anxiety-and-homework' },
  { n: 4, text: 'Bloom, B. S. (1984). The 2 Sigma Problem. Educational Researcher 13(6), 4–16.', url: 'https://doi.org/10.3102/0013189X013006004' },
  { n: 5, text: 'The Star (16 Jul 2024). STEM enrolment hits 50.83% for 2024, says Education Ministry.', url: 'https://www.thestar.com.my/news/nation/2024/07/16/stem-enrolment-hits-5083-for-2024-up-from-4184-in-2019-says-education-ministry' },
  { n: 6, text: 'Ausubel, D. P. (1968). Educational Psychology: A Cognitive View. Holt, Rinehart and Winston.', url: null },
]

const PROBLEMS = [
  { who: 'Students', text: 'can’t see which earlier topic they’re missing. They only feel that “this is hard”, re-read the slides and lose confidence.' },
  { who: 'Lecturers', text: 'can’t check every student in a big class, so they usually find out at exam time.' },
  { who: 'AI chatbots', text: 'answer the question you typed, but don’t check whether something earlier is the real problem.' },
  { who: 'Campus support', text: 'exists (consultations, peer tutoring, study groups), but students don’t know which one they need, or when.' },
]

const STEPS = [
  { n: '1', title: 'Tell us what you’re stuck on', text: 'Type it in your own words, or paste the question. Punca works out which topic it is.' },
  { n: '2', title: 'Answer up to 5 quick questions', text: 'Get one wrong and Punca checks the earlier topic it’s built on.' },
  { n: '3', title: 'See what’s really missing', text: 'Punca names the earlier topic that’s causing the trouble, and shows the answers it based that on.' },
  { n: '4', title: 'Fix it', text: 'A short explanation taken from your course notes, with the source shown, plus 3 practice questions.' },
  { n: '5', title: 'Get help from people', text: 'Join a small study group of students stuck on the same thing, at a time you’re all free, with your lecturer.' },
  { n: '6', title: 'Prove it and earn a stamp', text: 'Pass a short re-check and the topic gets a stamp in your Punca Passport.' },
]

function HeroPassport() {
  return (
    <div className="lp-pp" aria-label="Example Punca Passport page">
      <div className="lp-pp-head">
        <span>PUNCA PASSPORT</span><span>Module: AI Methods</span>
      </div>
      <div className="lp-pp-body">
        <div className="lp-pp-region">Region: Calculus Foundations</div>
        <div className="lp-visas">
          <div className="lp-visa"><b>Derivatives</b><span className="stamp mini"><span className="stamp-top">Verified</span><span className="stamp-mid">PUNCA</span></span></div>
          <div className="lp-visa entry"><b>Chain rule</b><em>Entry required</em></div>
        </div>
        <div className="lp-pp-region">Region: Linear Algebra</div>
        <div className="lp-visas">
          <div className="lp-visa"><b>Dot product</b><span className="stamp mini"><span className="stamp-top">Verified</span><span className="stamp-mid">PUNCA</span></span></div>
          <div className="lp-visa"><b>Matrix multiplication</b><span className="stamp mini endorsed"><span className="stamp-top">Endorsed</span><span className="stamp-mid">PUNCA</span></span></div>
        </div>
        <div className="lp-pp-next">
          <div><small>Next destination</small><b>Backpropagation</b></div>
          <div className="lp-route"><span className="gap">Chain rule</span>→<span>Gradient descent</span>→<span>Backprop</span></div>
        </div>
      </div>
    </div>
  )
}

export default function LandingPage({ user, onStart, onSignIn }) {
  const signedIn = !!user
  return (
    <div className="lp">
      <header className="lp-nav">
        <a className="brand" href="#/"><svg viewBox="0 0 64 64" aria-hidden="true"><path d="M32 8c-8 10-16 18-16 28a16 16 0 0 0 32 0c0-10-8-18-16-28z" /><circle cx="32" cy="38" r="5" /></svg><span>Punca</span></a>
        <nav>
          <button onClick={() => scrollTo('problem')}>Problem</button>
          <button onClick={() => scrollTo('impact')}>Impact</button>
          <button onClick={() => scrollTo('solution')}>How it works</button>
          <button onClick={() => scrollTo('passport')}>Passport</button>
          <button onClick={() => scrollTo('lecturers')}>For lecturers</button>
        </nav>
        <div className="lp-nav-cta">
          {!signedIn && <button className="btn ghost small" onClick={onSignIn}>Sign in</button>}
          <button className="btn primary small" onClick={onStart}>{signedIn ? 'Open my passport' : 'Create my passport'}</button>
        </div>
      </header>

      <section className="lp-hero">
        <div className="lp-hero-text">
          <div className="lp-eyebrow">Built for APU students</div>
          <h1>Stuck on a topic?<br /><span>Find the earlier lesson that’s holding you back.</span></h1>
          <p className="lp-lead">Often you’re not bad at the new topic. You just missed something it builds on. Punca asks you up to 5 quick questions to find it, then helps you fix it.</p>
          <p className="lp-malay">Cari puncanya, bukan sekadar jawapannya. <span>Find the cause, not just the answer.</span></p>
          <div className="lp-cta">
            <button className="btn primary big" onClick={onStart}>{signedIn ? 'Open my passport' : 'Create my passport'}</button>
            <button className="btn big" onClick={() => scrollTo('solution')}>See how it works</button>
          </div>
          <ul className="lp-ticks">
            <li>Free for APU students</li><li>Not a grade</li><li>Sharing is opt-in</li>
          </ul>
        </div>
        <HeroPassport />
      </section>

      <section id="problem" className="lp-section">
        <div className="lp-kicker">The problem</div>
        <h2>New topics are built on old ones. So are the struggles.</h2>
        <p className="lp-sub">In maths, science, engineering and computing, every topic builds on earlier ones. When a new topic feels impossible, the real problem is often an older one you never fully understood. You can’t see that, so you re-read the same slides and fall further behind. Nobody connects <em>“I’m stuck on this lab”</em> to <em>“you missed this earlier topic, and here’s how to fix it.”</em></p>
        <div className="lp-cards four">
          {PROBLEMS.map((p) => <div key={p.who} className="lp-card"><h3>{p.who}</h3><p>{p.text}</p></div>)}
        </div>
      </section>

      <section id="impact" className="lp-section lp-tint">
        <div className="lp-kicker">Why it matters</div>
        <h2>What the research says</h2>
        <p className="lp-sub">Numbers from published studies (sources at the bottom of the page). Our own survey of APU students is in progress.</p>
        <div className="lp-stats">
          {STATS.map((s) => (
            <div key={s.big} className="lp-stat">
              <div className="lp-stat-big">{s.big}</div>
              <p>{s.text}</p>
              <a href={`#src-${s.src}`} onClick={(e) => { e.preventDefault(); scrollTo(`src-${s.src}`) }} className="lp-srclink">Source [{s.src}]</a>
            </div>
          ))}
        </div>
        <div className="lp-split">
          <blockquote className="lp-quote">
            “The most important single factor influencing learning is what the learner already knows.”
            <cite>David Ausubel, 1968 [6]</cite>
          </blockquote>
          <div className="lp-local">
            <div className="lp-stat-big small">50.83%</div>
            <p>of Malaysian students were in STEM in 2024. The national target is 60%, so every student who gives up on STEM counts. <a href="#src-5" onClick={(e) => { e.preventDefault(); scrollTo('src-5') }} className="lp-srclink">Source [5]</a></p>
          </div>
        </div>
        <div className="lp-bridge">
          <div><b>Start from what you already know</b><span>What you already understand decides how well you learn the next topic [6]. Punca finds the piece that’s missing.</span></div>
          <div><b>Practise, don’t just re-read</b><span>Students fail far less when classes include active practice [2]. Punca gives you practice questions and a study group.</span></div>
          <div><b>Personal help for everyone</b><span>One-to-one tutoring works best but is expensive [4]. Punca gives every student the “find what’s missing” part for free.</span></div>
        </div>
      </section>

      <section id="solution" className="lp-section">
        <div className="lp-kicker">Our solution</div>
        <h2>From “I’m stuck” to the exact topic to fix</h2>
        <div className="lp-steps">
          {STEPS.map((s) => <div key={s.n} className="lp-step"><span className="lp-step-n">{s.n}</span><h3>{s.title}</h3><p>{s.text}</p></div>)}
        </div>
        <div className="lp-demo">
          <div className="lp-demo-q"><small>Example: a student in a machine-learning lab</small>“I don’t get how backpropagation works in my neural network lab.”</div>
          <div className="lp-demo-a">
            <small>Punca, after 5 quick questions</small>
            <div className="lp-demo-h">The problem isn’t <s>Backpropagation</s>. It’s the <b>Chain rule</b> from calculus.</div>
            <ul>
              <li className="no">Backpropagation · incorrect</li>
              <li className="no">Chain rule · incorrect · slip: forgot the inner derivative</li>
              <li className="ok">Gradient descent · correct</li>
              <li className="ok">Neural network forward pass · correct</li>
              <li className="ok">Basic differentiation rules · correct</li>
            </ul>
            <div className="lp-route"><span className="gap">Chain rule</span>→<span>Backpropagation</span></div>
          </div>
        </div>
      </section>

      <section id="passport" className="lp-section lp-tint">
        <div className="lp-kicker">The Punca Passport</div>
        <h2>Your progress, stamped</h2>
        <p className="lp-sub">Every topic you prove you understand earns a stamp. Every missing topic is marked “entry required” until you fix it. Your passport shows how far you’ve come, and Punca shows the route to where you’re stuck.</p>
        <div className="lp-cards three">
          <div className="lp-card"><span className="stamp mini static"><span className="stamp-top">Verified</span><span className="stamp-mid">PUNCA</span></span><h3>Verified stamp</h3><p>Earned only by passing a re-check after you’ve worked on the gap. A first diagnosis never earns one, so guessing doesn’t work.</p></div>
          <div className="lp-card"><span className="stamp mini endorsed static"><span className="stamp-top">Endorsed</span><span className="stamp-mid">PUNCA</span></span><h3>Endorsed stamp</h3><p>Your lecturer countersigns it after a study circle session or a consultation.</p></div>
          <div className="lp-card"><span className="lp-entry">Entry required</span><h3>Entry required</h3><p>Points at exactly one concept to clear next, instead of a vague feeling of falling behind.</p></div>
        </div>
        <p className="lp-note">Stamps are study aids, not grades or credentials. No leaderboards. Nobody sees your passport unless you choose to share it.</p>
      </section>

      <section id="lecturers" className="lp-section">
        <div className="lp-kicker">For lecturers</div>
        <h2>See the gap before the lab, not at the exam</h2>
        <div className="lp-split">
          <ul className="lp-list">
            <li><b>Who needs help, in numbers.</b> For example: “12 students need a chain-rule refresher before Lab 5.”</li>
            <li><b>A class heatmap.</b> Which earlier topics are causing trouble in which labs.</li>
            <li><b>Consultations that fill themselves.</b> Post your consultation hours; Punca groups students who are stuck on the same topic and free at the same time.</li>
            <li><b>Private by default.</b> Aggregates only, hidden below 3 students; names appear only when students opt in.</li>
          </ul>
          <div className="lp-heat" aria-label="Example heatmap">
            <div className="lp-heat-row head"><span /><span>Lab 2</span><span>Lab 3</span><span>Lab 5</span></div>
            <div className="lp-heat-row"><span>Chain rule</span><i style={{ '--h': 0.1 }}>·</i><i style={{ '--h': 0.1 }}>·</i><i className="strong" style={{ '--h': 1 }}>19</i></div>
            <div className="lp-heat-row"><span>Matrix mult.</span><i style={{ '--h': 0.1 }}>·</i><i className="strong" style={{ '--h': 0.7 }}>13</i><i style={{ '--h': 0.25 }}>4</i></div>
            <div className="lp-heat-row"><span>Logarithms</span><i style={{ '--h': 0.2 }}>3</i><i style={{ '--h': 0.1 }}>·</i><i style={{ '--h': 0.1 }}>·</i></div>
            <small>Illustration with synthetic numbers.</small>
          </div>
        </div>
      </section>

      <section className="lp-section lp-trust">
        <div className="lp-cards four">
          <div className="lp-card"><h3>Grounded, with citations</h3><p>Explanations come only from course notes and cite them. If the notes don’t cover it, Punca says so instead of inventing content.</p></div>
          <div className="lp-card"><h3>Clear reasons</h3><p>You see every answer Punca used to decide what you’re missing, and you can tell it “I actually know this”.</p></div>
          <div className="lp-card"><h3>Built on Google AI</h3><p>Gemini with a pinned model and structured JSON output. Designed for Google Cloud (Cloud Run, Firestore, Vertex AI).</p></div>
          <div className="lp-card"><h3>Honest by design</h3><p>A probabilistic estimate, not a certified assessment. Demo cohort data is synthetic and labelled that way.</p></div>
        </div>
      </section>

      <section className="lp-final">
        <h2>Your first stamp is five questions away.</h2>
        <p>Create your Punca Passport, make it yours, and find the cause, not just the answer.</p>
        <div className="lp-cta center">
          <button className="btn primary big" onClick={onStart}>{signedIn ? 'Open my passport' : 'Create my passport'}</button>
          {!signedIn && <button className="btn big light" onClick={onSignIn}>I already have one: sign in</button>}
        </div>
      </section>

      <footer className="lp-foot">
        <h3>Sources</h3>
        <ol className="lp-sources">
          {SOURCES.map((s) => (
            <li key={s.n} id={`src-${s.n}`}>{s.url ? <a href={s.url} target="_blank" rel="noreferrer noopener">{s.text}</a> : s.text}</li>
          ))}
        </ol>
        <p className="fine">Punca prototype · APU Cloud Innovation Hackathon 2026 · Smart Campus &amp; Student Experience. Figures above come from the published sources listed; demo data inside the app is synthetic.</p>
      </footer>
    </div>
  )
}
