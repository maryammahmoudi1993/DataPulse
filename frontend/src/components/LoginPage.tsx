import { useState } from 'react'
import { api } from '../api'

interface Props {
  onLogin: () => void
}

export function LoginPage({ onLogin }: Props) {
  const [tab, setTab] = useState<'login' | 'register'>('login')
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [workspace, setWorkspace] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handle = async () => {
    setError('')
    setLoading(true)
    try {
      const res = tab === 'login'
        ? await api.login(username, password)
        : await api.register({ username, password, workspace })
      localStorage.setItem('access', res.access)
      localStorage.setItem('refresh', res.refresh)
      onLogin()
    } catch {
      setError(tab === 'login' ? 'Invalid credentials.' : 'Registration failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <form
        onSubmit={e => { e.preventDefault(); void handle() }}
        className="bg-white rounded-2xl border border-gray-200 p-8 w-full max-w-sm space-y-5"
      >
        <h1 className="text-xl font-semibold text-gray-800">DataPulse</h1>

        <div className="flex gap-2 border-b border-gray-100 pb-4">
          {(['login', 'register'] as const).map(t => (
            <button
              type="button"
              key={t}
              onClick={() => setTab(t)}
              className={`text-sm px-3 py-1 rounded-lg transition ${
                tab === t ? 'bg-indigo-50 text-indigo-700 font-medium' : 'text-gray-500'
              }`}
            >
              {t === 'login' ? 'Sign in' : 'Register'}
            </button>
          ))}
        </div>

        <div className="space-y-3">
          <input
            placeholder="Username"
            autoComplete="username"
            value={username}
            onChange={e => setUsername(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
          />
          <input
            type="password"
            placeholder="Password"
            autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
            value={password}
            onChange={e => setPassword(e.target.value)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
          />
          {tab === 'register' && (
            <input
              placeholder="Workspace slug (e.g. acme-corp)"
              value={workspace}
              onChange={e => setWorkspace(e.target.value)}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm"
            />
          )}
          {error && <p className="text-xs text-red-600">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition disabled:opacity-50"
          >
            {loading ? 'Please wait…' : tab === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </div>
      </form>
    </div>
  )
}
