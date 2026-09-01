/**
 * Helpers to map analysis report → prototype UI shapes.
 */

export function greetingName(fullName, email) {
  if (fullName?.trim()) return fullName.trim().split(/\s+/)[0]
  if (email) return email.split('@')[0]
  return 'there'
}

export function initialsFrom(fullName, email) {
  if (fullName?.trim()) {
    const parts = fullName.trim().split(/\s+/).filter(Boolean)
    if (parts.length >= 2) return `${parts[0][0]}${parts[1][0]}`.toUpperCase()
    return parts[0].slice(0, 2).toUpperCase()
  }
  if (email) return email.slice(0, 2).toUpperCase()
  return 'SB'
}

/** Strip CV-extractor bullets / zero-width chars from skill labels. */
export function cleanSkillLabel(raw) {
  return String(raw || '')
    .replace(/^[\s●•▪◦\-–—*]+/u, '')
    .replace(/[\u200b\u200c\u200d\ufeff]/g, '')
    .trim()
}

/** Expand short lexicon labels for display (e.g. embedded → Embedded Systems). */
const SKILL_DISPLAY_NAMES = {
  embedded: 'Embedded Systems',
  'embedded systems': 'Embedded Systems',
}

export function displaySkillName(raw) {
  const cleaned = cleanSkillLabel(raw)
  if (!cleaned) return cleaned
  const mapped = SKILL_DISPLAY_NAMES[cleaned.toLowerCase()]
  return mapped || cleaned
}

export function extractSkills(cv, report) {
  const structured = report?.cv_summary?.structured_cv || cv?.structured_data || {}
  if (!Array.isArray(structured?.skills)) return []
  return structured.skills.map(cleanSkillLabel).filter(Boolean)
}

function clipSentence(text, max = 160) {
  const t = String(text || '').replace(/\s+/g, ' ').trim()
  if (!t) return null
  if (t.length <= max) return t
  const cut = t.slice(0, max)
  const at = cut.lastIndexOf(' ')
  return `${(at > 80 ? cut.slice(0, at) : cut).trim()}…`
}

/**
 * Build a short cohesive profile paragraph for the CV page.
 */
export function buildProfileSummary(cv, report) {
  const structured = report?.cv_summary?.structured_cv || cv?.structured_data || {}
  const text = report?.cv_summary?.text || cv?.summary || ''

  const name = structured?.name || null
  const location = structured?.location || null
  const about = clipSentence(structured?.summary || '', 180)
  const skills = extractSkills(cv, report).slice(0, 8)

  const exp = Array.isArray(structured?.experience) ? structured.experience[0] : null
  const roleBits = exp
    ? [exp.title, exp.company].filter(Boolean).join(' at ')
    : null

  const edu = Array.isArray(structured?.education) ? structured.education[0] : null
  const eduBits = edu
    ? [edu.degree, edu.institution].filter(Boolean).join(', ')
    : null

  const sentences = []
  if (name && location) sentences.push(`${name} is based in ${location}.`)
  else if (name) sentences.push(`${name}.`)
  else if (location) sentences.push(`Based in ${location}.`)

  if (about) sentences.push(about.endsWith('.') ? about : `${about}.`)
  if (roleBits) sentences.push(`Most recent role: ${roleBits}.`)
  if (eduBits) sentences.push(`Education: ${eduBits}.`)
  if (skills.length) {
    sentences.push(`Key skills include ${skills.map(displaySkillName).join(', ')}.`)
  }

  const paragraph = sentences.join(' ').trim()
  if (paragraph) {
    return { paragraph, fallbackText: null }
  }

  if (text && text !== 'No AI summary available yet.') {
    return { paragraph: null, fallbackText: clipSentence(text, 320) || text }
  }

  return { paragraph: null, fallbackText: 'No AI summary available yet.' }
}

export function extractGaps(report) {
  return Array.isArray(report?.skill_gaps?.gaps) ? report.skill_gaps.gaps : []
}

export function extractMatches(report) {
  return Array.isArray(report?.top_matches?.jobs) ? report.top_matches.jobs : []
}

export function extractIssues(cv, report) {
  const ats = report?.ats || {}
  if (Array.isArray(ats.issues)) return ats.issues
  if (Array.isArray(cv?.ats_issues)) return cv.ats_issues
  return []
}

