import { api, wsUrl } from './client'

export function startInterview({ role, cvId, difficulty = 'junior' }) {
  return api.post('/interview/start', {
    role: role || null,
    cv_id: cvId || null,
    difficulty: difficulty || 'junior',
  })
}

export function listUserInterviews(userId) {
  if (userId == null) return api.get('/interview/me')
  return api.get(`/interview/user/${userId}`)
}

export function listUserInterviewSummaries(userId) {
  if (userId == null) return api.get('/interview/me/summary')
  return api.get(`/interview/user/${userId}/summary`)
}

export function getInterview(sessionId) {
  return api.get(`/interview/${sessionId}`)
}

export function getInterviewHistory(sessionId) {
  return api.get(`/interview/${sessionId}/history`)
}

export function resumeInterview(sessionId) {
  return api.post(`/interview/${sessionId}/resume`, {})
}

export function completeInterview(sessionId, overallFeedback = null) {
  return api.post(`/interview/${sessionId}/complete`, {
    overall_feedback: overallFeedback,
  })
}

export function abandonInterview(sessionId) {
  return api.post(`/interview/${sessionId}/abandon`, {})
}

export function interviewWsUrl(sessionId) {
  return wsUrl(`/interview/ws/${sessionId}`)
}
