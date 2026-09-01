import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useToast } from '../components/ToastHost'
import { displaySkillName } from '../lib/analysisUi'
import { useSession } from './SessionContext'

const STORAGE_KEY = 'skillbridge.roadmapExtras.v1'

const RoadmapExtrasContext = createContext(null)

function readStore() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
  } catch {
    return {}
  }
}

function writeStore(store) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store))
}

function bucketKey(userId, cvId) {
  return `${userId || 'anon'}:${cvId || 'none'}`
}

function learnUrlForSkill(skill) {
  const q = encodeURIComponent(String(skill || '').trim())
  if (!q) return null
  // Prefer freeCodeCamp search; always a real URL so "Add to roadmap" never shows "No link yet"
  return `https://www.freecodecamp.org/news/search/?query=${q}`
}

function buildTasksForSkill(skill, { demand_pct, reason, priority } = {}) {
  const name = displaySkillName(skill) || skill
  const baseId = String(skill || name).toLowerCase().replace(/\s+/g, '-')
  const learnUrl = learnUrlForSkill(name)
  const metaBits = [
    'Added from skill gaps',
    demand_pct != null ? `${Math.round(Number(demand_pct))}% demand` : null,
    priority ? String(priority) : null,
  ].filter(Boolean)

  return [
    {
      id: `user:${baseId}:study`,
      kind: 'user',
      phase: 'days_30',
      skill,
      label: `Study ${name} fundamentals with a hands-on project`,
      meta: metaBits.join(' · '),
      url: learnUrl,
      reason: reason || null,
      addedAt: Date.now(),
    },
    {
      id: `user:${baseId}:apply`,
      kind: 'user',
      phase: 'days_60',
      skill,
      label: `Apply ${name} in one portfolio piece and document it`,
      meta: metaBits.join(' · '),
      url: learnUrl,
      addedAt: Date.now(),
    },
    {
      id: `user:${baseId}:verify`,
      kind: 'user',
      phase: 'days_90',
      skill,
      label: `Re-run analysis after practicing ${name} and compare match-rate lift`,
      meta: metaBits.join(' · '),
      url: learnUrl,
      addedAt: Date.now(),
    },
  ]
}

export function RoadmapExtrasProvider({ children }) {
  const { userId, cvId } = useSession()
  const { push } = useToast()
  const navigate = useNavigate()
  const key = bucketKey(userId, cvId)

  const [store, setStore] = useState(() => readStore())
  const extras = store[key] || []

  const addSkillToRoadmap = useCallback(
    (gap, { navigateToRoadmap = true } = {}) => {
      const skill = gap?.skill
      if (!skill) return false

      const tasks = buildTasksForSkill(skill, gap)
      const prev = readStore()
      const current = prev[key] || []
      const existingIds = new Set(current.map((t) => t.id))
      const fresh = tasks.filter((t) => !existingIds.has(t.id))

      if (!fresh.length) {
        push(`${displaySkillName(skill)} is already on your roadmap`)
        if (navigateToRoadmap) navigate(`/roadmap?highlight=${encodeURIComponent(skill)}`)
        return false
      }

      const next = { ...prev, [key]: [...current, ...fresh] }
      writeStore(next)
      setStore(next)
      push(`Added ${displaySkillName(skill)} to your roadmap`)
      if (navigateToRoadmap) navigate(`/roadmap?highlight=${encodeURIComponent(skill)}`)
      return true
    },
    [key, navigate, push],
  )

  const removeSkillFromRoadmap = useCallback(
    (skill) => {
      const needle = String(skill || '').toLowerCase()
      const prev = readStore()
      const next = {
        ...prev,
        [key]: (prev[key] || []).filter((t) => String(t.skill || '').toLowerCase() !== needle),
      }
      writeStore(next)
      setStore(next)
    },
    [key],
  )

  const value = useMemo(
    () => ({ extras, addSkillToRoadmap, removeSkillFromRoadmap }),
    [extras, addSkillToRoadmap, removeSkillFromRoadmap],
  )

  return <RoadmapExtrasContext.Provider value={value}>{children}</RoadmapExtrasContext.Provider>
}

export function useRoadmapExtras() {
  const ctx = useContext(RoadmapExtrasContext)
  if (!ctx) throw new Error('useRoadmapExtras must be used within RoadmapExtrasProvider')
  return ctx
}
