import AnalysisGate from '../components/AnalysisGate'
import { JobRow, PageHeader, ViewShell } from '../components/ui'
import { useToast } from '../components/ToastHost'
import { useAnalysis } from '../context/AnalysisContext'
import { extractMatches, jobMeta, timeAgo } from '../lib/analysisUi'

function JobsBody() {
  const { report, analysis, rerun, running } = useAnalysis()
  const { push } = useToast()
  const matches = extractMatches(report)

  return (
    <ViewShell>
      <PageHeader
        eyebrow="Market matching"
        title="Roles worth your attention."
        sub={`${matches.length} jobs ranked by semantic fit, skills and career direction.`}
        actions={
          <button
            type="button"
            className="btn primary"
            disabled={running}
            onClick={() => {
              rerun()
              push('Refreshing matches…')
            }}
          >
            Refresh matches
          </button>
        }
      />

      <div className="card">
        <div className="cardtitle">
          Top matches <span>Updated {timeAgo(analysis?.created_at)}</span>
        </div>
        {matches.length === 0 ? (
          <p className="empty-state">No matches yet. Refresh analysis after jobs are indexed.</p>
        ) : (
          matches.map((job, idx) => (
            <JobRow
              key={`${job.job_id || job.id || idx}-${job.title}`}
              company={job.company}
              title={job.title}
              meta={jobMeta(job)}
              matchPct={(job.score || 0) * 100}
              onView={() => {
                if (job.url) window.open(job.url, '_blank', 'noreferrer')
                else push('No posting URL for this match')
              }}
            />
          ))
        )}
      </div>
    </ViewShell>
  )
}

export default function JobsPage() {
  return (
    <AnalysisGate title="Job Matches">
      <JobsBody />
    </AnalysisGate>
  )
}
