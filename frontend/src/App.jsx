import { Routes, Route, Link } from 'react-router-dom'
import CVUpload from './pages/CVUpload'

const Home = () => (
  <main className="max-w-3xl mx-auto p-8">
    <h1 className="text-2xl font-semibold mb-4">AI Career Intelligence Platform</h1>
    <p className="mb-4">The initial scaffold is ready. Use the navigation to test upload.</p>
    <ul className="list-disc ml-6">
      <li>FastAPI backend</li>
      <li>React + Vite frontend</li>
      <li>Docker Compose services</li>
      <li>CI workflow</li>
    </ul>
  </main>
)

const App = () => {
  return (
    <div className="min-h-screen">
      <nav className="bg-white shadow">
        <div className="max-w-5xl mx-auto p-4 flex gap-4">
          <Link to="/" className="font-medium">Home</Link>
          <Link to="/cv/upload" className="font-medium">Upload CV</Link>
        </div>
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/cv/upload" element={<CVUpload />} />
      </Routes>
    </div>
  )
}

export default App;
