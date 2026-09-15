import { useEffect, useMemo, useRef, useState } from 'react'
import {
  abandonInterview,
  completeInterview,
  formatApiError,
  getInterviewHistory,
  listUserInterviews,
  resumeInterview,
  startInterview,
} from '../api'
import { MetricCard, PageHeader, ViewShell } from '../components/ui'
import ConfirmDialog from '../components/ConfirmDialog'
import { useToast } from '../components/ToastHost'
import { useSession } from '../context/SessionContext'
import { useInterviewSocket } from '../hooks/useInterviewSocket'

const ACTIVE_KEY = 'skillbridge.activeInterviewSession'
const ROLE_SUGGESTIONS = [
  'Java Developer',
  'Frontend Developer',
  'Backend Developer',
  'Full Stack Developer',
  'Data Scientist',
  'DevOps Engineer',
  'QA Engineer',
  'Product Manager',
  'Machine Learning Engineer',
  'Mobile Developer',
]
const LEVELS = ['junior', 'mid', 'senior']

function ChatMsg({ event }) {
  if (event.kind === 'system') {
    return <div className="chat-notice">{event.text}</div>
  }
  if (event.kind === 'question') {
    return (
      <div className="msg question">
        <div className="msg-eyebrow">
          Question{event.turnIndex != null ? ` ${Number(event.turnIndex) + 1}` : ''}
        </div>
        <div className="msg-body">{event.text}</div>
        {event.topics?.length > 0 && (
          <div className="msg-topics">
            {event.topics.map((t) => (
              <span key={t} className="msg-topic">
                {t}
              </span>
            ))}
          </div>
        )}
      </div>
    )
  }
  if (event.kind === 'answer') {
    return <div className="msg user">{event.text}</div>
  }
  if (event.kind === 'feedback') {
    return (
      <div className="msg feedback">
        <div className="msg-eyebrow">
          Feedback{event.score != null ? ` · ${event.score}/10` : ''}
        </div>
        <div className="msg-body">{event.text}</div>
        {event.runningScore != null && (
          <div className="msg-meta">Running average: {event.runningScore}/10</div>
        )}
      </div>
    )
  }
  if (event.kind === 'error') {
    return <div className="chat-notice is-error">{event.text}</div>
  }
  return null
}

function isBusyNotice(text) {
  return /generat|evaluat|working|connected to interview|session state refreshed|on the way/i.test(
    String(text || ''),
  )
}

