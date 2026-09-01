import { useAnalysis } from '../context/AnalysisContext'

export default function AnalysisGate({ children, title = 'Analysis' }) {
  const { loading, running, error, report, rerun } = useAnalysis()

  if (loading || running) {
    return (
      <div className="view-enter" role="status" aria-live="polite">
        <div className="eyebrow">{running ? 'Running analysis' : 'Loading'}</div>
        <h1 style={{ marginBottom: 16 }}>{title}</h1>
        <div className="card">
          <p className="sub">
            {running
              ? 'Matching jobs, detecting skill gaps, and building your roadmap…'
              : `Loading ${title.toLowerCase()}…`}
          </p>
          <div className="track" style={{ height: 8, marginTop: 14 }}>
            <div className="fill green" style={{ width: running ? '68%' : '35%' }} />
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
        <div className="card">
          <div className="eyebrow">No analysis yet</div>
          <h2 style={{ font: '700 18px var(--font-display)', margin: '6px 0 8px' }}>{title}</h2>
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
