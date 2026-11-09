import React from 'react'

const LETTERS = ['A', 'B', 'C', 'D', 'E', 'F']

/** One multiple-choice question. feedback = {correct, correctIndex, explanation, misconceptionLabel} after answering. */
export default function ProbeCard({ probe, onAnswer, chosen, feedback, busy, eyebrow }) {
  const answered = feedback != null
  return (
    <div className="probe">
      {eyebrow && <div className="eyebrow">{eyebrow}</div>}
      <h3 className="probe-q">{probe.question}</h3>
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
          {!feedback.correct && feedback.misconceptionLabel && (
            <div className="mis">Possible slip: {feedback.misconceptionLabel.toLowerCase()}</div>
          )}
        </div>
      )}
    </div>
  )
}
