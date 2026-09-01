import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { ApiError, formatApiError } from '../api/client'
import { getCv, listMyCvs } from '../api/cv'
import { useAuth } from './AuthContext'

const STORAGE_KEY = 'skillbridge.session.v1'

const SessionContext = createContext(null)

function readStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    return JSON.parse(raw)
  } catch {
    return {}
  }
}

function writeStored(next) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
}

export function SessionProvider({ children }) {
  const { isAuthenticated, userId, userEmail, loading: authLoading } = useAuth()
  const stored = readStored()
  const [cvId, setCvId] = useState(() => stored.cvId ?? null)
  const [cvStatus, setCvStatus] = useState(() => stored.cvStatus ?? null)
  const [bootstrapping, setBootstrapping] = useState(true)
  const [sessionError, setSessionError] = useState(null)

  useEffect(() => {
    writeStored({ userId, cvId, cvStatus })
  }, [userId, cvId, cvStatus])

  useEffect(() => {
    if (authLoading) return undefined
    let cancelled = false

    async function bootstrap() {
      setBootstrapping(true)
      setSessionError(null)

      if (!isAuthenticated) {
        setCvId(null)
        setCvStatus(null)
        if (!cancelled) setBootstrapping(false)
        return
      }

      try {
        let nextCvId = cvId
        let nextStatus = cvStatus

        if (nextCvId) {
          try {
            const cv = await getCv(nextCvId)
            if (cancelled) return
            nextStatus = cv.status
            setCvStatus(cv.status)
          } catch (err) {
            if (err instanceof ApiError && (err.status === 404 || err.status === 403)) {
              nextCvId = null
              nextStatus = null
              setCvId(null)
              setCvStatus(null)
            } else {
              throw err
            }
          }
        }

        if (!nextCvId) {
          const cvs = await listMyCvs()
          if (cancelled) return
          const completed = (cvs || []).find((c) => c.status === 'completed') || (cvs || [])[0]
          if (completed) {
            setCvId(completed.id)
            setCvStatus(completed.status)
          }
        } else if (nextStatus) {
          setCvStatus(nextStatus)
        }
      } catch (err) {
        if (!cancelled) {
          setSessionError(formatApiError(err, 'Failed to load your CVs'))
        }
      } finally {
        if (!cancelled) setBootstrapping(false)
      }
    }

    bootstrap()
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, authLoading, userId])

  const setActiveCv = useCallback((cv) => {
    if (!cv) {
      setCvId(null)
      setCvStatus(null)
      return
    }
    setCvId(cv.id)
    setCvStatus(cv.status)
  }, [])

  const clearCv = useCallback(() => {
    setCvId(null)
    setCvStatus(null)
  }, [])

  const hasCompletedCv = Boolean(cvId && cvStatus === 'completed')

  const value = useMemo(
    () => ({
      userId,
      userEmail,
      cvId,
      cvStatus,
      hasCompletedCv,
      bootstrapping: authLoading || bootstrapping,
      sessionError,
      setActiveCv,
      clearCv,
      setCvStatus,
    }),
    [
      userId,
      userEmail,
      cvId,
      cvStatus,
      hasCompletedCv,
      authLoading,
      bootstrapping,
      sessionError,
      setActiveCv,
      clearCv,
    ],
  )

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>
}

export function useSession() {
  const ctx = useContext(SessionContext)
  if (!ctx) throw new Error('useSession must be used within SessionProvider')
  return ctx
}
