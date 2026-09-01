import { api } from './client'

export function createUser({ email, full_name } = {}) {
  return api.post('/users/', { email, full_name: full_name || null })
}

export function getUser(userId) {
  return api.get(`/users/${userId}`)
}

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
