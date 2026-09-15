import { Link } from 'react-router-dom'
import AnalysisGate from '../components/AnalysisGate'
import { IconBriefcase, IconSpark, IconTrend } from '../components/icons'
import { HeroRing, JobRow, MetricCard, PageHeader, SkillBar, ViewShell } from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { useSkillDrawer } from '../context/SkillDrawerContext'
import { useAnalysis } from '../context/AnalysisContext'
import {
  avgMatchPct,
  displaySkillName,
  extractGaps,
  extractInsights,
  extractMatches,
  extractSkills,
  extractSources,
  greetingName,
  readinessScore,
  skillProfileRows,
  timeAgo,
  jobMeta,
} from '../lib/analysisUi'

function DashboardHero({ score, strong, improve, critical, topGap, matches, name, hello }) {
  return (
    <div className="dashboard-hero">
      <div className="dashboard-hero-copy">
        <div className="eyebrow">Career readiness</div>
        <h2>
          {score != null && score >= 70
            ? 'You’re on a strong path.'
            : score != null && score >= 50
              ? 'Solid foundation — close a few gaps.'
              : 'Let’s strengthen your profile.'}
        </h2>
        <p>
          {topGap
            ? `Your profile is a strong match for roles aligned with your CV. We analyzed your profile against ${matches.length || 'recent'} postings and found that closing your ${topGap.skill} gap could meaningfully improve your opportunities.`
            : 'Your profile is being matched against current openings. Upload or refresh analysis to deepen insights.'}
        </p>
        <div className="chips">
          {strong.length > 0 && <span className="chip good">✓ Strong: {strong.join(' · ')}</span>}
          {improve.length > 0 && (
            <span className="chip warn">
              △ Improve: {improve.map((g) => displaySkillName(g.skill)).join(' · ')}
            </span>
          )}
          {critical.length > 0 && (
            <span className="chip bad">
              × Gap: {critical.map((g) => displaySkillName(g.skill)).join(' · ')}
            </span>
          )}
        </div>
      </div>
      <HeroRing score={score ?? 0} />
    </div>
  )
}

function DashboardMetrics({ matches, avg, gaps, report, cv }) {
  const highGaps = gaps.filter((g) => String(g.priority || '').toLowerCase() === 'high')

  return (
    <div className="dashboard-metrics">
      <MetricCard
        icon={<IconBriefcase />}
        iconStyle={{ background: 'var(--indigo-soft)', color: 'var(--indigo)' }}
        value={matches.length}
        label="relevant job matches"
        trend={matches.length ? `Top score ${Math.round((matches[0]?.score || 0) * 100)}%` : 'Run analysis for matches'}
      />
      <MetricCard
        icon={<IconTrend />}
        iconStyle={{ background: 'var(--primary-soft)', color: 'var(--primary)' }}
        value={avg == null ? '—' : `${avg}%`}
        label="average job match"
        trend={
          typeof (report?.ats?.score ?? cv?.ats_score) === 'number'
            ? `ATS ${Math.round(report?.ats?.score ?? cv?.ats_score)}/100`
            : 'ATS pending'
        }
      />
      <MetricCard
        icon={<IconSpark />}
        iconStyle={{ background: 'var(--amber-soft)', color: 'var(--amber)' }}
        value={gaps.length}
        label="priority skills to close"
        trend={
          highGaps.length ? `${highGaps.length} are high impact` : gaps.length ? 'Prioritize from Skill Gap' : 'No critical gaps'
        }
        trendStyle={highGaps.length ? { color: 'var(--amber)' } : undefined}
      />
    </div>
  )
}

function DashboardFocusPanel({ title, subtitle, children, isEmpty, emptyMessage }) {
  return (
    <div className="card dashboard-block">
      <div className="cardtitle">
        {title} <span>{subtitle}</span>
      </div>
      {isEmpty ? <p className="empty-state">{emptyMessage}</p> : children}
    </div>
  )
}

