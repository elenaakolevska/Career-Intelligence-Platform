/** Score stamp — interview feedback / metric callouts. */
export default function Stamp({ value, label = 'Score', tone }) {
  const n = typeof value === 'number' ? value : null
  const resolved =
    tone ||
    (n == null ? 'neutral' : n >= 8 ? 'ok' : n >= 5 ? 'warn' : 'danger')
  return (
    <div className={`stamp tone-${resolved}`} aria-label={`${label} ${n ?? 'n/a'}`}>
      <span className="stamp-label">{label}</span>
      <strong className="stamp-value">{n == null ? '—' : n % 1 === 0 ? n : n.toFixed(1)}</strong>
    </div>
  )
}
