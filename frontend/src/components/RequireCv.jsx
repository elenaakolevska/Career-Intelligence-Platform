import { Navigate, useLocation } from 'react-router-dom'
import { useSession } from '../context/SessionContext'

export default function RequireCv({ children }) {
  const { hasCompletedCv, bootstrapping } = useSession()
  const location = useLocation()

  if (bootstrapping) {
    return (
      <div className="card" role="status">
        <div className="eyebrow">Loading</div>
        <p className="sub">Checking your CV…</p>
      </div>
    )
  }

  if (!hasCompletedCv) {
    return <Navigate to="/cv" replace state={{ from: location, guardReason: 'no-cv' }} />
  }

  return children
}