function DashboardBody() {
  const { user, fullName, userEmail } = useAuth()
  const { cv, report, analysis } = useAnalysis()
  const { openSkill } = useSkillDrawer()

  const skills = extractSkills(cv, report)
  const gaps = extractGaps(report)
  const matches = extractMatches(report)
  const insights = extractInsights(report)
  const sources = extractSources(report)
  const score = readinessScore(cv, report, matches)
  const avg = avgMatchPct(matches)
  const highGaps = gaps.filter((g) => String(g.priority || '').toLowerCase() === 'high')
  const topGap = gaps[0]
  const profileRows = skillProfileRows(skills, gaps, report?.market_trends)
  const name = greetingName(fullName || user?.full_name, userEmail)
  const hour = new Date().getHours()
  const hello = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening'
  const strong = skills.slice(0, 3)
  const improve = gaps.filter((g) => String(g.priority).toLowerCase() === 'medium').slice(0, 2)
  const critical = highGaps.slice(0, 2)

  const impact = topGap
    ? Math.max(6, Math.round((Number(topGap.demand_pct) || 40) / 7))
    : 11

  return (
    <ViewShell>
      <div className="dashboard-page" id="overview-export">
        <PageHeader
          eyebrow={`AI analysis complete · ${timeAgo(analysis?.created_at)}`}
          title={`${hello}, ${name}.`}
          sub="Here’s what your career profile is telling us right now."
        />

        <DashboardHero
          score={score}
          strong={strong}
          improve={improve}
          critical={critical}
          topGap={topGap}
          matches={matches}
          hello={hello}
          name={name}
        />

        <DashboardMetrics matches={matches} avg={avg} gaps={gaps} report={report} cv={cv} />

        {topGap && (
          <div className="card insight dashboard-insight">
            <div className="ai-line">
              <div className="spark">✦</div>
              <div>
                <div className="eyebrow">AI insight</div>
                <p>
                  <strong>Your biggest opportunity is {topGap.skill}.</strong>{' '}
                  {Number(topGap.demand_pct)
                    ? `It appears in ${Math.round(topGap.demand_pct)}% of the roles you’re targeting.`
                    : ''}{' '}
                  {topGap.reason ||
                    'Based on your current profile, this is a high-impact gap to close.'}{' '}
                  Closing it could lift match rate by roughly +{impact}%.
                </p>
                <button type="button" className="link" onClick={() => openSkill({ ...topGap, impact_pct: impact })}>
                  Show me why →
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="dashboard-focus">
          <DashboardFocusPanel
            title="Your skill profile"
            subtitle="vs. market demand"
            isEmpty={profileRows.length === 0}
            emptyMessage="No skill profile yet."
          >
            {profileRows.map((row) => (
              <SkillBar
                key={row.name}
                name={row.name}
                value={row.value}
                tone={row.tone}
                demand={row.demand}
              />
            ))}
          </DashboardFocusPanel>

          <DashboardFocusPanel
            title="Best opportunities"
            subtitle={`Top ${Math.min(3, matches.length)} of ${matches.length}`}
            isEmpty={matches.length === 0}
            emptyMessage="No matches yet — refresh analysis after jobs are indexed."
          >
            {matches.slice(0, 3).map((job, idx) => (
              <JobRow
                key={`${job.job_id || job.id || idx}-${job.title}`}
                company={job.company}
                title={job.title}
                meta={jobMeta(job)}
                matchPct={(job.score || 0) * 100}
                compact
              />
            ))}
            <div className="footerlink">
              <Link to="/jobs">View all matches →</Link>
            </div>
          </DashboardFocusPanel>
        </div>

        <div className="dashboard-bottom">
          <DashboardFocusPanel
            title="Priority skill gaps"
            subtitle={`${gaps.length} identified`}
            isEmpty={gaps.length === 0}
            emptyMessage="No material gaps detected."
          >
            {gaps.slice(0, 3).map((g) => {
              const p = String(g.priority || 'medium').toLowerCase()
              return (
                <button
                  type="button"
                  className="gap"
                  key={g.skill}
                  style={{ width: '100%', textAlign: 'left' }}
                  onClick={() => openSkill(g)}
                >
                  <i className="dot" style={{ background: p === 'high' ? 'var(--red)' : 'var(--amber)' }} />
                  <div>
                    <b>{displaySkillName(g.skill)}</b>
                    <small>
                      {g.demand_pct != null
                        ? `Required in ${Math.round(g.demand_pct)}% of target roles`
                        : g.reason || 'Identified from matched roles'}
                    </small>
                  </div>
                  <em className={`priority ${p === 'high' ? 'critical' : p === 'low' ? 'low' : 'medium'}`}>
                    {p === 'high' ? 'Critical' : p === 'low' ? 'Low' : 'Medium'}
                  </em>
                </button>
              )
            })}
            <div className="footerlink">
              <Link to="/skills">Explore skill gaps →</Link>
            </div>
          </DashboardFocusPanel>

          <div className="card next dashboard-next">
            <div className="nextnum">01</div>
            <div className="next-copy">
              <div className="eyebrow">Recommended next step</div>
              <h3>{topGap ? `Focus on ${topGap.skill}` : 'Refresh your profile'}</h3>
              <p>
                {topGap
                  ? `Apply it in one existing project this week to improve your match strength and visibility.`
                  : 'Keep your CV updated and re-run analysis after new experience.'}
              </p>
            </div>
            <Link className="arrow" to="/roadmap" aria-label="Open roadmap">
              Review roadmap →
            </Link>
          </div>
        </div>

        {insights.length > 0 && (
          <div className="card dashboard-block">
            <div className="cardtitle">
              Grounded insights <span>{insights.length} explained</span>
            </div>
            {insights.map((ins) => (
              <div className="ai-line" key={ins.skill} style={{ marginBottom: 16 }}>
                <div className="spark">✦</div>
                <div>
                  <div className="eyebrow">
                    {displaySkillName(ins.skill)} · {ins.priority || 'gap'}
                  </div>
                  <p style={{ margin: 0 }}>{ins.answer}</p>
                  {ins.sources.length > 0 && (
                    <div className="insight-sources">
                      {ins.sources.map((s) =>
                        s.url ? (
                          <a key={s.ref} href={s.url} target="_blank" rel="noreferrer">
                            {s.title || s.ref}
                          </a>
                        ) : (
                          <span key={s.ref} className="muted">
                            {s.title || s.ref}
                          </span>
                        ),
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}

        {sources.length > 0 && (
          <div className="card dashboard-block">
            <div className="cardtitle">
              Sources <span>{sources.length} references</span>
            </div>
            <ul className="source-list">
              {sources.map((s) => (
                <li key={s.ref}>
                  {s.url ? (
                    <a href={s.url} target="_blank" rel="noreferrer">
                      {s.title || s.ref}
                    </a>
                  ) : (
                    <span>{s.title || s.ref}</span>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </ViewShell>
  )
}

export default function DashboardPage() {
  return (
    <AnalysisGate title="Overview">
      <DashboardBody />
    </AnalysisGate>
  )
}
