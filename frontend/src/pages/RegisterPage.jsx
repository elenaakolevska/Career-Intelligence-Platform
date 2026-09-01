import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { formatApiError } from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function RegisterPage() {
  const { register, isAuthenticated, loading } = useAuth()
  const navigate = useNavigate()
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)

  if (!loading && isAuthenticated) {
    return <Navigate to="/cv" replace />
  }

  async function onSubmit(e) {
    e.preventDefault()
    setError(null)
    setSubmitting(true)
    try {
      await register({
        email: email.trim(),
        password,
        full_name: fullName.trim() || null,
      })
      navigate('/cv', { replace: true })
    } catch (err) {
      setError(formatApiError(err, 'Could not create account'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="auth-screen">
      <div className="auth-atmosphere" aria-hidden />
      <div className="auth-panel">
        <p className="brand-hero">SkillBridge</p>
        <h1>Create account</h1>
        <p className="auth-lede">Bridge your skills to roles that need them.</p>
        <form className="auth-form" onSubmit={onSubmit}>
          <label>
            Full name
            <input
              type="text"
              autoComplete="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Optional"
            />
          </label>
          <label>
            Email
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label>
            Password
            <input
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button type="submit" className="btn primary" disabled={submitting}>
            {submitting ? 'Creating…' : 'Create account'}
          </button>
        </form>
        <p className="auth-switch">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
