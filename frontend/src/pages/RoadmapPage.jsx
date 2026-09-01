import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import AnalysisGate from '../components/AnalysisGate'
import { PageHeader, ViewShell } from '../components/ui'
import { useRoadmapExtras } from '../context/RoadmapExtrasContext'
import { useAnalysis } from '../context/AnalysisContext'
import { displaySkillName, extractGaps } from '../lib/analysisUi'

const HORIZONS = [
  { key: 'days_30', title: '01 · FIRST 30 DAYS — FOUNDATIONS' },
  { key: 'days_60', title: '02 · DAYS 31–60 — CLOUD & DEPLOYMENT' },
  { key: 'days_90', title: '03 · DAYS 61–90 — INTERVIEW READY' },
]

function buildPhaseItems(section, gapFallback) {
  const skills = section?.skills || []
  const focus = section?.focus || null
  const resources = Array.isArray(section?.resources) ? section.resources : []
  const items = []

  skills.forEach((skill) => {
    const linked = resources.filter(
      (r) => String(r.skill || '').toLowerCase() === String(skill).toLowerCase() && r.url,
    )
    if (linked.length) {
      linked.forEach((r, idx) => {
        items.push({
          id: `skill-res:${skill}:${r.id || r.url || idx}`,
          kind: 'resource',
          label: `Learn ${displaySkillName(skill)}: ${r.title || 'Resource'}`,
          meta: [r.type, r.source].filter(Boolean).join(' · ') || 'Learning resource',
          url: r.url,
          skill,
        })
      })
    } else {
      items.push({
        id: `skill:${skill}`,
        kind: 'skill',
        label: `Build hands-on practice with ${displaySkillName(skill)}`,
        meta: 'Skill to close',
        skill,
      })
    }
  })

  // Resources not already tied to a listed skill
  resources.forEach((r, idx) => {
    if (!r?.url) return
    const already = items.some((it) => it.url === r.url)
    if (already) return
    const skillPart = r.skill ? `${displaySkillName(r.skill)}: ` : ''
    items.push({
      id: `res:${r.id || r.url || idx}`,
      kind: 'resource',
      label: `${skillPart}${r.title || 'Learning resource'}`,
      meta: [r.type, r.source, r.skill ? displaySkillName(r.skill) : null]
        .filter(Boolean)
        .join(' · ') || 'Learning resource',
      url: r.url,
      skill: r.skill,
    })
  })

  if (!items.length && gapFallback?.length) {
    gapFallback.forEach((g) => {
      items.push({
        id: `gap:${g.skill}`,
        kind: 'skill',
        label: `Close gap: ${displaySkillName(g.skill)}`,
        meta: g.reason || 'From skill-gap analysis',
        skill: g.skill,
      })
    })
  }

  return { focus, items }
}

