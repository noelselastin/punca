import React from 'react'

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']

const CONFIDENCE_OPTIONS = [
  { id: 'low', label: 'Guessing / Unsure', hint: 'Will still verify prerequisites' },
  { id: 'medium', label: 'Somewhat sure', hint: 'Standard check' },
  { id: 'high', label: 'Confident', hint: 'Certain of this foundation' },
]

/** One multiple-choice question with optional Certainty-Based Marking (confidence selector). */
export default function ProbeCard({
  probe,
  onAnswer,
  chosen,
  feedback,
  busy,
  eyebrow,
  confidence,
  onConfidenceChange,
}) {
  const answered = feedback != null
  return (
    <div className="probe">
      {eyebrow && <div className="eyebrow">{eyebrow}</div>}
      <h3 className="probe-q">{probe.question}</h3>

      {onConfidenceChange && (
        <div className="confidence-picker" role="radiogroup" aria-label="How confident are you in your answer?">
          <span className="confidence-label">How confident are you before answering?</span>
          <div className="confidence-pills">
            {CONFIDENCE_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                type="button"
                role="radio"
                aria-checked={confidence === opt.id}
                disabled={answered || busy}
                className={`conf-pill ${confidence === opt.id ? 'on' : ''} conf-${opt.id}`}
                onClick={() => onConfidenceChange(opt.id)}
              >
                <b>{opt.label}</b>
                <small>{opt.hint}</small>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className="options">
        {probe.options.map((opt, i) => {
          let cls = 'option'
          if (answered && i === feedback.correctIndex) cls += ' right'
          else if (answered && i === chosen) cls += ' wrong'
          else if (!answered && i === chosen) cls += ' picked'
          return (
            <button key={i} className={cls} disabled={answered || busy} onClick={() => onAnswer(i)}>
              <span className="letter">{LETTERS[i]}</span><span>{opt}</span>
            </button>
          )
        })}
      </div>
      {answered && (
        <div className={`feedback ${feedback.correct ? 'ok' : 'no'}`}>
          <b>{feedback.correct ? 'Correct.' : 'Not quite.'}</b> {feedback.explanation}
          {feedback.luckyGuess && (
            <div className="mis">
              Note: You marked <b>Guessing / Unsure</b>, so Punca will still check the underlying prerequisites to make sure this foundation is solid.
            </div>
          )}
          {feedback.highConfidenceGap && (
            <div className="mis">
              High-confidence slip detected — Punca will trace this prerequisite carefully.
            </div>
          )}
          {!feedback.correct && feedback.misconceptionLabel && (
            <div className="mis">Possible slip: {feedback.misconceptionLabel.toLowerCase()}</div>
          )}
        </div>
      )}
    </div>
  )
}