export default function InterviewPage() {
  const { userId, cvId } = useSession()
  const { push } = useToast()
  const [tab, setTab] = useState('live')
  const [role, setRole] = useState('')
  const [difficulty, setDifficulty] = useState('junior')
  const [sessionId, setSessionId] = useState(() => {
    try {
      const raw = localStorage.getItem(ACTIVE_KEY)
      return raw ? Number(raw) : null
    } catch {
      return null
    }
  })
  const [answer, setAnswer] = useState('')
  const [busy, setBusy] = useState(false)
  const [confirmAction, setConfirmAction] = useState(null)
  const [setupError, setSetupError] = useState(null)
  const [history, setHistory] = useState([])
  const bottomRef = useRef(null)
  const nearBottomRef = useRef(true)
  const requestingNext = useRef(false)
  const questionCountSeen = useRef(0)

  const {
    connection,
    lastError,
    session,
    events,
    send,
    connect,
    clearError,
    setEvents,
    resetTranscript,
  } = useInterviewSocket(sessionId)

  useEffect(() => {
    if (sessionId) localStorage.setItem(ACTIVE_KEY, String(sessionId))
    else localStorage.removeItem(ACTIVE_KEY)
  }, [sessionId])

  useEffect(() => {
    const track = () => {
      const el = bottomRef.current
      if (!el) return
      nearBottomRef.current = el.getBoundingClientRect().top < window.innerHeight + 80
    }
    window.addEventListener('scroll', track, { passive: true })
    window.addEventListener('resize', track, { passive: true })
    return () => {
      window.removeEventListener('scroll', track)
      window.removeEventListener('resize', track)
    }
  }, [])

  useEffect(() => {
    if (session?.status === 'completed' || session?.status === 'abandoned') return
    if (!nearBottomRef.current) return
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events, session?.status])

  // Only clear the in-flight flag when a *new* question arrives (not on status spam).
  useEffect(() => {
    const qCount = events.filter((e) => e.kind === 'question').length
    if (qCount > questionCountSeen.current) {
      questionCountSeen.current = qCount
      requestingNext.current = false
    }
    if (events.some((e) => e.kind === 'error')) {
      requestingNext.current = false
    }
  }, [events])

  // Reconnect safety: if the socket dropped after sending `next_question` but
  // before the question arrived, the in-flight flag would otherwise stay true
  // and the auto-request loop would never recover. Clearing it on (re)open lets
  // the auto-request effect re-evaluate against the re-hydrated transcript.
  useEffect(() => {
    if (connection === 'open') requestingNext.current = false
  }, [connection])

  // Auto-ask first question, then the next after each feedback — the session only
  // ends when the user completes or abandons it.
  useEffect(() => {
    if (!sessionId || connection !== 'open') return
    if (session?.status === 'completed' || session?.status === 'abandoned') return
    if (requestingNext.current) return

    const questionCount = events.filter((e) => e.kind === 'question').length
    const feedbackCount = events.filter((e) => e.kind === 'feedback').length
    const lastTurn = [...events]
      .reverse()
      .find((e) => ['question', 'answer', 'feedback'].includes(e.kind))

    const needFirst = questionCount === 0
    const needNext =
      lastTurn?.kind === 'feedback' && questionCount === feedbackCount

    if (!needFirst && !needNext) return

    requestingNext.current = true
    send({ type: 'next_question' })
  }, [sessionId, connection, session?.status, events, send])

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      if (!userId || tab !== 'history') return
      try {
        const rows = await listUserInterviews(userId)
        if (!cancelled) setHistory(rows || [])
      } catch {
        if (!cancelled) setHistory([])
      }
    })()
    return () => {
      cancelled = true
    }
  }, [userId, tab])

  const awaitingAnswer = useMemo(() => {
    const lastQ = [...events].reverse().find((e) => e.kind === 'question')
    if (!lastQ) return false
    const after = events.slice(events.indexOf(lastQ) + 1)
    return !after.some((e) => e.kind === 'answer' || e.kind === 'feedback')
  }, [events])

  const turnLabel = useMemo(() => {
    const q = events.filter((e) => e.kind === 'question').length
    return `Question ${String(Math.max(q, 1)).padStart(2, '0')}`
  }, [events])

  const score = session?.running_score

  const interviewStats = useMemo(() => {
    const scored = events.filter((e) => e.kind === 'feedback' && e.score != null)
    const answers = events.filter((e) => e.kind === 'answer')
    const overall =
      score != null
        ? Number(score)
        : scored.length
          ? scored.reduce((s, e) => s + Number(e.score), 0) / scored.length
          : null

    let technical = overall
    if (scored.length) {
      const weights = scored.map((_, i) => i + 1)
      const wSum = weights.reduce((a, b) => a + b, 0)
      technical = scored.reduce((s, e, i) => s + Number(e.score) * weights[i], 0) / wSum
    }

    let communication = overall
    if (answers.length && scored.length) {
      const lens = answers.map((a) => String(a.text || '').trim().split(/\s+/).filter(Boolean).length)
      const avgLen = lens.reduce((a, b) => a + b, 0) / lens.length
      const lenFactor = avgLen < 25 ? -0.8 : avgLen < 60 ? -0.2 : avgLen < 120 ? 0.15 : 0.35
      communication = Math.max(1, Math.min(10, (overall || 7) + lenFactor))
    }

    const rating = (v) => {
      if (v == null) return '—'
      if (v >= 8.5) return 'Excellent'
      if (v >= 7.5) return 'Strong'
      if (v >= 6.5) return 'Good'
      if (v >= 5) return 'Fair'
      return 'Needs work'
    }

    let vsLast = null
    try {
      const prev = Number(localStorage.getItem('skillbridge.lastInterviewScore') || '')
      if (overall != null && Number.isFinite(prev) && prev > 0) {
        const delta = overall - prev
        vsLast = `${delta >= 0 ? '↑' : '↓'} ${Math.abs(delta).toFixed(1)} vs last session`
      }
    } catch {
      /* ignore */
    }

    return {
      technical,
      communication,
      overall,
      technicalTrend: rating(technical),
      communicationTrend: rating(communication),
      overallTrend: vsLast || (session?.status === 'completed' ? 'Complete' : 'In progress'),
    }
  }, [events, score, session?.status])

  useEffect(() => {
    if (score == null) return
    if (session?.status !== 'completed') return
    try {
      localStorage.setItem('skillbridge.lastInterviewScore', String(score))
    } catch {
      /* ignore */
    }
  }, [score, session?.status])

  async function startSession() {
    const targetRole = role.trim()
    if (!userId) {
      setSetupError('Sign in to start an interview')
      return
    }
    if (!targetRole) {
      setSetupError('Enter the target role for this interview')
      return
    }
    setBusy(true)
    setSetupError(null)
    try {
      const created = await startInterview({ role: targetRole, cvId, difficulty })
      requestingNext.current = false
      questionCountSeen.current = 0
      resetTranscript()
      setSessionId(created.id)
      setTab('live')
      push('Interview session started')
    } catch (err) {
      setSetupError(formatApiError(err, 'Could not start interview'))
    } finally {
      setBusy(false)
    }
  }

  function submitAnswer() {
    const text = answer.trim()
    if (!text) return
    if (!send({ type: 'answer', answer: text })) return
    setEvents((prev) => [...prev, { id: `${Date.now()}-ans`, kind: 'answer', text }])
    setAnswer('')
    push('Answer submitted — AI is evaluating')
  }

  async function finishSession() {
    if (!sessionId) return
    try {
      send({ type: 'complete' })
      await completeInterview(sessionId)
      push('Session ended')
    } catch (err) {
      push(formatApiError(err, 'Could not complete session'))
    }
  }

  async function leaveSession() {
    if (sessionId && session?.status !== 'completed' && session?.status !== 'abandoned') {
      try {
        await abandonInterview(sessionId)
      } catch {
        /* ignore */
      }
    }
    setSessionId(null)
    resetTranscript()
  }

  async function onResume(id) {
    setBusy(true)
    try {
      await resumeInterview(id)
      const hist = await getInterviewHistory(id)
      setEvents(
        (hist?.history || []).flatMap((t, i) => {
          const rows = [{ id: `h-q-${i}`, kind: 'question', text: t.question, topics: t.topics }]
          if (t.answer) rows.push({ id: `h-a-${i}`, kind: 'answer', text: t.answer })
          if (t.feedback) {
            rows.push({
              id: `h-f-${i}`,
              kind: 'feedback',
              text: t.feedback,
              score: t.score,
            })
          }
          return rows
        }),
      )
      requestingNext.current = false
      questionCountSeen.current = (hist?.history || []).filter((t) => t.question).length
      setSessionId(id)
      setTab('live')
    } catch (err) {
      push(formatApiError(err, 'Could not resume interview'))
    } finally {
      setBusy(false)
    }
  }

  const questionCount = events.filter((e) => e.kind === 'question').length
  const feedbackCount = events.filter((e) => e.kind === 'feedback').length
  const waitingForNext =
    connection === 'open' &&
    session?.status !== 'completed' &&
    session?.status !== 'abandoned' &&
    !awaitingAnswer &&
    (questionCount === 0 || feedbackCount === questionCount)
  const generating = waitingForNext
  const evaluating =
    connection === 'open' &&
    events.some((e) => e.kind === 'answer') &&
    (() => {
      const last = [...events].reverse().find((e) => ['answer', 'feedback', 'question'].includes(e.kind))
      return last?.kind === 'answer'
    })()

  const liveNotice = evaluating
    ? 'Evaluating your answer…'
    : generating
      ? questionCount === 0
        ? 'Generating your first question…'
        : 'Generating the next question…'
      : null

  // Internal/status lines only as centered notices — never as interviewer bubbles.
  // Drop busy notices from the event stream when we already show liveNotice.
  const transcriptEvents = events.filter((e) => {
    if (e.kind === 'system' || e.kind === 'error') {
      if (liveNotice && isBusyNotice(e.text)) return false
      return true
    }
    return true
  })

  return (
    <ViewShell>
      {sessionId ? (
        <PageHeader
          eyebrow={`AI technical interview · ${difficulty} track`}
          title="Interview Simulator."
          sub={`${session?.role || role || 'Role'} · ${connection}`}
          actions={
            <div className="pagehead-actions">
              {session?.status === 'completed' ? (
                <button type="button" className="btn primary" onClick={leaveSession}>
                  Start new session
                </button>
              ) : (
                <button
                  type="button"
                  className="btn primary"
                  onClick={() => setConfirmAction('end')}
                >
                  End session
                </button>
              )}
              <button type="button" className="btn" onClick={() => setConfirmAction('leave')}>
                Leave
              </button>
            </div>
          }
        />
      ) : null}

      <div className="tabs" role="tablist">
        <button type="button" className={tab === 'live' ? 'active' : ''} onClick={() => setTab('live')}>
          Live session
        </button>
        <button type="button" className={tab === 'history' ? 'active' : ''} onClick={() => setTab('history')}>
          Past interviews
        </button>
      </div>

      {tab === 'history' ? (
        <div className="card">
          <div className="cardtitle">
            Past interviews <span>{history.length}</span>
          </div>
          {history.length === 0 ? (
            <p className="empty-state">No previous sessions.</p>
          ) : (
            history.map((row) => (
              <div className="job" key={row.id} style={{ padding: '14px 0' }}>
                <div className="joblogo">#{row.id}</div>
                <div className="jobinfo">
                  <div className="jobtitle">{row.role || 'Interview'}</div>
                  <div className="jobmeta">
                    {row.status} · score {row.running_score ?? '—'}
                  </div>
                </div>
                <button type="button" className="btn" onClick={() => onResume(row.id)}>
                  Resume
                </button>
              </div>
            ))
          )}
        </div>
      ) : !sessionId ? (
        <div className="interview-hero">
          <div className="interview-hero-copy">
            <h2>Practice makes interviews easier.</h2>
            <p>
              Pick a role and a level — the AI interviewer asks adaptive technical questions,
              scores every answer and coaches you in real time.
            </p>
            <ul className="interview-hero-points">
              <li>
                <b>Adaptive</b> — questions follow your role, level and answers.
              </li>
              <li>
                <b>Live feedback</b> — a score and coaching after every answer.
              </li>
              <li>
                <b>No pressure</b> — sessions end only when you decide.
              </li>
            </ul>
          </div>
          <div className="card interview-setup-card">
            {setupError && (
              <div className="callout is-error" role="alert">
                {setupError}
              </div>
            )}
            <label>
              Target role
              <input
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="e.g. Java Developer"
                autoComplete="off"
                list="role-suggestions"
              />
            </label>
            <div className="chipgroup">
              <span className="chipgroup-label">Popular roles</span>
              <div className="role-chips" role="listbox" aria-label="Popular roles">
                {ROLE_SUGGESTIONS.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    className={`role-chip${role.trim().toLowerCase() === suggestion.toLowerCase() ? ' active' : ''}`}
                    onClick={() => setRole(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            </div>
            <label>
              Experience level
              <div className="segmented" role="radiogroup" aria-label="Experience level">
                {LEVELS.map((level) => (
                  <button
                    key={level}
                    type="button"
                    className={difficulty === level ? 'active' : ''}
                    onClick={() => setDifficulty(level)}
                  >
                    {level === 'junior' ? 'Junior' : level === 'mid' ? 'Mid' : 'Senior'}
                  </button>
                ))}
              </div>
            </label>
            <button
              type="button"
              className="btn primary"
              disabled={busy || !userId || !role.trim()}
              onClick={startSession}
            >
              {busy ? 'Starting…' : 'Start interview'}
            </button>
          </div>
        </div>
      ) : (
        <>
          {(lastError || connection !== 'open') && session?.status !== 'completed' && (
            <div className="callout" style={{ marginBottom: 12 }}>
              {lastError || `Connection: ${connection}`}{' '}
              <button
                type="button"
                className="link"
                onClick={() => {
                  clearError()
                  connect()
                }}
              >
                Reconnect
              </button>
            </div>
          )}
          <div className="card chatcard">
            <div className="chathead">
              <div className="interviewer">
                <div className="aibadge">✦</div>
                <div>
                  <b style={{ fontSize: 12 }}>AI Interviewer</b>
                  <span style={{ display: 'block', color: 'var(--faint)', fontSize: 10, marginTop: 2 }}>
                    {session?.role || role || 'Backend'} · Adaptive difficulty
                  </span>
                </div>
              </div>
              <span className="mono" style={{ fontSize: 10, color: 'var(--primary)' }}>
                {turnLabel}
              </span>
            </div>
            <div className="chatbody">
              {transcriptEvents.map((ev) => (
                <ChatMsg key={ev.id} event={ev} />
              ))}
              {liveNotice && <div className="chat-notice">{liveNotice}</div>}
              <div ref={bottomRef} />
            </div>
            <div className="chatinput">
              <textarea
                id="answer"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault()
                    if (connection === 'open' && awaitingAnswer && answer.trim()) submitAnswer()
                  }
                }}
                placeholder="Type your answer..."
                rows={2}
                disabled={connection !== 'open' || !awaitingAnswer}
              />
              <button
                type="button"
                className="btn primary"
                disabled={connection !== 'open' || !awaitingAnswer || !answer.trim()}
                onClick={submitAnswer}
              >
                Send ↗
              </button>
            </div>
          </div>
          <div className="grid3" style={{ marginTop: 16 }}>
            <MetricCard
              labelFirst
              label="Technical depth"
              value={
                interviewStats.technical != null ? Number(interviewStats.technical).toFixed(1) : '—'
              }
              trend={interviewStats.technicalTrend}
              trendStyle={{ color: 'var(--primary2)' }}
            />
            <MetricCard
              labelFirst
              label="Communication"
              value={
                interviewStats.communication != null
                  ? Number(interviewStats.communication).toFixed(1)
                  : '—'
              }
              trend={interviewStats.communicationTrend}
              trendStyle={{ color: 'var(--primary2)' }}
            />
            <MetricCard
              labelFirst
              label="Overall session"
              value={
                interviewStats.overall != null ? Number(interviewStats.overall).toFixed(1) : '—'
              }
              trend={interviewStats.overallTrend}
              trendStyle={{ color: 'var(--primary2)' }}
            />
          </div>
        </>
      )}

      <ConfirmDialog
        open={confirmAction === 'end'}
        title="End session?"
        message="This finishes the interview and saves your score and feedback."
        confirmLabel="End session"
        onConfirm={() => {
          setConfirmAction(null)
          finishSession()
        }}
        onCancel={() => setConfirmAction(null)}
      />
      <ConfirmDialog
        open={confirmAction === 'leave'}
        title="Leave session?"
        message="This abandons the interview without a final score."
        confirmLabel="Leave session"
        tone="danger"
        onConfirm={() => {
          setConfirmAction(null)
          leaveSession()
        }}
        onCancel={() => setConfirmAction(null)}
      />
    </ViewShell>
  )
}
