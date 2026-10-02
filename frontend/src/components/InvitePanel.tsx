import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { Invite } from '../types'

interface Props { workspaceId: number }

const ROLES = ['MEMBER', 'VIEWER', 'OWNER']

export function InvitePanel({ workspaceId }: Props) {
  const [invites, setInvites] = useState<Invite[]>([])
  const [email, setEmail] = useState('')
  const [role, setRole] = useState('MEMBER')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const load = useCallback(() =>
    api.listInvites(workspaceId).then(setInvites).catch(() => setError('Invites are visible to owners only.')),
  [workspaceId])

  useEffect(() => { load() }, [load])

  const send = async () => {
    if (!email.trim()) { setError('Email is required.'); return }
    setLoading(true)
    setError('')
    try {
      await api.createInvite(workspaceId, email.trim(), role)
      setEmail('')
      load()
    } catch {
      setError('Could not send invite — check if the email is already a member.')
    } finally {
      setLoading(false)
    }
  }

  const revoke = async (id: number) => {
    setError('')
    try {
      await api.revokeInvite(workspaceId, id)
      load()
    } catch { setError('Revoke failed.') }
  }

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <input
          placeholder="Email address"
          value={email}
          onChange={e => setEmail(e.target.value)}
          className="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm"
        />
        <select
          value={role}
          onChange={e => setRole(e.target.value)}
          className="border border-gray-200 rounded-lg text-sm px-2 py-1.5 bg-white"
        >
          {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
        </select>
        <button
          onClick={send}
          disabled={loading}
          className="text-sm px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition"
        >
          Invite
        </button>
      </div>
      {error && <p className="text-xs text-red-500">{error}</p>}

      {invites.length > 0 && (
        <ul className="divide-y divide-gray-100 text-sm">
          {invites.map(inv => (
            <li key={inv.id} className="flex items-center justify-between py-2">
              <div>
                <span className="text-gray-700">{inv.email}</span>
                <span className="ml-2 text-xs text-gray-400">{inv.role}</span>
              </div>
              <button
                onClick={() => revoke(inv.id)}
                className="text-xs text-gray-400 hover:text-red-500"
              >
                Revoke
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
