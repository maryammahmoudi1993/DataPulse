import { useEffect, useState } from 'react'
import { api } from '../api'
import type { AuditEntry } from '../types'

const ACTION_LABELS: Record<string, string> = {
  STREAM_CREATED: 'Stream created',
  STREAM_PAUSED: 'Stream paused',
  STREAM_RESUMED: 'Stream resumed',
  STREAM_DELETED: 'Stream deleted',
  MEMBER_INVITED: 'Member invited',
  MEMBER_ROLE_CHANGED: 'Role changed',
  MEMBER_REMOVED: 'Member removed',
  ALERT_ACKNOWLEDGED: 'Alert acknowledged',
  ALERT_RESOLVED: 'Alert resolved',
  EXPORT_REQUESTED: 'Export requested',
  LSTM_TRAINING_TRIGGERED: 'LSTM training triggered',
  WEBHOOK_CREATED: 'Webhook created',
  WEBHOOK_DELETED: 'Webhook deleted',
}

interface Props { workspaceId: number }

export function AuditPanel({ workspaceId }: Props) {
  const [entries, setEntries] = useState<AuditEntry[]>([])
  const [filter, setFilter] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    setError('')
    api.auditLog(workspaceId, filter || undefined)
      .then(setEntries)
      .catch(() => {
        setEntries([])
        setError('Audit log not available — owner access required.')
      })
  }, [workspaceId, filter])

  return (
    <div className="space-y-3">
      <select
        value={filter}
        onChange={e => setFilter(e.target.value)}
        className="border border-gray-200 rounded-lg text-xs px-2 py-1.5 bg-white"
      >
        <option value="">All actions</option>
        {Object.keys(ACTION_LABELS).map(a => (
          <option key={a} value={a}>{ACTION_LABELS[a]}</option>
        ))}
      </select>

      {error && <p className="text-xs text-red-500">{error}</p>}

      <ul className="divide-y divide-gray-100 max-h-96 overflow-y-auto text-xs">
        {entries.map(e => (
          <li key={e.id} className="py-2 flex justify-between items-start gap-2">
            <div>
              <span className="font-medium text-gray-700">
                {ACTION_LABELS[e.action] ?? e.action}
              </span>
              <span className="text-gray-400 ml-1.5">by {e.actor_username ?? 'system'}</span>
              {e.stream_name && (
                <span className="text-gray-400 ml-1.5">· {e.stream_name}</span>
              )}
              {e.target_username && (
                <span className="text-gray-400 ml-1.5">→ {e.target_username}</span>
              )}
            </div>
            <span className="text-gray-400 shrink-0">
              {new Date(e.created_at).toLocaleString()}
            </span>
          </li>
        ))}
        {entries.length === 0 && !error && (
          <li className="py-4 text-center text-gray-400">No events.</li>
        )}
      </ul>
    </div>
  )
}
