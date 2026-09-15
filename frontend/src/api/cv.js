import { api } from './client'

export function listMyCvs() {
  return api.get('/cv/')
}

export function uploadCv({ file }) {
  const fd = new FormData()
  fd.append('file', file)
  return api.post('/cv/upload', fd)
}

export function getCv(cvId) {
  return api.get(`/cv/${cvId}`)
}
