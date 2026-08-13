import { useState } from 'react'
import axios from 'axios'

export default function CVUpload() {
  const [file, setFile] = useState(null)
  const [userId, setUserId] = useState('')
  const [message, setMessage] = useState('')

  const onSubmit = async (e) => {
    e.preventDefault()
    if (!file || !userId) {
      setMessage('Provide a user id and a file')
      return
    }
    const fd = new FormData()
    fd.append('file', file)
    fd.append('user_id', userId)
    try {
      const resp = await axios.post('/cv/upload', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
      setMessage('Uploaded CV id: ' + resp.data.id)
    } catch (err) {
      setMessage('Upload failed')
    }
  }

  return (
    <main className="max-w-2xl mx-auto p-8">
      <h2 className="text-xl font-semibold mb-4">Upload CV</h2>
      <form onSubmit={onSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium">User ID</label>
          <input value={userId} onChange={(e) => setUserId(e.target.value)} className="mt-1 block w-full border rounded p-2" />
        </div>
        <div>
          <label className="block text-sm font-medium">PDF or TXT file</label>
          <input type="file" accept=".pdf,.txt" onChange={(e) => setFile(e.target.files[0])} className="mt-1" />
        </div>
        <div>
          <button className="px-4 py-2 bg-blue-600 text-white rounded">Upload</button>
        </div>
      </form>
      {message && <p className="mt-4">{message}</p>}
    </main>
  )
}