export function readinessScore(cv, report, matches) {
  const ats = report?.ats?.score ?? cv?.ats_score
  const avg =
    matches.length > 0
      ? (matches.reduce((s, j) => s + (typeof j.score === 'number' ? j.score : 0), 0) / matches.length) *
        100
      : null
  if (typeof ats === 'number' && avg != null) return Math.round(ats * 0.55 + avg * 0.45)
  if (typeof ats === 'number') return Math.round(ats)
  if (avg != null) return Math.round(avg)
  return null
}

export function avgMatchPct(matches) {
  if (!matches.length) return null
  return Math.round(
    (matches.reduce((s, j) => s + (typeof j.score === 'number' ? j.score : 0), 0) / matches.length) *
      100,
  )
}

export function skillProfileRows(skills, gaps, trends) {
  const gapMap = new Map(gaps.map((g) => [String(g.skill).toLowerCase(), g]))
  const trendSkills = trends?.top_skills || trends?.data?.top_skills || []
  const trendMap = new Map(
    (Array.isArray(trendSkills) ? trendSkills : []).map((t) => [
      String(t.skill).toLowerCase(),
      Number(t.pct_of_postings ?? t.demand_pct ?? t.pct) || 0,
    ]),
  )

  const demandFor = (skillName, fallback) => {
    const key = String(skillName).toLowerCase()
    const g = gapMap.get(key)
    if (g?.demand_pct != null) return Number(g.demand_pct)
    if (trendMap.has(key)) return trendMap.get(key)
    return fallback
  }

  const toneForLevel = (you, index) => {
    // Prototype palette: strong green → purple → amber → red
    if (you >= 82 || index === 0) return 'green'
    if (you >= 62 || index <= 2) return 'indigo'
    if (you >= 40 || index === 3) return 'amber'
    return 'red'
  }

  const fromSkills = skills.slice(0, 5).map((s, i) => {
    const demand = demandFor(s, Math.max(28, 70 - i * 9))
    const g = gapMap.get(String(s).toLowerCase())
    const you = g
      ? Math.max(18, Math.min(88, 52 - Number(g.demand_pct || demand) * 0.2 + (4 - i) * 4))
      : Math.max(48, 92 - i * 8)
    return {
      name: displaySkillName(s),
      value: you,
      demand,
      tone: toneForLevel(you, i),
    }
  })
  const extraGaps = gaps
    .filter((g) => !skills.some((s) => String(s).toLowerCase() === String(g.skill).toLowerCase()))
    .slice(0, Math.max(0, 5 - fromSkills.length))
    .map((g, i) => {
      const demand = Number(g.demand_pct) || 50
      const you = Math.max(12, 38 - demand * 0.18 - i * 4)
      const index = fromSkills.length + i
      return {
        name: displaySkillName(g.skill),
        value: you,
        demand,
        tone: toneForLevel(you, index),
      }
    })

  const rows = [...fromSkills, ...extraGaps].slice(0, 5)
  // Re-apply tones by rank so the list always reads green → purple → amber → red
  const rankTones = ['green', 'indigo', 'indigo', 'amber', 'red']
  return rows
    .slice()
    .sort((a, b) => b.value - a.value)
    .map((row, i) => ({ ...row, tone: rankTones[i] || 'red' }))
}

export function fillToneForDemand(demand, priority) {
  const p = String(priority || '').toLowerCase()
  if (p === 'high' || demand >= 60) return 'red'
  if (p === 'medium' || demand >= 40) return 'amber'
  return 'green'
}

export function impactLabel(priority) {
  const p = String(priority || 'medium').toLowerCase()
  if (p === 'high') return 'HIGH IMPACT'
  if (p === 'low') return 'NICE TO HAVE'
  return 'MEDIUM'
}

export function jobMeta(job) {
  const skills = Array.isArray(job.skills) ? job.skills.slice(0, 3).join(' · ') : null
  return [job.company, job.location || 'Remote', job.salary, skills].filter(Boolean).join(' · ')
}

export function timeAgo(iso) {
  if (!iso) return 'just now'
  const t = new Date(iso).getTime()
  if (Number.isNaN(t)) return 'recently'
  const mins = Math.max(1, Math.round((Date.now() - t) / 60000))
  if (mins < 60) return `${mins} min ago`
  const hrs = Math.round(mins / 60)
  if (hrs < 48) return `${hrs} hour${hrs === 1 ? '' : 's'} ago`
  return new Date(iso).toLocaleDateString()
}
