import { Navigate } from 'react-router-dom'
import { useSession } from '../context/SessionContext'

export default function HomePage() {
  const { hasCompletedCv, bootstrapping } = useSession()

  if (bootstrapping) {
    return (
      <div className="card" role="status">
        <div className="eyebrow">Loading</div>
        <p className="sub">Preparing your workspace…</p>
      </div>
    )
  }

  return <Navigate to={hasCompletedCv ? '/dashboard' : '/cv'} replace />
}
