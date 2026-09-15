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

  if (Array.isArray(profile.bullets) && profile.bullets.length > 0) {
    return (
      <ul className="profile-summary-list">
        {profile.bullets.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    )
  }

  return <p className="profile-summary-lead">{profile.paragraph}</p>
}

function SkillGroup({ title, items, tone = 'good' }) {
  return (
    <div className="cv-skill-group">
      <div className="cv-group-header">
        <span className="cv-group-label">{title}</span>
      </div>
      <div className="cv-skill-pills">
        {items.length === 0 ? (
          <span className="muted">No skills detected.</span>
        ) : (
          items.map((s) => (
            <span key={s} className={`cv-skill-pill ${tone}`}>
              {displaySkillName(s)}
            </span>
          ))
        )}
      </div>
    </div>
  )
}

function CvProfileBody({ onOpenOverview }) {
  const { cv, report, rerun, running } = useAnalysis()
  const { push } = useToast()
  const skills = extractSkills(cv, report)
  const issues = extractIssues(cv, report)
  const profile = buildProfileSummary(cv, report)

  const groups = skills.length
    ? [
        { title: 'Core strengths', items: skills.slice(0, 4), tone: 'good' },
        { title: 'Technical foundation', items: skills.slice(4, 8), tone: 'indigo' },
      ]
    : []

  const orderedIssues = issues.slice(0, 6)
  const critical = orderedIssues.filter((issue) => /phone|name|experience|measurable|achievement|length|summary|email/i.test(issue.message || ''))
  const minor = orderedIssues.filter((issue) => !/phone|name|experience|measurable|achievement|length|summary|email/i.test(issue.message || ''))

  return (
    <div className="cv-page-section">
      <div className="cv-grid cv-grid-main">
        <section className="card cv-panel">
          <div className="cardtitle">
            Extracted profile <span>{skills.length} skills detected</span>
          </div>

          <div className="cv-skill-list">
            {groups.length === 0 ? (
              <p className="empty-state">No skills detected in the uploaded CV yet.</p>
            ) : (
              groups.map((group) => (
                <SkillGroup key={group.title} title={group.title} items={group.items} tone={group.tone} />
              ))
            )}
          </div>

          <div className="cv-section-divider" />

          <div className="cv-section-header">
            <h4>ATS insights</h4>
            <span>{orderedIssues.length} findings</span>
          </div>

          <div className="cv-ats-groups">
            {orderedIssues.length === 0 ? (
              <p className="sub">No ATS issues flagged.</p>
            ) : (
              <>
                {critical.length > 0 && (
                  <div className="cv-ats-group">
                    <div className="cv-ats-group-title">Key opportunities</div>
                    {critical.map((issue) => (
                      <div className="recommend" key={`${issue.code}-${issue.message}`}>
                        <i>!</i>
                        <span>{issue.message}</span>
                      </div>
                    ))}
                  </div>
                )}
                {minor.length > 0 && (
                  <div className="cv-ats-group">
                    <div className="cv-ats-group-title">Nice-to-improve</div>
                    {minor.map((issue) => (
                      <div className="recommend" key={`${issue.code}-${issue.message}`}>
                        <i>•</i>
                        <span>{issue.message}</span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>
        </section>

        <section className="card cv-panel cv-summary-panel">
          <div className="cardtitle">
            AI career summary <span>Generated from CV</span>
          </div>
          <div className="cv-summary-block">
            <ProfileSummaryView profile={profile} />
          </div>

          <button type="button" className="btn primary cv-overview-button" onClick={onOpenOverview}>
            Open overview →
          </button>
        </section>
      </div>
    </div>
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
    <div className="cv-upload-shell">
      <div className="card cv-upload-panel">
        <div className="cv-upload-header">
          <div>
            <div className="eyebrow">Upload CV</div>
            <h2>Bring in your latest profile</h2>
          </div>
          <span className="cv-upload-tag">PDF</span>
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
          <div className="cv-upload-drop-inner">
            <div className="cv-upload-icon">⇪</div>
            <div className="cv-upload-copy">
              <strong>{file ? file.name : 'Drop your CV here or browse'}</strong>
              <span className="muted">
                {file ? `${Math.max(1, Math.round(file.size / 1024))} KB` : 'Accepted format: PDF only'}
              </span>
            </div>
          </div>
        </label>

        <div className="cv-upload-meta">
          <span>Supported: PDF</span>
          <span>Analysis starts immediately after upload</span>
        </div>

        <button
          type="button"
          className="btn primary cv-upload-button"
          disabled={busy || !file || !userId}
          onClick={() => submit()}
        >
          {busy ? 'Processing…' : 'Upload and analyze'}
        </button>
      </div>
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

      <div className="cv-page-shell">
        <CvUploadPanel />

        {hasCompletedCv ? (
          <AnalysisGate title="My CV">
            <CvProfileBody onOpenOverview={() => navigate('/dashboard')} />
          </AnalysisGate>
        ) : (
          <div className="card empty-state cv-empty-state">
            Upload a completed CV to see extracted skills, ATS opportunities, and your AI profile summary.
          </div>
        )}
      </div>
    </ViewShell>
  )
}
