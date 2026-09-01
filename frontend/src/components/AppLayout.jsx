import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useRef } from 'react'
import { useAuth } from '../context/AuthContext'
import { useSession } from '../context/SessionContext'
import { useToast } from './ToastHost'
import SessionErrorBanner from './SessionErrorBanner'
import ToastHost from './ToastHost'
import {
  IconBars,
  IconBriefcase,
  IconChat,
  IconCheck,
  IconDoc,
  IconGrid,
  IconList,
  IconSettings,
} from './icons'
import { greetingName, initialsFrom } from '../lib/analysisUi'

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

function isActivePath(pathname, to) {
  if (to === '/dashboard') return pathname === '/' || pathname.startsWith('/dashboard')
  if (to === '/cv') return pathname === '/cv' || pathname.startsWith('/cv/')
  return pathname === to || pathname.startsWith(`${to}/`)
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
  const { push } = useToast()
  const fileRef = useRef(null)

  const title = TITLES[location.pathname] || 'Overview'
  const first = greetingName(fullName, userEmail)
  const initials = initialsFrom(fullName, userEmail)

  return (
    <div className="app">
      <aside className="sidebar" aria-label="SkillBridge navigation">
        <NavLink to="/dashboard" className="brand">
          <div className="brandmark">
            <IconCheck />
          </div>
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
            <button type="button" className="btn" onClick={() => push('Report export prepared')}>
              Export report
            </button>
            <button type="button" className="btn primary" onClick={() => fileRef.current?.click()}>
              + Upload CV
            </button>
            <input
              ref={fileRef}
              type="file"
              hidden
              accept=".pdf,application/pdf"
              onChange={(e) => {
                if (e.target.files?.[0]) {
                  push('Opening CV upload…')
                  navigate('/cv', { state: { file: e.target.files[0] } })
                  e.target.value = ''
                }
              }}
            />
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
