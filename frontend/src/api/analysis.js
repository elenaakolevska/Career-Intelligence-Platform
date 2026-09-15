import { api } from './client'

export function runAnalysis(cvId) {
  return api.post(`/analysis/run/${cvId}`, {})
}

export function getLatestAnalysis(cvId) {
  return api.get(`/analysis/cv/${cvId}/latest`)
}

export function fetchJobsForCv(cvId) {
  return api.post(`/jobs/fetch/${cvId}`, {})
}
