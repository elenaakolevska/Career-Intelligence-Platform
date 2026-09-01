import { useEffect, useState } from 'react'

const CIRC = 2 * Math.PI * 49

export function HeroRing({ score = 0, maxScore = 100 }) {
  const clamped = Math.max(0, Math.min(maxScore, Number(score) || 0))
  const [display, setDisplay] = useState(0)
  const offset = CIRC - (CIRC * display) / maxScore

  useEffect(() => {
    const reduce =
      typeof window !== 'undefined' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    if (reduce) {
      setDisplay(Math.round(clamped))
      return undefined
    }
    let raf = 0
    const start = performance.now()
    const tick = (now) => {
      const t = Math.min(1, (now - start) / 900)
      const eased = 1 - (1 - t) ** 3
      setDisplay(Math.round(clamped * eased))
      if (t < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [clamped])

  return (
    <div className="ring" aria-label={`Score ${Math.round(clamped)} of ${maxScore}`}>
      <svg viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="49" fill="none" stroke="#dbe9e3" strokeWidth="10" />
        <circle
          cx="60"
          cy="60"
          r="49"
          fill="none"
          stroke="#087f5b"
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={CIRC}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="center">
        <div className="score">{display}</div>
        <div className="den">/ {maxScore}</div>
      </div>
    </div>
  )
}

export function MetricCard({ icon, iconStyle, value, label, trend, trendStyle, labelFirst }) {
  return (
    <div className={`card metric ${labelFirst ? 'metric-stack' : ''}`}>
      {labelFirst ? (
        <>
          <div className="metriclabel">{label}</div>
          <div className="metricnum">{value}</div>
        </>
      ) : (
        <>
          {icon != null && (
            <div className="metricicon" style={iconStyle}>
              {icon}
            </div>
          )}
          <div className="metricnum">{value}</div>
          <div className="metriclabel">{label}</div>
        </>
      )}
      {trend != null && (
        <div className="trend" style={trendStyle}>
          {trend}
        </div>
      )}
    </div>
  )
}

export function SkillBar({ name, value, tone = 'green', suffix, large, tag, demand }) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0))
  const demandPct =
    demand == null || Number.isNaN(Number(demand))
      ? null
      : Math.max(0, Math.min(100, Number(demand)))
  return (
    <div className={large ? 'barlarge' : 'skill'}>
      <div className="skilltop">
        <b>
          {name}
          {tag}
        </b>
        <span>
          {suffix != null
            ? suffix
            : demandPct != null
              ? `${Math.round(pct)}% you · ${Math.round(demandPct)}% mkt`
              : `${Math.round(pct)}%`}
        </span>
      </div>
      <div className="track">
        <div className={`fill ${tone}`} style={{ width: `${pct}%` }} />
        {demandPct != null && (
          <span
            className="demand-mark"
            style={{ left: `${demandPct}%` }}
            title={`Market demand ${Math.round(demandPct)}%`}
            aria-label={`Market demand ${Math.round(demandPct)} percent`}
          />
        )}
      </div>
    </div>
  )
}

export function JobRow({ company, title, meta, matchPct, onView, compact }) {
  const initials = String(company || title || '?')
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0])
    .join('')
    .toUpperCase() || '?'
  const pct = typeof matchPct === 'number' ? Math.round(matchPct) : null
  const tone = pct == null ? '' : pct >= 80 ? '' : pct >= 60 ? 'mid' : 'lo'
  const hue = (initials.charCodeAt(0) || 0) % 3
  const logoStyle =
    hue === 1
      ? { background: 'var(--primary-soft)', color: 'var(--primary2)' }
      : hue === 2
        ? { background: 'var(--amber-soft)', color: 'var(--amber)' }
        : undefined

  return (
    <div className="job" style={compact ? undefined : { padding: '16px 0' }}>
      <div className="joblogo" style={logoStyle}>
        {initials.slice(0, 2)}
      </div>
      <div className="jobinfo">
        <div className="jobtitle">{title || 'Untitled role'}</div>
        <div className="jobmeta">{meta}</div>
      </div>
      {pct != null && <span className={`match ${tone}`}>{pct}%{compact ? '' : ' match'}</span>}
      {onView && (
        <button type="button" className="btn" onClick={onView}>
          View
        </button>
      )}
    </div>
  )
}

export function PageHeader({ eyebrow, title, sub, actions }) {
  return (
    <div className="pagehead">
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {sub && <p className="sub">{sub}</p>}
      </div>
      {actions}
    </div>
  )
}

export function ViewShell({ children }) {
  return <div className="view-enter">{children}</div>
}
