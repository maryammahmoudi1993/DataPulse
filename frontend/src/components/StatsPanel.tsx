import {
  BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Cell,
} from 'recharts'
import type { StreamAlert } from '../types'

interface Props {
  alerts: StreamAlert[]
}

const SEVERITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] as const

const COLORS: Record<string, string> = {
  LOW: '#93c5fd',
  MEDIUM: '#fde68a',
  HIGH: '#fdba74',
  CRITICAL: '#fca5a5',
}

export function StatsPanel({ alerts }: Props) {
  const counts = alerts.reduce<Record<string, number>>((acc, a) => {
    acc[a.severity] = (acc[a.severity] ?? 0) + 1
    return acc
  }, {})

  const data = SEVERITIES.map(sev => ({ name: sev, count: counts[sev] ?? 0 }))
  const total = alerts.length

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-3">
      <p className="text-xs font-medium text-gray-600 uppercase tracking-wide">
        Session statistics
      </p>

      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="text-xl font-semibold text-gray-800">{total}</p>
          <p className="text-xs text-gray-400">total alerts</p>
        </div>
        <div>
          <p className="text-xl font-semibold text-orange-500">{counts['HIGH'] ?? 0}</p>
          <p className="text-xs text-gray-400">high</p>
        </div>
        <div>
          <p className="text-xl font-semibold text-red-500">{counts['CRITICAL'] ?? 0}</p>
          <p className="text-xs text-gray-400">critical</p>
        </div>
      </div>

      {total > 0 && (
        <div className="h-28">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={data} margin={{ top: 4, right: 4, left: -24, bottom: 0 }}>
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
              <Tooltip contentStyle={{ fontSize: 11 }} />
              <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                {data.map(d => (
                  <Cell key={d.name} fill={COLORS[d.name]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