function RoadmapBody() {
  const { report } = useAnalysis()
  const { extras } = useRoadmapExtras()
  const [params] = useSearchParams()
  const highlight = (params.get('highlight') || '').toLowerCase()
  const gaps = extractGaps(report)
  const roadmapWrap = report?.learning_roadmap || {}
  const roadmap = roadmapWrap.roadmap || null
  const storageKey = 'skillbridge.roadmapChecks.v2'
  const [checked, setChecked] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(storageKey) || '{}')
    } catch {
      return {}
    }
  })

  const phases = useMemo(() => {
    const built = HORIZONS.map((h, idx) => {
      const section = roadmap ? roadmap[h.key] || {} : {}
      const { focus, items } = roadmap
        ? buildPhaseItems(section, [])
        : buildPhaseItems({}, gaps.slice(idx * 2, idx * 2 + 3))

      const userItems = extras
        .filter((t) => t.phase === h.key)
        .map((t) => ({
          id: t.id,
          kind: t.kind || 'user',
          label: t.label,
          meta: t.meta,
          url: t.url || null,
          skill: t.skill,
          userAdded: true,
        }))

      // Avoid duplicating user tasks that already match an auto skill label
      const merged = [...userItems]
      items.forEach((it) => {
        const dup = userItems.some(
          (u) =>
            u.skill &&
            it.skill &&
            String(u.skill).toLowerCase() === String(it.skill).toLowerCase() &&
            it.kind === 'skill',
        )
        if (!dup) merged.push(it)
      })

      return { ...h, focus, items: merged }
    })

    // If extras exist but phases had no auto items, still show them
    return built
  }, [roadmap, gaps, extras])

  useEffect(() => {
    if (!highlight) return undefined
    const el = document.querySelector(`[data-skill-highlight="${highlight.replace(/"/g, '')}"]`)
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
    return undefined
  }, [highlight, phases])

  const allKeys = phases.flatMap((p) => p.items.map((it) => `${p.key}::${it.id}`))
  const done = allKeys.filter((k) => checked[k]).length
  const pct = allKeys.length ? Math.round((done / allKeys.length) * 100) : 0
  const linkedCount = phases.reduce(
    (n, p) => n + p.items.filter((it) => it.url).length,
    0,
  )

  function toggle(key) {
    setChecked((prev) => {
      const next = { ...prev, [key]: !prev[key] }
      localStorage.setItem(storageKey, JSON.stringify(next))
      return next
    })
  }

  if (!roadmapWrap.available && !gaps.length && !extras.length) {
    return (
      <ViewShell>
        <PageHeader eyebrow="Personalized learning path" title="Your 90-day roadmap." />
        <div className="card empty-state">No roadmap was generated for this analysis.</div>
      </ViewShell>
    )
  }

  return (
    <ViewShell>
      <PageHeader
        eyebrow="Personalized learning path"
        title="Your 90-day roadmap."
        sub={
          linkedCount
            ? `Generated from your skill gaps · ${linkedCount} resources with learn links`
            : 'Generated from your skill gaps and target roles. Re-run analysis if links are missing.'
        }
        actions={
          <div className="mono" style={{ fontSize: 11, color: 'var(--primary)' }}>
            {pct}% COMPLETE
          </div>
        }
      />

      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, marginBottom: 7 }}>
          <b>Overall progress</b>
          <span>
            {done} of {allKeys.length} tasks
          </span>
        </div>
        <div className="track" style={{ height: 8 }}>
          <div className="fill green" style={{ width: `${pct}%` }} />
        </div>
      </div>

      <div className="card bigcard">
        <div className="timeline">
          {phases.map((phase) => (
            <div className="phase" key={phase.key}>
              <div className="phasehead">{phase.title}</div>
              {phase.focus ? <p className="phase-desc">{phase.focus}</p> : null}
              {phase.items.length === 0 ? (
                <p className="muted" style={{ fontSize: 12, margin: '6px 0 14px' }}>
                  No tasks in this phase yet.
                </p>
              ) : (
                phase.items.map((item) => {
                  const key = `${phase.key}::${item.id}`
                  const isDone = Boolean(checked[key])
                  const isHighlight =
                    highlight &&
                    item.skill &&
                    String(item.skill).toLowerCase() === highlight
                  return (
                    <div
                      key={key}
                      className={`task-row ${isDone ? 'done' : ''} ${isHighlight ? 'task-highlight' : ''} ${item.userAdded ? 'task-user' : ''}`}
                      data-skill-highlight={
                        item.skill ? String(item.skill).toLowerCase() : undefined
                      }
                    >
                      <button
                        type="button"
                        className={`task ${isDone ? 'done' : ''}`}
                        onClick={() => toggle(key)}
                      >
                        <span className="checkbox" />
                        <span className="task-copy">
                          <span className="task-label">{item.label}</span>
                          {item.meta && <small className="task-meta">{item.meta}</small>}
                        </span>
                      </button>
                      {item.url ? (
                        <a
                          className="btn task-learn"
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                        >
                          Open →
                        </a>
                      ) : (
                        <span className="task-nolink muted">No link yet</span>
                      )}
                    </div>
                  )
                })
              )}
            </div>
          ))}
        </div>
      </div>
    </ViewShell>
  )
}

export default function RoadmapPage() {
  return (
    <AnalysisGate title="Roadmap">
      <RoadmapBody />
    </AnalysisGate>
  )
}
