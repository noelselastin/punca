import React, { useMemo } from 'react'

const W = 176
const H = 44
const GX = 54
const GY = 14
const PAD = 16

function wrap(name, max = 22) {
  const words = name.split(' ')
  const lines = ['']
  for (const w of words) {
    const cur = lines[lines.length - 1]
    if ((cur + ' ' + w).trim().length <= max) lines[lines.length - 1] = (cur + ' ' + w).trim()
    else lines.push(w)
  }
  if (lines.length > 2) return [lines[0], lines.slice(1).join(' ').slice(0, max - 1) + '…']
  return lines
}

/**
 * Layered drawing of the prerequisite graph: prerequisites on the left, the concepts that need them on the right.
 * props.include: Set of concept ids to draw (null = all). props.stateOf(id) -> solid|shaky|gap|stamped|...
 */
export default function ConceptMap({ concepts, include = null, stateOf, highlight = [], root, target, onPick }) {
  const layout = useMemo(() => {
    const byId = Object.fromEntries(concepts.map((c) => [c.id, c]))
    const ids = concepts.map((c) => c.id).filter((id) => !include || include.has(id))
    const inSet = new Set(ids)
    const memo = {}
    const level = (id) => {
      if (memo[id] === undefined) {
        const prs = byId[id].prerequisites.filter((p) => inSet.has(p))
        memo[id] = prs.length ? 1 + Math.max(...prs.map(level)) : 0
      }
      return memo[id]
    }
    const cols = []
    ids.forEach((id) => { const l = level(id); (cols[l] = cols[l] || []).push(id) })
    const rowOf = {}
    cols.forEach((col, ci) => {
      col.sort((a, b) => (byId[a].area + byId[a].name).localeCompare(byId[b].area + byId[b].name))
      if (ci > 0) {
        const bary = (id) => {
          const prs = byId[id].prerequisites.filter((p) => inSet.has(p) && rowOf[p] !== undefined)
          return prs.length ? prs.reduce((s, p) => s + rowOf[p], 0) / prs.length : 0
        }
        col.sort((a, b) => bary(a) - bary(b))
      }
      col.forEach((id, i) => { rowOf[id] = i })
    })
    const pos = {}
    cols.forEach((col, ci) => col.forEach((id, i) => { pos[id] = { x: PAD + ci * (W + GX), y: PAD + i * (H + GY) } }))
    const width = PAD * 2 + cols.length * W + (cols.length - 1) * GX
    const height = PAD * 2 + Math.max(...cols.map((c) => c.length)) * (H + GY) - GY
    const edges = []
    ids.forEach((id) => byId[id].prerequisites.forEach((p) => { if (inSet.has(p)) edges.push([p, id]) }))
    return { byId, ids, pos, width, height, edges }
  }, [concepts, include])

  const hl = new Set(highlight)
  const onPath = (a, b) => hl.has(a) && hl.has(b)

  return (
    <div className="cmap-wrap">
      <svg className="cmap" width={layout.width} height={layout.height} role="img"
        aria-label="Concept dependency map: prerequisites on the left, later concepts on the right">
        {layout.edges.map(([p, c]) => {
          const a = layout.pos[p]
          const b = layout.pos[c]
          const x1 = a.x + W
          const y1 = a.y + H / 2
          const x2 = b.x
          const y2 = b.y + H / 2
          const mx = (x1 + x2) / 2
          return <path key={p + c} d={`M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`}
            className={onPath(p, c) ? 'edge on' : 'edge'} />
        })}
        {layout.ids.map((id) => {
          const { x, y } = layout.pos[id]
          const st = stateOf ? stateOf(id) : 'untested'
          const lines = wrap(layout.byId[id].name)
          const tag = id === root ? 'ROOT CAUSE' : id === target ? 'STUCK HERE' : null
          return (
            <g key={id} transform={`translate(${x},${y})`} className={`node s-${st}${hl.has(id) ? ' hl' : ''}${onPick ? ' pick' : ''}`}
              onClick={onPick ? () => onPick(id) : undefined}>
              <title>{layout.byId[id].name}: {layout.byId[id].description}</title>
              <rect width={W} height={H} rx="9" />
              <circle cx="14" cy={H / 2} r="5" className="pip" />
              {lines.map((ln, i) => (
                <text key={i} x="26" y={lines.length === 1 ? H / 2 + 4 : 18 + i * 14}>{ln}</text>
              ))}
              {tag && <text className="tag" x={W - 6} y="-4" textAnchor="end">{tag}</text>}
            </g>
          )
        })}
      </svg>
    </div>
  )
}

export function MapLegend() {
  return (
    <div className="legend">
      <span><i className="lg solid" />Solid / stamped</span>
      <span><i className="lg shaky" />Shaky</span>
      <span><i className="lg gap" />Gap / entry required</span>
      <span><i className="lg untested" />Untested</span>
    </div>
  )
}
