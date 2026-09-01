import { useAuth } from '../context/AuthContext'
import { PageHeader, ViewShell } from '../components/ui'
import { useToast } from '../components/ToastHost'

export default function SettingsPage() {
  const { userEmail, fullName, logout } = useAuth()
  const { push } = useToast()

  return (
    <ViewShell>
      <PageHeader eyebrow="Account" title="Settings." sub="Manage your SkillBridge account." />
      <div className="card bigcard" style={{ maxWidth: 520 }}>
        <div className="cardtitle">Profile</div>
        <div className="recommend">
          <i>•</i>
          <span>
            <strong>{fullName || '—'}</strong>
            <div className="muted">{userEmail}</div>
          </span>
        </div>
        <div className="panelsection">
          <h4>Actions</h4>
          <button
            type="button"
            className="btn"
            style={{ marginRight: 8 }}
            onClick={() => push('Password reset coming soon')}
          >
            Change password
          </button>
          <button type="button" className="btn primary" onClick={logout}>
            Log out
          </button>
        </div>
      </div>
    </ViewShell>
  )
}
