import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { formatApiError } from '../api/client'
import { getCv, uploadCv } from '../api/cv'
import { useSession } from '../context/SessionContext'

const STATUS_COPY = {
  idle: { label: 'Ready', hint: 'Choose a PDF resume to begin.' },
  pending: { label: 'Pending', hint: 'Upload queued…' },
  processing: { label: 'Processing', hint: 'Extracting text and structuring your CV…' },
  completed: { label: 'Completed', hint: 'CV ready — opening dashboard…' },
  failed: { label: 'Failed', hint: 'Processing did not finish successfully.' },
}

const TERMINAL = new Set(['completed', 'failed'])

export default function CVUploadPage() {
  const { userId, setActiveCv, setCvStatus, bootstrapping, sessionError } = useSession()
  const navigate = useNavigate()
  const location = useLocation()
  const [file, setFile] = useState(null)
  const [status, setStatus] = useState('idle')
  const [cvId, setCvId] = useState(null)
  const [error, setError] = useState(null)
  const [duplicate, setDuplicate] = useState(false)
  const [dragOver, setDragOver] = useState(false)
  const pollRef = useRef(null)
  const fileInputRef = useRef(null)

  const clearPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  useEffect(() => () => clearPoll(), [clearPoll])

  const finishCompleted = useCallback(
    (cv) => {
      clearPoll()
      setStatus('completed')
      setCvStatus('completed')
      setActiveCv(cv)
      setTimeout(() => navigate('/dashboard', { replace: true }), 600)
    },
    [clearPoll, navigate, setActiveCv, setCvStatus],
  )

  const finishFailed = useCallback(
    (message, cv = null) => {
      clearPoll()
      setStatus('failed')
      setError(message || 'CV processing failed')
      if (cv) {
        setActiveCv(cv)
        setCvStatus('failed')
      }
    },
    [clearPoll, setActiveCv, setCvStatus],
  )

  const startPolling = useCallback(
    (id) => {
      clearPoll()
      const tick = async () => {
        try {
          const cv = await getCv(id)
          setStatus(cv.status || 'processing')
          setCvStatus(cv.status)
          setActiveCv(cv)
          if (cv.status === 'completed') {
            finishCompleted(cv)
          } else if (cv.status === 'failed') {
            finishFailed(cv.error_message || 'CV processing failed', cv)
          }
        } catch (err) {
          finishFailed(formatApiError(err, 'Could not refresh CV status'))
        }
      }
      tick()
      pollRef.current = setInterval(tick, 1200)
    },
    [clearPoll, finishCompleted, finishFailed, setActiveCv, setCvStatus],
  )

  const onFileChange = (e) => {
    const next = e.target.files?.[0] || null
    setError(null)
    setDuplicate(false)
    if (!next) {
      setFile(null)
      return
    }
    if (next.type !== 'application/pdf' && !next.name.toLowerCase().endsWith('.pdf')) {
      setFile(null)
      setError('Only PDF files are accepted')
      if (fileInputRef.current) fileInputRef.current.value = ''
      return
    }
    setFile(next)
    if (status !== 'processing' && status !== 'pending') {
      setStatus('idle')
    }
  }

  const onSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setDuplicate(false)

    if (!userId) {
      setError('Sign in to upload a CV.')
      return
    }
    if (!file) {
      setError('Choose a PDF file to upload')
      return
    }

    setStatus('pending')
    setCvId(null)

    try {
      setStatus('processing')
      const uploaded = await uploadCv({ file })
      setCvId(uploaded.id)
      setDuplicate(Boolean(uploaded.duplicate))
      setActiveCv({ id: uploaded.id, status: uploaded.status })
      setCvStatus(uploaded.status)

      if (uploaded.status === 'completed') {
        // Still poll once so dashboard gets full CV payload in session if needed
        const cv = await getCv(uploaded.id)
        finishCompleted(cv)
        return
      }
      if (uploaded.status === 'failed') {
        const cv = await getCv(uploaded.id).catch(() => null)
        finishFailed(cv?.error_message || 'CV processing failed', cv)
        return
      }
      // pending / processing — poll until terminal
      startPolling(uploaded.id)
    } catch (err) {
      finishFailed(formatApiError(err, 'Upload failed'))
    }
  }

  const guardReason = location.state?.guardReason
  const copy = STATUS_COPY[status] || STATUS_COPY.idle
  const busy = status === 'pending' || status === 'processing' || bootstrapping

  return (
    <section className="dash-modern">
      <header className="page-toolbar">
        <div>
          <p className="eyebrow">CV intake</p>
          <h1>Upload your CV</h1>
          <p className="dash-sub">
            Drop a PDF resume. We extract text, structure the profile, and score ATS readiness.
          </p>
        </div>
      </header>

      {guardReason === 'no-cv' && (
        <div className="callout" role="status">
          Upload a completed CV before opening dashboard, skills, roadmap, or interview.
        </div>
      )}

      {sessionError && (
        <div className="callout is-error" role="alert">
          {sessionError}
        </div>
      )}

      <div className="ui-card upload-card">
        <form className="upload-form" onSubmit={onSubmit}>
          <label
            className={['file-drop', dragOver ? 'is-drag' : '', file ? 'has-file' : ''].filter(Boolean).join(' ')}
            onDragOver={(e) => {
              e.preventDefault()
              setDragOver(true)
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault()
              setDragOver(false)
              const next = e.dataTransfer.files?.[0]
              if (next) {
                setFile(next)
                setError(null)
                if (status !== 'processing' && status !== 'pending') setStatus('idle')
              }
            }}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept="application/pdf,.pdf"
              onChange={onFileChange}
              disabled={busy}
            />
            <span className="file-drop-title">{file ? file.name : 'Drop PDF here or browse'}</span>
            <span className="file-drop-hint">
              {file ? `${Math.max(1, Math.round(file.size / 1024))} KB` : 'application/pdf · max size enforced by API'}
            </span>
          </label>

          <button type="submit" className="btn btn-primary" disabled={busy || !file || !userId}>
            {busy ? 'Working…' : 'Upload and process'}
          </button>
        </form>

        <div
          className={['status-panel', `is-${status}`, TERMINAL.has(status) ? 'is-terminal' : '']
            .filter(Boolean)
            .join(' ')}
          role="status"
          aria-live="polite"
        >
          <p className="status-label">{copy.label}</p>
          <p>{copy.hint}</p>
          {cvId && <p className="status-meta">CV id #{cvId}{duplicate ? ' · existing file reused' : ''}</p>}
          {error && (
            <p className="status-error" role="alert">
              {error}
            </p>
          )}
        </div>
      </div>
    </section>
  )
}
