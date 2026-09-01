import { Route, Routes, Navigate } from 'react-router-dom'
import AppLayout from './components/AppLayout'
import RequireAuth from './components/RequireAuth'
import RequireCv from './components/RequireCv'
import { AnalysisProvider } from './context/AnalysisContext'
import { AuthProvider } from './context/AuthContext'
import { SessionProvider } from './context/SessionContext'
import { SkillDrawerProvider } from './context/SkillDrawerContext'
import { RoadmapExtrasProvider } from './context/RoadmapExtrasContext'
import { ToastProvider } from './components/ToastHost'
import CvPage from './pages/CvPage'
import DashboardPage from './pages/DashboardPage'
import HomePage from './pages/HomePage'
import InterviewPage from './pages/InterviewPage'
import JobsPage from './pages/JobsPage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'
import RegisterPage from './pages/RegisterPage'
import RoadmapPage from './pages/RoadmapPage'
import SettingsPage from './pages/SettingsPage'
import SkillGapsPage from './pages/SkillGapsPage'

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <SessionProvider>
          <AnalysisProvider>
            <RoadmapExtrasProvider>
              <SkillDrawerProvider>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/register" element={<RegisterPage />} />

                <Route
                  element={
                    <RequireAuth>
                      <AppLayout />
                    </RequireAuth>
                  }
                >
                  <Route path="/" element={<HomePage />} />
                  <Route path="/cv" element={<CvPage />} />
                  <Route path="/upload" element={<Navigate to="/cv" replace />} />
                  <Route path="/cv/upload" element={<Navigate to="/cv" replace />} />
                  <Route
                    path="/dashboard"
                    element={
                      <RequireCv>
                        <DashboardPage />
                      </RequireCv>
                    }
                  />
                  <Route
                    path="/jobs"
                    element={
                      <RequireCv>
                        <JobsPage />
                      </RequireCv>
                    }
                  />
                  <Route
                    path="/skills"
                    element={
                      <RequireCv>
                        <SkillGapsPage />
                      </RequireCv>
                    }
                  />
                  <Route
                    path="/roadmap"
                    element={
                      <RequireCv>
                        <RoadmapPage />
                      </RequireCv>
                    }
                  />
                  <Route
                    path="/interview"
                    element={
                      <RequireCv>
                        <InterviewPage />
                      </RequireCv>
                    }
                  />
                  <Route path="/settings" element={<SettingsPage />} />
                  <Route path="*" element={<NotFoundPage />} />
                </Route>

                <Route path="*" element={<Navigate to="/login" replace />} />
              </Routes>
            </SkillDrawerProvider>
            </RoadmapExtrasProvider>
          </AnalysisProvider>
        </SessionProvider>
      </ToastProvider>
    </AuthProvider>
  )
}
