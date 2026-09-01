import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import { ApiError, formatApiError } from '../api/client'
import { getLatestAnalysis, runAnalysis, seedMockJobs } from '../api/analysis'
import { getCv } from '../api/cv'
import { useSession } from './SessionContext'

const AnalysisContext = createContext(null)

export function AnalysisProvider({ children }) {
  const { cvId, hasCompletedCv } = useSession()
  const [cv, setCv] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)

  const report = analysis?.final_report || null

  const loadCv = useCallback(async (id) => {
    if (!id) {
      setCv(null)
      return null
    }
    const data = await getCv(id)
    setCv(data)
    return data
  }, [])

  const refreshLatest = useCallback(async (id) => {
    if (!id) {
      setAnalysis(null)
      return null
    }
    try {
      const latest = await getLatestAnalysis(id)
      setAnalysis(latest)
      setError(null)
      return latest
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setAnalysis(null)
        return null
      }
      throw err
    }
  }, [])

  const ensureAnalysis = useCallback(
    async ({ force = false } = {}) => {
      if (!cvId || !hasCompletedCv) return null
      setLoading(true)
      setError(null)
      try {
        await loadCv(cvId)
        if (!force) {
          const existing = await refreshLatest(cvId)
          if (existing?.final_report) {
            return existing
          }
        }
        setRunning(true)
        // Ensure a job corpus exists for matching (idempotent seed)
        try {
          await seedMockJobs()
        } catch {
          // Non-fatal if jobs already present / endpoint busy
        }
        const result = await runAnalysis(cvId)
        setAnalysis(result)
        return result
      } catch (err) {
        const message = formatApiError(err, 'Analysis failed')
        setError(message)
        throw err
      } finally {
        setRunning(false)
        setLoading(false)
      }
    },
    [cvId, hasCompletedCv, loadCv, refreshLatest],
  )

  useEffect(() => {
    if (!hasCompletedCv || !cvId) {
      setCv(null)
      setAnalysis(null)
      setError(null)
      return
    }
    let cancelled = false
    ;(async () => {
      setLoading(true)
      setError(null)
      try {
        await loadCv(cvId)
        if (cancelled) return
        const existing = await refreshLatest(cvId)
        if (cancelled) return
        if (!existing?.final_report) {
          setRunning(true)
          try {
            await seedMockJobs()
          } catch {
            /* ignore */
          }
          if (cancelled) return
          const result = await runAnalysis(cvId)
          if (!cancelled) setAnalysis(result)
        }
      } catch (err) {
        if (!cancelled) {
          setError(formatApiError(err, 'Could not load analysis'))
        }
      } finally {
        if (!cancelled) {
          setRunning(false)
          setLoading(false)
        }
      }
    })()
    return () => {
      cancelled = true
    }
  }, [cvId, hasCompletedCv, loadCv, refreshLatest])

  const value = useMemo(
    () => ({
      cv,
      analysis,
      report,
      loading,
      running,
      error,
      ensureAnalysis,
      refreshLatest: () => refreshLatest(cvId),
      rerun: () => ensureAnalysis({ force: true }),
    }),
    [cv, analysis, report, loading, running, error, ensureAnalysis, refreshLatest, cvId],
  )

  return <AnalysisContext.Provider value={value}>{children}</AnalysisContext.Provider>
}

export function useAnalysis() {
  const ctx = useContext(AnalysisContext)
  if (!ctx) throw new Error('useAnalysis must be used within AnalysisProvider')
  return ctx
}
