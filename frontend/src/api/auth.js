import { api } from './client'

export function register({ email, password, full_name }) {
  return api.post('/auth/register', {
    email,
    password,
    full_name: full_name || null,
  })
}

export function login({ email, password }) {
  return api.post('/auth/login', { email, password })
}

export function getMe() {
  return api.get('/auth/me')
}
