import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import {
  changePassword as changePasswordRequest,
  getMe,
  login as loginRequest,
  register as registerRequest,
  updateProfile as updateProfileRequest,
} from '../api/auth'
import { ApiError, clearStoredToken, formatApiError, getStoredToken, setStoredToken } from '../api/client'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => getStoredToken())
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(() => Boolean(getStoredToken()))
  const [error, setError] = useState(null)

  const applySession = useCallback((accessToken, nextUser) => {
    setStoredToken(accessToken)
    setToken(accessToken)
    setUser(nextUser)
    setError(null)
  }, [])

  const logout = useCallback(() => {
    clearStoredToken()
    setToken(null)
    setUser(null)
    setError(null)
    try {
      localStorage.removeItem('cip.session.v1')
      localStorage.removeItem('skillbridge.session.v1')
    } catch {
      // ignore
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    async function hydrate() {
      if (!token) {
        setUser(null)
        setLoading(false)
        return
      }
      setLoading(true)
      try {
        const me = await getMe()
        if (!cancelled) {
          setUser(me)
          setError(null)
        }
      } catch (err) {
        if (!cancelled) {
          if (err instanceof ApiError && err.status === 401) {
            logout()
          } else {
            setError(formatApiError(err, 'Could not restore session'))
          }
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    hydrate()
    return () => {
      cancelled = true
    }
  }, [token, logout])

  const login = useCallback(
    async ({ email, password }) => {
      const data = await loginRequest({ email, password })
      applySession(data.access_token, data.user)
      return data.user
    },
    [applySession],
  )

  const register = useCallback(
    async ({ email, password, full_name }) => {
      const data = await registerRequest({ email, password, full_name })
      applySession(data.access_token, data.user)
      return data.user
    },
    [applySession],
  )

  const updateProfile = useCallback(async ({ full_name, email }) => {
    const updated = await updateProfileRequest({ full_name, email })
    setUser(updated)
    return updated
  }, [])

  const changePassword = useCallback(async ({ current_password, new_password }) => {
    await changePasswordRequest({ current_password, new_password })
  }, [])

  const value = useMemo(
    () => ({
      token,
      user,
      userId: user?.id ?? null,
      userEmail: user?.email ?? '',
      fullName: user?.full_name ?? '',
      isAuthenticated: Boolean(token && user),
      loading,
      error,
      login,
      register,
      updateProfile,
      changePassword,
      logout,
    }),
    [token, user, loading, error, login, register, updateProfile, changePassword, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
