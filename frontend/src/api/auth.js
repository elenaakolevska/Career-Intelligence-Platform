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

export function updateProfile({ full_name, email }) {
  return api.patch('/users/me', { full_name, email })
}

export function changePassword({ current_password, new_password }) {
  return api.post('/users/me/password', { current_password, new_password })
}
