import { useMemo, useState } from 'react'
import AnalysisGate from '../components/AnalysisGate'
import { PageHeader, SkillBar, ViewShell } from '../components/ui'
import { useSkillDrawer } from '../context/SkillDrawerContext'
import { useAnalysis } from '../context/AnalysisContext'
import { useRoadmapExtras } from '../context/RoadmapExtrasContext'
import { displaySkillName, extractGaps, fillToneForDemand } from '../lib/analysisUi'

function SkillGapsBody() {
  const { report } = useAnalysis()
  const { openSkill } = useSkillDrawer()
  const { addSkillToRoadmap } = useRoadmapExtras()
  const gaps = extractGaps(report)
  const available = report?.skill_gaps?.available
  const [filter, setFilter] = useState('all')

  const filtered = useMemo(() => {
    if (filter === 'all') return gaps
    if (filter === 'critical') return gaps.filter((g) => String(g.priority).toLowerCase() === 'high')
    return gaps.filter((g) => String(g.priority).toLowerCase() === 'medium')
  }, [gaps, filter])

  const focus = filtered[0] || gaps[0]
  const impact = focus ? Math.max(6, Math.round((Number(focus.demand_pct) || 40) / 7)) : 11

  return (
    <ViewShell>
      <PageHeader
        eyebrow="Skill gap analysis"
        title="Close the gaps that matter."
        sub="Ranked by market demand and potential impact on your match rate."
      />

      <div className="tabs" role="tablist">
        {[
          { id: 'all', label: 'All gaps' },
          { id: 'critical', label: 'Critical' },
          { id: 'medium', label: 'Medium' },
        ].map((t) => (
          <button
            key={t.id}
            type="button"
            className={filter === t.id ? 'active' : ''}
            onClick={() => setFilter(t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {!available ? (
        <div className="card empty-state">Skill gap section was not produced by the analysis run.</div>
      ) : (
        <div className="sectiongrid">
          <div className="card bigcard">
            <div className="cardtitle">
              Missing skills <span>{filtered.length} detected</span>
            </div>
            {filtered.length === 0 ? (
              <p className="empty-state">No gaps in this filter.</p>
            ) : (
              filtered.map((g) => {
                const demand = Number(g.demand_pct) || 0
                const p = String(g.priority || 'medium').toLowerCase()
                const tag =
                  p === 'high' ? (
                    <span className="tag high">HIGH IMPACT</span>
                  ) : p === 'low' ? (
                    <span className="tag low">NICE TO HAVE</span>
                  ) : (
                    <span className="tag med">MEDIUM</span>
                  )
                return (
                  <button
                    type="button"
                    key={g.skill}
                    style={{ display: 'block', width: '100%', textAlign: 'left' }}
                    onClick={() => openSkill({ ...g, impact_pct: Math.max(6, Math.round(demand / 7)) })}
                  >
                    <SkillBar
                      large
                      name={
                        <>
                          {displaySkillName(g.skill)} {tag}
                        </>
                      }
                      value={demand || 40}
                      tone={fillToneForDemand(demand, p)}
                      suffix={`${Math.round(demand || 0)}% demand`}
                    />
                  </button>
                )
              })
            )}
          </div>

          <div className="card bigcard">
            <div className="cardtitle">
              Why {displaySkillName(focus?.skill) || 'this skill'} first <span>AI recommendation</span>
            </div>
            {focus ? (
              <>
                <div className="impact">
                  <div>
                    <b>+{impact}%</b>
                    <span>potential match-rate improvement</span>
                  </div>
                  <div style={{ fontSize: 20 }}>↗</div>
                </div>
                <div className="panelsection">
                  <h4>What we found</h4>
                  <p className="sub" style={{ lineHeight: 1.7 }}>
                    {focus.reason ||
                      `${displaySkillName(focus.skill)} appears repeatedly across roles you already match. Closing this gap is a high-signal next step.`}
                  </p>
                </div>
                <div className="panelsection">
                  <h4>Recommended actions</h4>
                  <div className="recommend">
                    <i>01</i>
                    <span>
                      Study {displaySkillName(focus.skill)} fundamentals with a hands-on project.
                    </span>
                  </div>
                  <div className="recommend">
                    <i>02</i>
                    <span>Apply it in one existing portfolio piece and document it.</span>
                  </div>
                  <div className="recommend">
                    <i>03</i>
                    <span>Re-run analysis and compare match-rate lift.</span>
                  </div>
                </div>
                <button
                  type="button"
                  className="btn primary"
                  style={{ marginTop: 12 }}
                  onClick={() => addSkillToRoadmap(focus)}
                >
                  Add to roadmap →
                </button>
              </>
            ) : (
              <p className="empty-state">No gap selected.</p>
            )}
          </div>
        </div>
      )}
    </ViewShell>
  )
}

export default function SkillGapsPage() {
  return (
    <AnalysisGate title="Skill Gap">
      <SkillGapsBody />
    </AnalysisGate>
  )
}
