import { useEffect, useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { StatusBadge } from '../components/StatusBadge'
import type { ShareData } from '../types'

interface Props { token: string }

/** Public read-only view of a shared stream; makes no authenticated requests. */
export function ShareViewPage({ token }: Props) {
  const [data, setData] = useState<ShareData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    fetch(`/api/share/${encodeURIComponent(token)}/`)
      .then(r => {
        if (r.status === 410) throw new Error('expired')
        if (r.status === 429) throw new Error('throttled')
        if (!r.ok) throw new Error('not_found')
        return r.json() as Promise<ShareData>
      })
      .then(setData)
      .catch((e: Error) => setError(
        e.message === 'expired' ? 'This share link has expired.'
          : e.message === 'throttled' ? 'Too many requests — please try again in a minute.'
            : 'Share link not found or revoked.'
      ))
  }, [token])

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center space-y-2">
          <p className="text-2xl">🔗</p>
          <p className="text-gray-600">{error}</p>
        </div>
      </div>
    )
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <p className="text-gray-400 text-sm">Loading…</p>
      </div>
    )
  }

  const chartData = data.points.map(p => ({
    time: new Date(p.timestamp).toLocaleTimeString(),
    value: p.value,
  }))

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="font-semibold text-gray-800">{data.title}</h1>
            <p className="text-xs text-gray-400 mt-0.5">
              {data.stream_name} · {data.detector_type} · {data.view_count} views
            </p>
          </div>
          <div className="text-xs text-gray-400">
            Expires {new Date(data.expires_at).toLocaleDateString()}
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-6 space-y-6">
        <div className="bg-white rounded-xl border border-gray-200 p-4">
          <p className="text-xs text-gray-400 mb-2">Last {data.points.length} data points</p>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                <XAxis dataKey="time" tick={{ fontSize: 10 }} interval="preserveStartEnd" />
                <YAxis tick={{ fontSize: 10 }} domain={['auto', 'auto']} />
                <Tooltip contentStyle={{ fontSize: 11 }} />
                <Line
                  type="monotone"
                  dataKey="value"
                  stroke="#6366f1"
                  dot={false}
                  strokeWidth={1.5}
                  isAnimationActive={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {data.open_alerts.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-4">
            <p className="text-xs font-medium text-gray-600 uppercase tracking-wide mb-3">Open alerts</p>
            <ul className="divide-y divide-gray-100">
              {data.open_alerts.map((a, i) => (
                <li key={i} className="flex items-center justify-between py-2 text-sm">
                  <div className="flex items-center gap-2">
                    <StatusBadge severity={a.severity} />
                    <span className="text-xs text-gray-400 font-mono">score {a.score}</span>
                  </div>
                  <span className="text-xs text-gray-400">{new Date(a.timestamp).toLocaleTimeString()}</span>
                </li>
              ))}
            </ul>
          </div>
        )}

        <p className="text-center text-xs text-gray-400">Read-only view · Powered by DataPulse</p>
      </main>
    </div>
  )
}
