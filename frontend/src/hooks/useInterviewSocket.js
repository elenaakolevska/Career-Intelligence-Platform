import { useCallback, useEffect, useRef, useState } from 'react'
import { interviewWsUrl } from '../api/interview'

/**
 * Manage a live interview WebSocket (P8-06).
 * Connection loss is surfaced via `connection` + `lastError` — never silent.
 * Completing/abandoning the session is an intentional close (not an error).
 */
export function useInterviewSocket(sessionId) {
  const [connection, setConnection] = useState('idle') // idle|connecting|open|closed|error
  const [lastError, setLastError] = useState(null)
  const [session, setSession] = useState(null)
  const [events, setEvents] = useState([])
  const wsRef = useRef(null)
  const intentionalClose = useRef(false)
  const sessionEnded = useRef(false)
  const socketGen = useRef(0)
  const sessionIdRef = useRef(sessionId)

  useEffect(() => {
    sessionIdRef.current = sessionId
  }, [sessionId])

  const pushEvent = useCallback((event) => {
    setEvents((prev) => [...prev, { id: `${Date.now()}-${prev.length}`, at: new Date().toISOString(), ...event }])
  }, [])

  const disconnect = useCallback(() => {
    intentionalClose.current = true
    if (wsRef.current) {
      try {
        wsRef.current.close(1000, 'client_disconnect')
      } catch {
        /* ignore */
      }
      wsRef.current = null
    }
    setConnection('closed')
  }, [])

  const handleMessage = useCallback(
    (raw) => {
      let msg
      try {
        msg = JSON.parse(raw)
      } catch {
        setLastError('Received invalid message from server')
        pushEvent({ kind: 'error', text: 'Invalid server message' })
        return
      }

      const type = msg.type
      if (msg.session) setSession(msg.session)

      if (type === 'connected' || type === 'state') {
        if (msg.session?.history?.length) {
          const hydrated = []
          for (const turn of msg.session.history) {
            if (turn.question) {
              hydrated.push({
                id: `q-${turn.turn_index}`,
                at: turn.asked_at || new Date().toISOString(),
                kind: 'question',
                text: turn.question,
                turnIndex: turn.turn_index,
                topics: turn.topics,
                difficulty: turn.difficulty,
              })
            }
            if (turn.answer) {
              hydrated.push({
                id: `a-${turn.turn_index}`,
                at: turn.answered_at || new Date().toISOString(),
                kind: 'answer',
                text: turn.answer,
              })
            }
            if (turn.feedback || turn.score != null) {
              hydrated.push({
                id: `f-${turn.turn_index}`,
                at: turn.answered_at || new Date().toISOString(),
                kind: 'feedback',
                text: turn.feedback || 'Scored',
                score: turn.score,
                runningScore: msg.session.running_score,
              })
            }
          }
          setEvents(hydrated)
        }
        pushEvent({
          kind: 'system',
          text: type === 'connected' ? 'Connected to interview session' : 'Session state refreshed',
        })
        return
      }
      if (type === 'status') {
        const detail = msg.detail || 'Working…'
        setEvents((prev) => {
          const withoutBusy = prev.filter(
            (e) => !(e.kind === 'system' && /generat|evaluat|working/i.test(e.text || '')),
          )
          return [
            ...withoutBusy,
            {
              id: `status-${Date.now()}`,
              at: new Date().toISOString(),
              kind: 'system',
              text: detail,
            },
          ]
        })
        return
      }
      if (type === 'question') {
        setEvents((prev) => {
          const lastQ = [...prev].reverse().find((e) => e.kind === 'question')
          if (lastQ && lastQ.text === msg.question) {
            // Same question already shown (duplicate WS delivery) — ignore
            return prev.filter(
              (e) => !(e.kind === 'system' && /generat/i.test(e.text || '')),
            )
          }
          const cleaned = prev.filter(
            (e) => !(e.kind === 'system' && /generat/i.test(e.text || '')),
          )
          return [
            ...cleaned,
            {
              id: `q-${msg.turn_index ?? Date.now()}`,
              at: new Date().toISOString(),
              kind: 'question',
              text: msg.question,
              turnIndex: msg.turn_index,
              topics: msg.topics,
              difficulty: msg.difficulty,
            },
          ]
        })
        return
      }
      if (type === 'feedback') {
        setEvents((prev) => {
          const cleaned = prev.filter(
            (e) => !(e.kind === 'system' && /evaluat|working|generat/i.test(e.text || '')),
          )
          return [
            ...cleaned,
            {
              id: `f-${msg.turn_index ?? Date.now()}`,
              at: new Date().toISOString(),
              kind: 'feedback',
              text: msg.feedback,
              score: msg.score,
              question: msg.question,
              answer: msg.answer,
              turnIndex: msg.turn_index,
              runningScore: msg.running_score ?? msg.session?.running_score,
            },
          ]
        })
        return
      }
      if (type === 'completed') {
        sessionEnded.current = true
        intentionalClose.current = true
        setLastError(null)
        pushEvent({ kind: 'system', text: 'Interview marked complete' })
        try {
          wsRef.current?.close(1000, 'interview_completed')
        } catch {
          /* ignore */
        }
        return
      }
      if (type === 'abandoned') {
        sessionEnded.current = true
        intentionalClose.current = true
        setLastError(null)
        pushEvent({ kind: 'system', text: 'Interview abandoned' })
        try {
          wsRef.current?.close(1000, 'interview_abandoned')
        } catch {
          /* ignore */
        }
        return
      }
      if (type === 'pong') return
      if (type === 'error') {
        const detail = msg.detail || msg.code || 'Interview error'
        setLastError(detail)
        pushEvent({ kind: 'error', text: detail, code: msg.code })
        return
      }
      pushEvent({ kind: 'system', text: `Event: ${type}` })
    },
    [pushEvent],
  )

  const connect = useCallback(() => {
    const id = sessionIdRef.current
    if (!id) return
    intentionalClose.current = false
    sessionEnded.current = false
    setLastError(null)
    setConnection('connecting')

    if (wsRef.current) {
      intentionalClose.current = true
      try {
        wsRef.current.close(1000, 'reconnect')
      } catch {
        /* ignore */
      }
    }

    const gen = ++socketGen.current
    intentionalClose.current = false
    const url = interviewWsUrl(id)
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {
      if (gen !== socketGen.current) return
      setConnection('open')
      setLastError(null)
    }
    ws.onmessage = (ev) => {
      if (gen !== socketGen.current) return
      handleMessage(ev.data)
    }
    ws.onerror = () => {
      if (gen !== socketGen.current) return
      if (intentionalClose.current || sessionEnded.current) return
      setConnection('error')
      setLastError('WebSocket connection error')
    }
    ws.onclose = () => {
      if (gen !== socketGen.current) return
      if (wsRef.current === ws) wsRef.current = null
      if (intentionalClose.current || sessionEnded.current) {
        setConnection('closed')
        setLastError(null)
        return
      }
      setConnection('closed')
      setLastError((prev) => prev || 'Connection lost — reconnect to continue without losing session state')
      pushEvent({ kind: 'error', text: 'Connection lost' })
    }
  }, [handleMessage, pushEvent])

  const send = useCallback((payload) => {
    const ws = wsRef.current
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      setLastError('Not connected — reconnect before sending')
      return false
    }
    // Completing / leaving is intentional — avoid a false "Connection lost" if the
    // server closes the socket right after acknowledging.
    if (payload?.type === 'complete' || payload?.type === 'abandon') {
      intentionalClose.current = true
      sessionEnded.current = true
    }
    ws.send(JSON.stringify(payload))
    return true
  }, [])

  const resetTranscript = useCallback(() => setEvents([]), [])

  useEffect(() => {
    if (!sessionId) {
      disconnect()
      setSession(null)
      setEvents([])
      setConnection('idle')
      return undefined
    }
    connect()
    return () => {
      intentionalClose.current = true
      socketGen.current += 1
      if (wsRef.current) {
        try {
          wsRef.current.close(1000, 'effect_cleanup')
        } catch {
          /* ignore */
        }
        wsRef.current = null
      }
    }
  }, [sessionId, connect, disconnect])

  return {
    connection,
    lastError,
    session,
    events,
    send,
    connect,
    disconnect,
    resetTranscript,
    setEvents,
    setSession,
    clearError: () => setLastError(null),
  }
}
