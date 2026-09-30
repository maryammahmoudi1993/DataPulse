import { StatusBadge } from './StatusBadge'
import type { StreamAlert } from '../types'

interface Props {
  alerts: StreamAlert[]
}

export function AlertFeed({ alerts }: Props) {
  if (alerts.length === 0) {
    return (
      <div className="text-sm text-gray-400 py-6 text-center">
        No alerts yet — system monitoring…
      </div>
    )
  }

  return (
    <ul className="divide-y divide-gray-100 max-h-72 overflow-y-auto">
      {alerts.map(a => (
        <li key={a.alert_id} className="flex items-center justify-between py-2 text-sm">
          <div className="flex items-center gap-2">
            <StatusBadge severity={a.severity} />
            <span className="font-mono text-gray-700">{a.value.toFixed(3)}</span>
            <span className="text-gray-400 text-xs">score {a.score.toFixed(2)}</span>
          </div>
          <span className="text-gray-400 text-xs">
            {new Date(a.timestamp).toLocaleTimeString()}
          </span>
        </li>
      ))}
    </ul>
  )
}
