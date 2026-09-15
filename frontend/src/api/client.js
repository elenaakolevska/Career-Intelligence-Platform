/**
 * Shared API client — all frontend HTTP/WS traffic goes through here (P8-07).
 */

const DEFAULT_BASE = 'http://localhost:8000/api/v1'
const TOKEN_KEY = 'skillbridge.token'

export function getApiBaseUrl() {
  const raw = import.meta.env.VITE_API_BASE_URL
  if (raw && String(raw).trim()) {
    return String(raw).replace(/\/$/, '')
  }
  return DEFAULT_BASE
}

/** Convert HTTP API base to WebSocket base (ws/wss). */
export function getWsBaseUrl() {
  const http = getApiBaseUrl()
  if (http.startsWith('https://')) return `wss://${http.slice('https://'.length)}`
  if (http.startsWith('http://')) return `ws://${http.slice('http://'.length)}`
  if (http.startsWith('ws://') || http.startsWith('wss://')) return http
  return `ws://${http}`
}

export function wsUrl(path) {
  const base = getWsBaseUrl()
  const suffix = path.startsWith('/') ? path : `/${path}`
  return `${base}${suffix}`
}

export function getStoredToken() {
  try {
    return localStorage.getItem(TOKEN_KEY)
  } catch {
    return null
  }
}

export function setStoredToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    // ignore storage errors
  }
}

export function clearStoredToken() {
  setStoredToken(null)
}

export class ApiError extends Error {
  constructor(message, { status, detail, body, code } = {}) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.body = body
    this.code = code
  }
}

export function formatApiError(err, fallback = 'Something went wrong') {
  if (!err) return fallback
  if (err instanceof ApiError) return err.detail || err.message || fallback
  if (typeof err === 'string') return err
  return err.message || fallback
}

function extractDetail(body, fallback) {
  if (!body) return fallback
  if (typeof body === 'string') return body
  if (typeof body.detail === 'string') return body.detail
  if (Array.isArray(body.detail)) {
    return body.detail
      .map((item) => (typeof item === 'string' ? item : item.msg || JSON.stringify(item)))
      .join('; ')
  }
  if (body.error && body.detail) {
    const d = body.detail
    if (typeof d === 'string') return d
    if (Array.isArray(d)) {
      return d.map((item) => (typeof item === 'string' ? item : item.msg || JSON.stringify(item))).join('; ')
    }
  }
  if (body.message) return body.message
  return fallback
}

export async function apiRequest(path, options = {}) {
  const base = getApiBaseUrl()
  const url = path.startsWith('http') ? path : `${base}${path.startsWith('/') ? '' : '/'}${path}`

  const headers = { ...(options.headers || {}) }
  const isFormData = typeof FormData !== 'undefined' && options.body instanceof FormData
  if (!isFormData && options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }

  const token = options.token !== undefined ? options.token : getStoredToken()
  if (token && !headers.Authorization) {
    headers.Authorization = `Bearer ${token}`
  }

  let response
  try {
    response = await fetch(url, { ...options, headers })
  } catch (err) {
    throw new ApiError(
      'Cannot reach the API. Is the backend running on port 8000?',
      { status: 0, detail: err?.message || 'Network error', code: 'network' },
    )
  }

  const contentType = response.headers.get('content-type') || ''
  let body = null
  if (contentType.includes('application/json')) {
    try {
      body = await response.json()
    } catch {
      body = null
    }
  } else {
    const text = await response.text()
    body = text || null
  }

  if (!response.ok) {
    if (response.status === 401 && !options.skipAuthRedirect) {
      clearStoredToken()
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        const next = encodeURIComponent(window.location.pathname + window.location.search)
        window.location.assign(`/login?next=${next}`)
      }
    }
    const detail = extractDetail(body, response.statusText || 'Request failed')
    throw new ApiError(detail, {
      status: response.status,
      detail,
      body,
      code: response.status === 0 ? 'network' : 'http',
    })
  }

  return body
}

export const api = {
  get: (path, options) => apiRequest(path, { ...options, method: 'GET' }),
  post: (path, body, options = {}) =>
    apiRequest(path, {
      ...options,
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
    }),
  patch: (path, body, options = {}) =>
    apiRequest(path, {
      ...options,
      method: 'PATCH',
      body: body instanceof FormData ? body : JSON.stringify(body ?? {}),
    }),
}
