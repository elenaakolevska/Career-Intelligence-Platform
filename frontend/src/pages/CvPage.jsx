import { useCallback, useEffect, useRef, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { formatApiError } from '../api/client'
import { getCv, uploadCv } from '../api/cv'
import AnalysisGate from '../components/AnalysisGate'
import { PageHeader, ViewShell } from '../components/ui'
import { useToast } from '../components/ToastHost'
import { useAnalysis } from '../context/AnalysisContext'
import { useSession } from '../context/SessionContext'
import { buildProfileSummary, displaySkillName, extractIssues, extractSkills } from '../lib/analysisUi'

function ProfileSummaryView({ profile }) {
  if (profile.fallbackText) {
    return <p className="profile-summary-fallback">{profile.fallbackText}</p>
  }
  return <p className="profile-summary-lead">{profile.paragraph}</p>
}

function CvProfileBody() {
  const { cv, report, rerun, running } = useAnalysis()
  const { push } = useToast()
  const skills = extractSkills(cv, report)
  const issues = extractIssues(cv, report)
  const profile = buildProfileSummary(cv, report)

  return (
    <>
      <div className="grid2">
        <div className="card bigcard">
          <div className="cardtitle">
            Extracted skills <span>{skills.length} detected</span>
          </div>
          <div className="chips">
            {skills.length === 0 ? (
              <span className="muted">No skills extracted yet.</span>
            ) : (
              skills.map((s, i) => (
                <span key={s} className={`chip ${i > 5 ? 'indigo' : 'good'}`}>
                  {displaySkillName(s)}
                </span>
              ))
            )}
          </div>
          <div className="panelsection">
            <h4>ATS opportunities</h4>
            {issues.length === 0 ? (
              <p className="sub">No ATS issues flagged.</p>
            ) : (
              issues.slice(0, 6).map((issue) => (
                <div className="recommend" key={`${issue.code}-${issue.message}`}>
                  <i>!</i>
                  <span>{issue.message}</span>
                </div>
              ))
            )}
          </div>
        </div>
        <div className="card bigcard">
          <div className="cardtitle">
            AI profile summary <span>Generated from CV</span>
          </div>
          <ProfileSummaryView profile={profile} />
          <button
            type="button"
            className="btn primary"
            style={{ marginTop: 18 }}
            disabled={running}
            onClick={() => {
              rerun()
              push('Optimizing profile — re-running analysis…')
            }}
          >
            Optimize CV with AI ✦
          </button>
        </div>
      </div>
    </>
  )
}

function CvUploadPanel({ onUploaded }) {
  const { userId, setActiveCv, setCvStatus, bootstrapping } = useSession()
  const { push } = useToast()
  const location = useLocation()
  const [file, setFile] = useState(location.state?.file || null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [dragOver, setDragOver] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    if (location.state?.file) setFile(location.state.file)
  }, [location.state])

  const submit = useCallback(
    async (nextFile) => {
      const f = nextFile || file
      if (!f) {
        setError('Choose a PDF file to upload')
        return
      }
      if (!userId) {
        setError('Sign in to upload a CV.')
        return
      }
      setBusy(true)
      setError(null)
      try {
        push('CV uploaded — analysis starting')
        const uploaded = await uploadCv({ file: f })
        setActiveCv({ id: uploaded.id, status: uploaded.status })
        setCvStatus(uploaded.status)
        if (uploaded.status === 'completed') {
          const cv = await getCv(uploaded.id)
          setActiveCv(cv)
          onUploaded?.(cv)
        } else {
          // poll briefly
          const cv = await getCv(uploaded.id)
          setActiveCv(cv)
          onUploaded?.(cv)
        }
      } catch (err) {
        setError(formatApiError(err, 'Upload failed'))
      } finally {
        setBusy(false)
      }
    },
    [file, userId, setActiveCv, setCvStatus, onUploaded, push],
  )

  return (
    <div className="card bigcard" style={{ marginBottom: 16 }}>
      <div className="cardtitle">
        Upload a new CV <span>PDF</span>
      </div>
      {error && (
        <div className="callout is-error" role="alert">
          {error}
        </div>
      )}
      <label
        className={['upload-drop', dragOver ? 'is-drag' : ''].filter(Boolean).join(' ')}
        onDragOver={(e) => {
          e.preventDefault()
          setDragOver(true)
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragOver(false)
          const next = e.dataTransfer.files?.[0]
          if (next) setFile(next)
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept="application/pdf,.pdf"
          disabled={busy || bootstrapping}
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        <strong>{file ? file.name : 'Drop PDF here or browse'}</strong>
        <span className="muted" style={{ fontSize: 11 }}>
          {file ? `${Math.max(1, Math.round(file.size / 1024))} KB` : 'application/pdf'}
        </span>
      </label>
      <button
        type="button"
        className="btn primary"
        disabled={busy || !file || !userId}
        onClick={() => submit()}
      >
        {busy ? 'Processing…' : 'Upload and analyze'}
      </button>
    </div>
  )
}

export default function CvPage() {
  const { hasCompletedCv } = useSession()
  const navigate = useNavigate()

  return (
    <ViewShell>
      <PageHeader
        eyebrow="CV intelligence"
        title="Your profile, understood."
        sub="AI-extracted skills, experience signals and optimization opportunities."
      />
      <CvUploadPanel
        onUploaded={() => {
          navigate('/dashboard')
        }}
      />
      {hasCompletedCv ? (
        <AnalysisGate title="My CV">
          <CvProfileBody />
        </AnalysisGate>
      ) : (
        <div className="card empty-state">
          Upload a completed CV to see extracted skills, ATS opportunities, and your AI profile summary.
        </div>
      )}
    </ViewShell>
  )
}
