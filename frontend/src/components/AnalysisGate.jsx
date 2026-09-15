import { useAnalysis } from '../context/AnalysisContext'

export default function AnalysisGate({ children, title = 'Analysis' }) {
  const { loading, running, error, report, rerun } = useAnalysis()

  if (loading || running) {
    return (
      <div className="view-enter" role="status" aria-live="polite">
        <div className="analysis-state-shell">
          <div className="analysis-state-header">
            <div className="eyebrow">{running ? 'Running analysis' : 'Loading'}</div>
            <h1>{title}</h1>
          </div>

          <div className="card analysis-state-card">
            <div className="analysis-state-copy">
              <div className="analysis-pulse" aria-hidden="true" />
              <div>
                <p className="analysis-state-label">
                  {running
                    ? 'Analyzing profile and extracting key insights…'
                    : `Loading ${title.toLowerCase()}…`}
                </p>
                <div className="analysis-steps">
                  <span>Profile overview</span>
                  <span>Skills</span>
                  <span>ATS review</span>
                </div>
              </div>
            </div>
            <div className="track analysis-track" aria-hidden="true">
              <div className="fill green" style={{ width: running ? '68%' : '35%' }} />
            </div>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="view-enter">
        <div className="card callout is-error" role="alert">
          <strong>Analysis error</strong>
          <p style={{ marginTop: 6 }}>{error}</p>
          <button type="button" className="btn primary" style={{ marginTop: 12 }} onClick={() => rerun()}>
            Retry analysis
          </button>
        </div>
      </div>
    )
  }

  if (!report) {
    return (
      <div className="view-enter">
        <div className="card analysis-state-card analysis-empty-card">
          <div className="eyebrow">No analysis yet</div>
          <h2>{title}</h2>
          <p className="sub">Run the career analysis pipeline to populate this page.</p>
          <button type="button" className="btn primary" style={{ marginTop: 14 }} onClick={() => rerun()}>
            Run analysis
          </button>
        </div>
      </div>
    )
  }

  return children
}
