import { Link } from 'react-router-dom'
import { PageHeader, ViewShell } from '../components/ui'

export default function NotFoundPage() {
  return (
    <ViewShell>
      <PageHeader eyebrow="404" title="Page not found." sub="That route isn’t in SkillBridge." />
      <Link className="btn primary" to="/dashboard">
        Back to overview
      </Link>
    </ViewShell>
  )
}
