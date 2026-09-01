/** Dual skill-vs-demand bar used on dashboard and skill gaps. */
export default function DualBar({ you = 0, demand = 0, label }) {
  const youPct = Math.max(0, Math.min(100, Number(you) || 0))
  const demandPct = Math.max(0, Math.min(100, Number(demand) || 0))
  return (
    <div className="dual-bar" role="img" aria-label={label || `You ${youPct}%, demand ${demandPct}%`}>
      <div className="dual-bar-row">
        <span className="dual-bar-label">You</span>
        <div className="dual-bar-track">
          <span className="dual-bar-fill dual-you" style={{ width: `${youPct}%` }} />
        </div>
        <span className="dual-bar-metric">{Math.round(youPct)}</span>
      </div>
      <div className="dual-bar-row">
        <span className="dual-bar-label">Demand</span>
        <div className="dual-bar-track">
          <span className="dual-bar-fill dual-demand" style={{ width: `${demandPct}%` }} />
        </div>
        <span className="dual-bar-metric">{Math.round(demandPct)}</span>
      </div>
    </div>
  )
}
