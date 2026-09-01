import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { displaySkillName } from '../lib/analysisUi'
import { useRoadmapExtras } from './RoadmapExtrasContext'

const SkillDrawerContext = createContext(null)

export function SkillDrawerProvider({ children }) {
  const [open, setOpen] = useState(false)
  const [skill, setSkill] = useState(null)

  const openSkill = useCallback((payload) => {
    setSkill(payload || null)
    setOpen(true)
  }, [])

  const closeSkill = useCallback(() => {
    setOpen(false)
  }, [])

  const value = useMemo(
    () => ({ open, skill, openSkill, closeSkill }),
    [open, skill, openSkill, closeSkill],
  )

  return (
    <SkillDrawerContext.Provider value={value}>
      {children}
      <SkillDrawer />
    </SkillDrawerContext.Provider>
  )
}

export function useSkillDrawer() {
  const ctx = useContext(SkillDrawerContext)
  if (!ctx) throw new Error('useSkillDrawer must be used within SkillDrawerProvider')
  return ctx
}

function SkillDrawer() {
  const { open, skill, closeSkill } = useSkillDrawer()
  const { addSkillToRoadmap } = useRoadmapExtras()
  if (!skill && !open) return null

  const name = displaySkillName(skill?.skill) || 'Skill'
  const demand = skill?.demand_pct != null ? Math.round(Number(skill.demand_pct)) : null
  const impact = skill?.impact_pct != null ? Math.round(Number(skill.impact_pct)) : Math.max(6, Math.round((demand || 40) / 7))
  const priority = String(skill?.priority || 'high').toLowerCase()
  const reason = skill?.reason || 'Identified from your CV and the job market for your target roles.'
  const steps = skill?.steps || [
    `Complete ${name} fundamentals.`,
    `Apply ${name} in one existing project.`,
    'Document it on your CV and portfolio.',
  ]

  return (
    <div className={`drawer ${open ? 'open' : ''}`} role="dialog" aria-modal="true" aria-label={`${name} skill analysis`}>
      <div className="backdrop" onClick={closeSkill} />
      <aside className="panel">
        <button type="button" className="close" onClick={closeSkill} aria-label="Close">
          ×
        </button>
        <div className="eyebrow">AI skill analysis</div>
        <h2>{name}</h2>
        <p className="desc">A high-impact skill gap identified from your CV and the job market.</p>
        <div className="panelsection">
          <div className="impact">
            <div>
              <b>+{impact}%</b>
              <span style={{ display: 'block' }}>potential match-rate impact</span>
            </div>
            <strong style={{ color: 'var(--primary2)' }}>{priority === 'high' ? 'HIGH' : priority.toUpperCase()}</strong>
          </div>
        </div>
        <div className="panelsection">
          <h4>Why this matters</h4>
          <p className="desc">
            {demand != null
              ? `${name} appears in ${demand}% of the roles that fit your current profile. ${reason}`
              : reason}
          </p>
        </div>
        <div className="panelsection">
          <h4>What we found</h4>
          <div className="recommend">
            <i>×</i>
            <span>No strong evidence of {name} experience detected in your CV.</span>
          </div>
          <div className="recommend">
            <i>✓</i>
            <span>Your existing backend foundation provides a good base to close this gap.</span>
          </div>
        </div>
        <div className="panelsection">
          <h4>Recommended next steps</h4>
          {steps.map((step, idx) => (
            <div className="recommend" key={step}>
              <i>{String(idx + 1).padStart(2, '0')}</i>
              <span>{step}</span>
            </div>
          ))}
        </div>
        <button
          type="button"
          className="btn primary"
          style={{ width: '100%', justifyContent: 'center', marginTop: 20 }}
          onClick={() => {
            addSkillToRoadmap(skill)
            closeSkill()
          }}
        >
          Add to roadmap →
        </button>
        <Link
          className="btn"
          style={{ width: '100%', justifyContent: 'center', marginTop: 8 }}
          to="/roadmap"
          onClick={closeSkill}
        >
          Open roadmap
        </Link>
      </aside>
    </div>
  )
}
