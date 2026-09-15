import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { PageHeader, ViewShell } from '../components/ui'
import { useToast } from '../components/ToastHost'
import { formatApiError } from '../api'

export default function SettingsPage() {
  const { userEmail, fullName, updateProfile, changePassword, logout } = useAuth()
  const { push } = useToast()

  const [name, setName] = useState(fullName || '')
  const [email, setEmail] = useState(userEmail || '')
  const [savingProfile, setSavingProfile] = useState(false)

  const [currentPw, setCurrentPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [savingPw, setSavingPw] = useState(false)

  async function saveProfile(e) {
    e.preventDefault()
    if (savingProfile) return
    setSavingProfile(true)
    try {
      await updateProfile({ full_name: name, email })
      push('Profile updated')
    } catch (err) {
      push(formatApiError(err, 'Could not update profile'))
    } finally {
      setSavingProfile(false)
    }
  }

  async function savePassword(e) {
    e.preventDefault()
    if (savingPw) return
    if (newPw !== confirmPw) {
      push('New passwords do not match')
      return
    }
    setSavingPw(true)
    try {
      await changePassword({ current_password: currentPw, new_password: newPw })
      setCurrentPw('')
      setNewPw('')
      setConfirmPw('')
      push('Password updated')
    } catch (err) {
      push(formatApiError(err, 'Could not update password'))
    } finally {
      setSavingPw(false)
    }
  }

  return (
    <ViewShell>
      <PageHeader eyebrow="Account" title="Settings." sub="Manage your profile and security." />

      <div className="grid2" style={{ maxWidth: 860 }}>
        <div className="card">
          <div className="cardtitle">Profile</div>
          <form className="settings-form" onSubmit={saveProfile}>
            <label>
              Full name
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Your name"
                autoComplete="name"
              />
            </label>
            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                autoComplete="email"
              />
            </label>
            <div className="settings-form-actions">
              <button type="submit" className="btn primary" disabled={savingProfile || !email.trim()}>
                {savingProfile ? 'Saving…' : 'Save changes'}
              </button>
            </div>
          </form>
        </div>

        <div className="card">
          <div className="cardtitle">Password</div>
          <form className="settings-form" onSubmit={savePassword}>
            <label>
              Current password
              <input
                type="password"
                value={currentPw}
                onChange={(e) => setCurrentPw(e.target.value)}
                autoComplete="current-password"
              />
            </label>
            <label>
              New password
              <input
                type="password"
                value={newPw}
                onChange={(e) => setNewPw(e.target.value)}
                placeholder="At least 8 characters"
                autoComplete="new-password"
              />
            </label>
            <label>
              Confirm new password
              <input
                type="password"
                value={confirmPw}
                onChange={(e) => setConfirmPw(e.target.value)}
                autoComplete="new-password"
              />
            </label>
            <div className="settings-form-actions">
              <button
                type="submit"
                className="btn primary"
                disabled={savingPw || !currentPw || !newPw || !confirmPw}
              >
                {savingPw ? 'Updating…' : 'Update password'}
              </button>
            </div>
          </form>
        </div>
      </div>

      <div className="card" style={{ maxWidth: 860, marginTop: 16 }}>
        <div className="cardtitle">Session</div>
        <div className="recommend">
          <i>•</i>
          <span>
            <strong>{fullName || '—'}</strong>
            <div className="muted">{userEmail}</div>
          </span>
        </div>
        <div className="settings-form-actions" style={{ justifyContent: 'flex-start', marginTop: 16 }}>
          <button type="button" className="btn danger" onClick={logout}>
            Log out
          </button>
        </div>
      </div>
    </ViewShell>
  )
}
