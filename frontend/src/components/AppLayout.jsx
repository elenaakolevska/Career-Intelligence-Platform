import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { useAuth } from '../context/AuthContext'
import { useSession } from '../context/SessionContext'
import { useToast } from './ToastHost'
import SessionErrorBanner from './SessionErrorBanner'
import ToastHost from './ToastHost'
import BrandLogo from './BrandLogo'
import {
  IconBars,
  IconBriefcase,
  IconChat,
  IconDoc,
  IconGrid,
  IconList,
  IconSettings,
} from './icons'
import { greetingName, initialsFrom } from '../lib/analysisUi'
import { exportOverviewPdf } from '../lib/exportPdf'

const TITLES = {
  '/dashboard': 'Overview',
  '/': 'Overview',
  '/cv': 'My CV',
  '/jobs': 'Job Matches',
  '/skills': 'Skill Gap',
  '/roadmap': 'Learning Roadmap',
  '/interview': 'Interview Simulator',
  '/settings': 'Settings',
}

function NavItem({ to, label, icon: Icon, badge, needsCv, hasCompletedCv }) {
  const locked = needsCv && !hasCompletedCv
  return (
    <NavLink
      to={locked ? '/cv' : to}
      className={({ isActive }) => (isActive && !locked ? 'active' : '')}
      state={locked ? { guardReason: 'no-cv' } : undefined}
      title={locked ? 'Upload a CV first' : undefined}
    >
      <Icon />
      <span>{label}</span>
      {badge ? <span className="badge">{badge}</span> : null}
    </NavLink>
  )
}

export default function AppLayout() {
  const { hasCompletedCv, bootstrapping } = useSession()
  const { userEmail, fullName, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()
  const { push, dismiss } = useToast()
  const [exporting, setExporting] = useState(false)

  const title = TITLES[location.pathname] || 'Overview'
  const first = greetingName(fullName, userEmail)
  const initials = initialsFrom(fullName, userEmail)
  const isOverview = location.pathname === '/' || location.pathname === '/dashboard'

  async function handleExport() {
    if (exporting) return
    setExporting(true)
    const toastId = push('Preparing report…', { ttl: 0 })
    try {
      await exportOverviewPdf()
      dismiss(toastId)
      push('Report downloaded')
    } catch (err) {
      dismiss(toastId)
      push('Could not export report')
    } finally {
      setExporting(false)
    }
  }

  return (
    <div className="app">
      <aside className="sidebar" aria-label="SkillBridge navigation">
        <NavLink to="/dashboard" className="brand">
          <BrandLogo size={38} />
          <div>
            <h2>SkillBridge</h2>
            <small>Career Intelligence</small>
          </div>
        </NavLink>

        <div className="navlabel">Workspace</div>
        <nav className="nav">
          <NavItem to="/dashboard" label="Overview" icon={IconGrid} needsCv hasCompletedCv={hasCompletedCv} />
          <NavItem to="/cv" label="My CV" icon={IconDoc} badge="AI" hasCompletedCv={hasCompletedCv} />
          <NavItem to="/jobs" label="Job Matches" icon={IconBriefcase} needsCv hasCompletedCv={hasCompletedCv} />
        </nav>

        <div className="navlabel">Intelligence</div>
        <nav className="nav">
          <NavItem to="/skills" label="Skill Gap" icon={IconBars} needsCv hasCompletedCv={hasCompletedCv} />
          <NavItem to="/roadmap" label="Roadmap" icon={IconList} needsCv hasCompletedCv={hasCompletedCv} />
          <NavItem to="/interview" label="Interview" icon={IconChat} needsCv hasCompletedCv={hasCompletedCv} />
        </nav>

        <div className="navlabel">Account</div>
        <nav className="nav">
          <NavLink to="/settings" className={({ isActive }) => (isActive ? 'active' : '')}>
            <IconSettings />
            <span>Settings</span>
          </NavLink>
        </nav>

        <div className="sidebottom">
          <div className="avatar">{initials}</div>
          <div>
            <b>{fullName || first}</b>
            <span>{bootstrapping ? 'Loading…' : 'Career profile'}</span>
          </div>
          <button
            type="button"
            className="logout"
            onClick={() => {
              logout()
              navigate('/login', { replace: true })
            }}
          >
            Log out
          </button>
        </div>
      </aside>

      <div className="main">
        <header className="topbar">
          <div>
            <div className="breadcrumb">Workspace / Career Intelligence</div>
            <div className="top-title">{title}</div>
          </div>
          <div className="actions">
            {isOverview && (
              <button type="button" className="btn" disabled={exporting} onClick={handleExport}>
                {exporting ? 'Preparing…' : 'Export report'}
              </button>
            )}
          </div>
        </header>
        <SessionErrorBanner />
        <div className="content">
          <Outlet />
        </div>
      </div>
      <ToastHost />
    </div>
  )
}
