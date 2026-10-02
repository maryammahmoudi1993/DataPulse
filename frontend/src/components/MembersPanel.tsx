import { useCallback, useEffect, useState } from 'react'
import { api } from '../api'
import type { Member } from '../types'

const ROLES = ['OWNER', 'MEMBER', 'VIEWER']

interface Props { workspaceId: number; currentUserId: number }

export function MembersPanel({ workspaceId, currentUserId }: Props) {
  const [members, setMembers] = useState<Member[]>([])
  const [error, setError] = useState('')

  const load = useCallback(() =>
    api.members(workspaceId).then(setMembers).catch(() => setError('Failed to load members.')),
  [workspaceId])

  useEffect(() => { load() }, [load])

  const changeRole = async (userId: number, role: string) => {
    setError('')
    try {
      await api.changeMemberRole(workspaceId, userId, role)
      load()
    } catch { setError('Role change failed — owner access required.') }
  }

  const remove = async (userId: number) => {
    if (!window.confirm('Remove this member?')) return
    setError('')
    try {
      await api.removeMember(workspaceId, userId)
      load()
    } catch { setError('Removal failed — owner access required.') }
  }

  return (
    <div className="space-y-2">
      {error && <p className="text-xs text-red-500">{error}</p>}
      <ul className="divide-y divide-gray-100">
        {members.map(m => (
          <li key={m.user_id}
              className="flex items-center justify-between py-2.5 text-sm">
            <div>
              <span className="font-medium text-gray-800">{m.username}</span>
              <span className="text-gray-400 ml-2 text-xs">{m.email}</span>
            </div>
            <div className="flex items-center gap-2">
              <select
                value={m.role}
                onChange={e => changeRole(m.user_id, e.target.value)}
                disabled={m.user_id === currentUserId}
                className="border border-gray-200 rounded text-xs px-2 py-1 bg-white disabled:opacity-50"
              >
                {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
              </select>
              {m.user_id !== currentUserId && (
                <button
                  onClick={() => remove(m.user_id)}
                  className="text-xs text-red-500 hover:text-red-700"
                >
                  Remove
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  )
}
