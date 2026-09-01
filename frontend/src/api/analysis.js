import { api } from './client'

export function runAnalysis(cvId) {
  return api.post(`/analysis/run/${cvId}`, {})
}

export function getLatestAnalysis(cvId) {
  return api.get(`/analysis/cv/${cvId}/latest`)
}

export function getAnalysis(analysisId) {
  return api.get(`/analysis/${analysisId}`)
}

export function seedMockJobs() {
  return api.post('/jobs/seed-mock', {})
}
