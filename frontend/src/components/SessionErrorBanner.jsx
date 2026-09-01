import { formatApiError } from '../api/client'
import { useSession } from '../context/SessionContext'

/** Surfaces centralized session/network errors in the shell (P8-07). */
export default function SessionErrorBanner() {
  const { sessionError } = useSession()
  if (!sessionError) return null
  return (
    <div className="shell-error" role="alert">
      {formatApiError(sessionError, 'Session error')}
    </div>
  )
}
