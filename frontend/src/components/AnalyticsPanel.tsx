import { useEffect, useState } from 'react'
import { apiRequest } from '../api'
import type { AlertRate, Rollup, Trend } from '../types'

interface Props {
  streamId: number | null
}

const DIR_LABEL: Record<string, string> = {
  up: '↗ Rising', down: '↘ Falling', flat: '→ Stable', unknown: '? Not enough data',
}
const DIR_COLOR: Record<string, string> = {
  up: 'text-red-500', down: 'text-blue-500', flat: 'text-gray-500', unknown: 'text-gray-400',
}

async function load<T>(path: string): Promise<T | null> {
  const res = await apiRequest(path)
  return res.ok ? ((await res.json()) as T) : null
}

export function AnalyticsPanel({ streamId }: Props) {
  const [rollups, setRollups] = useState<Rollup[]>([])
  const [trend, setTrend] = useState<Trend | null>(null)
  const [alertRate, setAlertRate] = useState<AlertRate | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (streamId === null) return
    let cancelled = false
    setLoading(true)
    setRollups([])
    setTrend(null)
    setAlertRate(null)

    Promise.all([
      load<Rollup[]>(`/streams/${streamId}/analytics/rollups/?period=HOURLY&limit=24`),
      load<Trend>(`/streams/${streamId}/analytics/trend/`),
      load<AlertRate>(`/streams/${streamId}/analytics/alert-rate/`),
    ])
      .then(([r, t, a]) => {
        if (cancelled) return
        setRollups(r ?? [])
        setTrend(t)
        setAlertRate(a)
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false) })

    return () => { cancelled = true }
  }, [streamId])

  if (streamId === null) return null

  const latest = rollups[0]

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-4 space-y-4">
      <p className="text-xs font-medium text-gray-600 uppercase tracking-wide">Analytics</p>

      {loading && <p className="text-xs text-gray-400">Loading…</p>}

      {trend && (
        <div className="space-y-1">
          <p className="text-xs text-gray-500">Signal trend (last {trend.samples} pts)</p>
          <p className={`text-sm font-medium ${DIR_COLOR[trend.direction]}`}>{DIR_LABEL[trend.direction]}</p>
          <p className="text-xs text-gray-400">
            slope {trend.slope.toFixed(4)} · R² {trend.r2.toFixed(2)}
          </p>
        </div>
      )}

      {alertRate && (
        <div className="space-y-1">
          <p className="text-xs text-gray-500">Alerts last {alertRate.period_hours}h</p>
          <p className="text-sm font-medium text-gray-800">{alertRate.total} total</p>
          <div className="flex gap-2 flex-wrap">
            {Object.entries(alertRate.by_severity)
              .filter(([, n]) => n > 0)
              .map(([severity, n]) => (
                <span key={severity} className="text-xs bg-gray-50 border border-gray-200 rounded px-1.5 py-0.5">
                  {severity} {n}
                </span>
              ))}
          </div>
        </div>
      )}

      {latest && (
        <div className="space-y-1">
          <p className="text-xs text-gray-500">
            Latest hourly rollup · {new Date(latest.bucket_ts).toLocaleString()}
          </p>
          <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
            <span className="text-gray-400">count</span>
            <span className="font-mono">{latest.count}</span>
            <span className="text-gray-400">mean</span>
            <span className="font-mono">{latest.mean.toFixed(3)}</span>
            <span className="text-gray-400">p95</span>
            <span className="font-mono">{latest.p95.toFixed(3)}</span>
            <span className="text-gray-400">alerts</span>
            <span className="font-mono">{latest.alert_count}</span>
          </div>
        </div>
      )}
    </div>
  )
}
